"""Collect MDDs for a list of funds into "YYYY - MM" folders with a tracker spreadsheet."""

from __future__ import annotations

import calendar
import logging
import re
import shutil
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

from .config import FundSource
from .extractor import pdf_text
from .facts import mdd_facts
from .report import PCT, _autosize, _header
from .scraper import Scraper, slugify

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
    isin: str | None = None
    facts: dict | None = None  # Fund AUM, Inception Date, Benchmark read from the MDD


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


_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_AS_AT = [  # explicit reporting-date phrases, most reliable first
    rf"as\s*(?:at|of)\s*(?:end\s*)?(?:\d{{1,2}}\s*)?{_MON}\s*(\d{{4}})",
    rf"as\s*(?:at|of)\s*(\d{{4}})[/-](\d{{1,2}})[/-]\d{{1,2}}",
    rf"as\s*(?:at|of)\s*\d{{1,2}}[/.-](\d{{1,2}})[/.-](\d{{4}})",
]


def _dates(text: str) -> list[tuple[int, int]]:
    """All (year, month) pairs in the order they appear in ``text``."""
    pattern = re.compile(rf"\b(?:\d{{1,2}}\s*)?{_MON}\s*(\d{{4}})\b|\b(\d{{4}})[/-](\d{{1,2}})[/-]\d{{1,2}}\b"
                         rf"|\b\d{{1,2}}[/.-](\d{{1,2}})[/.-](\d{{4}})\b", re.IGNORECASE)
    out = []
    for m in pattern.finditer(text):
        if m.group(1):
            out.append((int(m.group(2)), MONTHS[m.group(1).lower()[:3]]))
        elif m.group(3):
            out.append((int(m.group(3)), int(m.group(4))))
        else:
            out.append((int(m.group(6)), int(m.group(5))))
    return out


_CID = re.compile(r"\(cid:(\d+)\)")


def decode_cid(text: str) -> str:
    """Some MDDs use fonts whose text comes out as "(cid:21)(cid:19)..." - glyph numbers that are a
    fixed offset away from the real characters. Find the offset that turns them into month names
    and decode, so dates in those headers can be read."""
    if "(cid:" not in text:
        return text
    best, best_hits = None, 0
    for offset in range(20, 40):
        decoded = _CID.sub(lambda m: chr(int(m.group(1)) + offset) if 0 < int(m.group(1)) + offset < 0x10FFFF else "", text)
        hits = len(re.findall(rf"\b{_MON}\s*20\d\d", decoded, re.IGNORECASE))
        if hits > best_hits:
            best, best_hits = decoded, hits
    return best or text


def document_month(text: str, today: date | None = None, filename: str = "") -> str | None:
    """Month an MDD reports on, as "YYYY - MM".

    MDDs carry several dates (inception, TER period, issue, as-at). The reporting
    date is almost always the first recent date in the document, so in order of
    preference: the first date within the last six months, an explicit "as at/as of"
    date, a YYYY-MM (or YYYYMM) in the file name, then the latest date in the document.
    Dates in the current or a future month are ignored: an MDD reports on a past month-end.
    """
    today = today or date.today()
    text = decode_cid(text)

    def ok(y: int, m: int) -> bool:
        return 1 <= m <= 12 and 2000 <= y and (y, m) < (today.year, today.month)

    def fmt(y: int, m: int) -> str:
        return f"{y} - {m:02d}"

    for pat in (rf"as\s*at\s*end\s*(?:of\s*)?{_MON}\s*(\d{{4}})", rf"as\s*of\s*\d{{1,2}}\s*{_MON}\s*(\d{{4}})"):
        m = re.search(pat, text, re.IGNORECASE)
        if m and ok(int(m.group(2)), MONTHS[m.group(1).lower()[:3]]):
            return fmt(int(m.group(2)), MONTHS[m.group(1).lower()[:3]])
    oldest = (today.year * 12 + today.month - 1) - 6
    recent = [(y, m) for y, m in _dates(text) if ok(y, m) and y * 12 + m - 1 >= oldest]
    if recent:
        return fmt(*recent[0])
    for pat in _AS_AT:
        for m in re.finditer(pat, text, re.IGNORECASE):
            a, b = m.groups()
            y, mo = (int(b), MONTHS[a.lower()[:3]]) if not a.isdigit() else \
                (int(a), int(b)) if len(a) == 4 else (int(b), int(a))
            if ok(y, mo):
                return fmt(y, mo)
    fm =re.search(r"(20\d\d)[-_ ]?(0[1-9]|1[0-2])(?:[-_ ]?\d\d)?(?!\d)", filename)
    if fm and ok(int(fm.group(1)), int(fm.group(2))):
        return fmt(int(fm.group(1)), int(fm.group(2)))
    valid = [d for d in _dates(text) if ok(*d)]
    return fmt(*max(valid)) if valid else None


