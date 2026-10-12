"""Collect MDDs for a list of funds into "YYYY - MM" folders with a tracker spreadsheet."""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

from .config import FundSource
from .extractor import pdf_text
from .report import PCT, _autosize, _header
from .scraper import Scraper, ScrapeError, slugify

log = logging.getLogger(__name__)

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
COLLECTED_FILL = PatternFill("solid", fgColor="E2EFDA")
OUTSTANDING_FILL = PatternFill("solid", fgColor="FCE4D6")


@dataclass
class Fund:
    name: str
    aum: float | None = None


@dataclass
class Collected:
    fund: str
    month: str | None = None   # "YYYY - MM"
    path: Path | None = None
    source: str = ""
    note: str = ""


def load_fund_list(path: str | Path, sheet: str | None = None) -> list[Fund]:
    """Fund names (and AUM if present) from the first two columns of a holdings workbook."""
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    funds, seen = [], set()
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        name = row[0] if row else None
        if i == 0 or not isinstance(name, str) or not name.strip() or name.strip().startswith("-No Value"):
            continue
        name = name.strip()
        if name in seen:
            continue
        seen.add(name)
        aum = row[1] if len(row) > 1 and isinstance(row[1], (int, float)) else None
        funds.append(Fund(name, aum))
    return funds


def document_month(text: str, today: date | None = None) -> str | None:
    """Month an MDD reports on, as "YYYY - MM".

    MDDs carry several dates (inception, issue, as-at); the latest one that is not in
    the future is taken as the reporting date.
    """
    today = today or date.today()
    found: list[tuple[int, int]] = []
    for d, mon, y in re.findall(r"\b(\d{1,2})?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})\b",
                                text, re.IGNORECASE):
        found.append((int(y), MONTHS[mon.lower()[:3]]))
    for y, m in re.findall(r"\b(\d{4})[/-](\d{1,2})[/-]\d{1,2}\b", text):
        found.append((int(y), int(m)))
    for m, y in re.findall(r"\b\d{1,2}[/-](\d{1,2})[/-](\d{4})\b", text):
        found.append((int(y), int(m)))
    valid = [(y, m) for y, m in found if 1 <= m <= 12 and 2000 <= y and (y, m) <= (today.year, today.month)]
    if not valid:
        return None
    y, m = max(valid)
    return f"{y} - {m:02d}"


def collect(funds: list[Fund], sources: dict[str, FundSource], scraper: Scraper, out_dir: str | Path,
            months: list[str] | None = None) -> list[Collected]:
    """Fetch each fund's MDD, file it under out_dir/"YYYY - MM"/ and write a tracker per month."""
    out_dir = Path(out_dir)
    results = []
    for fund in funds:
        src = sources.get(fund.name)
        if src is None or not any([src.url, src.page, src.file]):
            results.append(Collected(fund.name, note="no MDD source configured"))
            continue
        try:
            pdf = scraper.fetch(src)
            month = document_month(pdf_text(pdf))
            if month is None:
                results.append(Collected(fund.name, source=str(pdf), note="could not read the MDD date"))
                continue
            dest = out_dir / month / f"{_safe_name(fund.name)}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf, dest)
            results.append(Collected(fund.name, month, dest, src.url or src.page or src.file or ""))
            log.info("%s -> %s", fund.name, dest)
        except (ScrapeError, Exception) as exc:  # one bad fund shouldn't stop the run
            results.append(Collected(fund.name, source=src.url or src.page or src.file or "", note=str(exc)))
            log.warning("%s: %s", fund.name, exc)

    all_months = sorted({r.month for r in results if r.month} | set(months or []))
    for month in all_months:
        write_tracker(out_dir / month / f"MDD Tracker {month}.xlsx", month, funds, results)
    return results


def write_tracker(path: Path, month: str, funds: list[Fund], results: list[Collected]) -> Path:
    by_fund = {r.fund: r for r in results}
    wb = Workbook()
    ws = wb.active
    ws.title = "Tracker"
    _header(ws, 1, ["Fund", "AUM", "Status", "MDD month found", "File", "Source", "Notes"])
    collected = 0
    for i, fund in enumerate(funds, start=2):
        r = by_fund.get(fund.name, Collected(fund.name))
        if r.month == month:
            status, fill = "Collected", COLLECTED_FILL
            collected += 1
        else:
            status, fill = "Outstanding", OUTSTANDING_FILL
        row = [fund.name, fund.aum, status, r.month, r.path.name if r.month == month and r.path else None,
               r.source, r.note or (f"latest MDD found is for {r.month}" if r.month and r.month != month else None)]
        for j, v in enumerate(row, start=1):
            c = ws.cell(row=i, column=j, value=v)
            c.fill = fill
        ws.cell(row=i, column=2).number_format = "#,##0"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _autosize(ws)

    s = wb.create_sheet("Summary", 0)
    _header(s, 1, ["Month", month])
    rows = [("Funds", len(funds)), ("Collected", collected), ("Outstanding", len(funds) - collected)]
    for i, (k, v) in enumerate(rows, start=2):
        s.cell(row=i, column=1, value=k)
        s.cell(row=i, column=2, value=v)
    s.cell(row=5, column=1, value="% collected")
    s.cell(row=5, column=2, value="=IF(B2=0,0,B3/B2*100)").number_format = PCT
    _autosize(s)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def _safe_name(name: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\[\]]+', " ", name)
    return re.sub(r"\s+", " ", clean).strip() or slugify(name)