ISIN_RE = re.compile(r"\b(?:ZA|IE|LU|GB|GG|JE|KY|BM)[A-Z0-9]{9}\d\b")


def find_isins(text: str) -> list[str]:
    """ISINs in the order they appear (South African ones look like ZAE000123456)."""
    return list(dict.fromkeys(ISIN_RE.findall(text)))


MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august",
               "september", "october", "november", "december"]


def expand_url(template: str, month: str) -> str:
    """Fill {yyyy}, {mm}, {yyyymm}, {month}/{Month} ("august"), {mon}/{Mon}/{MON} ("aug"), {dd} (last day
    of the month), {bdd} (last weekday of the month) and {next_yyyy}/{next_mm} (the following month)
    for a "YYYY - MM" month."""
    y, m = month.split(" - ")
    name = MONTH_NAMES[int(m) - 1]
    ny, nm = (int(y) + 1, 1) if m == "12" else (int(y), int(m) + 1)
    last_day = calendar.monthrange(int(y), int(m))[1]
    last_weekday = last_day - max(0, calendar.weekday(int(y), int(m), last_day) - 4)
    values = dict(yyyy=y, mm=m, yyyymm=f"{y}{m}", month=name, Month=name.title(), mon=name[:3],
                  Mon=name[:3].title(), MON=name[:3].upper(), dd=f"{last_day:02d}",
                  bdd=f"{last_weekday:02d}", next_yyyy=str(ny), next_mm=f"{nm:02d}")
    # only known placeholders are replaced, so regex braces such as \d{4} in a link_match survive
    return re.sub(r"\{(\w+)\}", lambda x: values.get(x.group(1), x.group(0)), template)


def _has_placeholder(template: str) -> bool:
    return expand_url(template, "2000 - 01") != template


def candidate_urls(src: FundSource, months: list[str]) -> list[str]:
    urls = [u for u in [src.url, *(src.urls or [])] if u]
    out = []
    for u in urls:
        out.extend(dict.fromkeys(expand_url(u, m) for m in months) if _has_placeholder(u) else [u])
    return list(dict.fromkeys(out))


def collect(funds: list[Fund], sources: dict[str, FundSource], scraper: Scraper, out_dir: str | Path,
            months: list[str] | None = None, skip_saved: bool = True) -> list[Collected]:
    """Fetch each fund's MDD(s), file them under out_dir/"YYYY - MM"/ and write a tracker per month.

    A source may list several URLs and URL templates ({yyyy}, {mm}, {month}, ...), which are
    expanded for each month in ``months`` so earlier months can be back-filled. With ``skip_saved``,
    a fund whose MDD is already in the folder for every month in ``months`` is not searched again.
    """
    out_dir = Path(out_dir)
    months = months or []
    results: list[Collected] = []
    for fund in funds:
        src = sources.get(fund.name)
        if src is None or not any([src.url, src.urls, src.page, src.file, src.sanlam_fund, src.mandg_fund]):
            note = (src.note if src and src.note else None) or "no MDD source configured"
            results.append(Collected(fund.name, note=note, isin=src.isin if src else None))
            continue
        saved = [out_dir / m / f"{_safe_name(fund.name)}.pdf" for m in months]
        if skip_saved and saved and all(p.exists() for p in saved):
            for month, path in zip(months, saved):
                results.append(Collected(fund.name, month, path, "already saved - not searched again",
                                         src.note or "", src.isin or _isin_of(path), _facts_of(path)))
            log.info("%s: MDDs for %s already saved, not searched again", fund.name, ", ".join(months))
            continue
        got: list[Collected] = []
        errors = []
        fetches = [replace(src, url=u, urls=None, page=None) for u in candidate_urls(src, months)]
        if src.page:
            pages = (dict.fromkeys(expand_url(src.page, m) for m in months)
                     if _has_placeholder(src.page) else [src.page])
            matches = (dict.fromkeys(expand_url(src.link_match, m) for m in months)
                       if _has_placeholder(src.link_match) else [src.link_match])
            fetches += [replace(src, url=None, urls=None, page=p, link_match=lm) for p in pages for lm in matches]
        fetches = fetches or [src]
        for one in fetches:
            try:
                if one.page and not one.url:  # resolve the link first so its file name can date the MDD
                    one = replace(one, url=scraper.find_pdf_link(one.page, one.link_match, one.render))
                pdf = scraper.fetch(one)
                text = pdf_text(pdf)
                month = document_month(text, filename=Path(one.url or one.file or pdf).name)
                isins = find_isins(text)
                where = one.url or one.page or one.file or ""
                if month is None:
                    errors.append(f"could not read the MDD date ({where})")
                    continue
                if any(g.month == month for g in got):
                    continue
                dest = out_dir / month / f"{_safe_name(fund.name)}.pdf"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(pdf, dest)
                got.append(Collected(fund.name, month, dest, where, src.note or "",
                                     src.isin or (isins[0] if isins else None), _facts_of(dest, text)))
                log.info("%s -> %s", fund.name, dest)
            except Exception as exc:  # one bad fund or URL shouldn't stop the run
                errors.append(str(exc))
        if got:
            results.extend(got)
        else:
            results.append(Collected(fund.name, source=src.url or src.page or src.file or "",
                                     note="; ".join(filter(None, [src.note, *errors[:2]])), isin=src.isin))
            log.warning("%s: %s", fund.name, errors[:1])

    all_months = sorted({r.month for r in results if r.month} | set(months)
                        | {d.name for d in out_dir.glob("20?? - ??") if d.is_dir()})
    results = _with_earlier_runs(funds, results, out_dir, all_months)
    for month in all_months:
        write_tracker(out_dir / month / f"!MDD Tracker {month}.xlsx", month, funds, results)
        (out_dir / month / f"MDD Tracker {month}.xlsx").unlink(missing_ok=True)  # name used before the "!"
    return results


def _facts_of(pdf: Path, text: str | None = None) -> dict:
    try:
        return mdd_facts(pdf, text)
    except Exception:  # facts are a nice-to-have; never fail a run over them
        return {}


def _isin_of(pdf: Path) -> str | None:
    try:
        isins = find_isins(pdf_text(pdf))
    except Exception:  # an unreadable PDF just leaves the ISIN blank
        return None
    return isins[0] if isins else None


def _with_earlier_runs(funds: list[Fund], results: list[Collected], out_dir: Path,
                       months: list[str]) -> list[Collected]:
    """Count MDDs already in the month folders from earlier runs, so a site being down this
    week doesn't turn a collected fund back into an outstanding one."""
    have = {(r.fund, r.month) for r in results if r.month}
    extra = []
    for fund in funds:
        prev = next((r for r in results if r.fund == fund.name and r.isin), None)
        for month in months:
            path = out_dir / month / f"{_safe_name(fund.name)}.pdf"
            if (fund.name, month) not in have and path.exists():
                extra.append(Collected(fund.name, month, path, "downloaded in an earlier run", "",
                                       prev.isin if prev else None, _facts_of(path)))
    if not extra:
        return results
    got = {r.fund for r in results if r.month} | {e.fund for e in extra}
    # drop "not found" placeholders for funds that do have an earlier MDD
    return [r for r in results if r.month or r.fund not in got] + extra


def recent_months(n: int, today: date | None = None) -> list[str]:
    """The last ``n`` completed months as "YYYY - MM" (MDDs are published after month-end)."""
    today = today or date.today()
    idx = today.year * 12 + today.month - 1
    return [f"{(i) // 12} - {(i) % 12 + 1:02d}" for i in range(idx - n, idx)]


FACT_COLUMNS = ["Fund AUM", "Inception Date", "Benchmark"]


def write_tracker(path: Path, month: str, funds: list[Fund], results: list[Collected]) -> Path:
    by_fund: dict[str, list[Collected]] = {}
    for r in results:
        by_fund.setdefault(r.fund, []).append(r)
    wb = Workbook()
    ws = wb.active
    ws.title = "Tracker"
    _header(ws, 1, ["Fund", "MitonOptimal AUM", "ISIN", *FACT_COLUMNS, "Status", "MDD month",
                    "Other months collected", "File", "Source", "Notes"])
    collected = 0
    for i, fund in enumerate(sorted(funds, key=lambda f: f.name.casefold()), start=2):  # A-Z
        rs = by_fund.get(fund.name) or [Collected(fund.name, note="no MDD source configured")]
        this = next((r for r in rs if r.month == month), None)
        dated = sorted((r for r in rs if r.month), key=lambda r: r.month)
        shown = this or (dated[-1] if dated else rs[0])
        isin = next((r.isin for r in rs if r.isin), None)
        if this:
            status, fill = "Collected", COLLECTED_FILL
            collected += 1
        else:
            status, fill = "Outstanding", OUTSTANDING_FILL
        others = ", ".join(r.month for r in dated if r.month != month) or None
        note = shown.note
        if not this and dated:
            note = "; ".join(filter(None, [f"latest MDD found is for {dated[-1].month}", note]))
        facts = next((r.facts for r in [shown, *reversed(dated)] if r.facts), None) or {}
        row = [fund.name, fund.aum, isin, *(facts.get(c) for c in FACT_COLUMNS),
               status, shown.month if this else None, others,
               shown.path.name if this and shown.path else None, shown.source or None, note or None]
        for j, v in enumerate(row, start=1):
            ws.cell(row=i, column=j, value=v).fill = fill
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
