"""Collect MDDs for a list of funds into "YYYY - MM" folders with a tracker spreadsheet."""

from __future__ import annotations

import calendar
import csv
import hashlib
import logging
import re
import shutil
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

from .config import DEFAULT_LAG_DAYS, FundSource
from .pdfinfo import analyse_with_timeout, sha256
from .pdfinfo import shutdown as shutdown_pdf_reader
from .report import PCT, _autosize, _header
from .scraper import Scraper, slugify

log = logging.getLogger(__name__)

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
COLLECTED_FILL = PatternFill("solid", fgColor="E2EFDA")
OUTSTANDING_FILL = PatternFill("solid", fgColor="FCE4D6")  # late
PENDING_FILL = PatternFill("solid", fgColor="FFF2CC")
QUIET_FILL = PatternFill("solid", fgColor="EDEDED")   # quarterly fund, no MDD due this month
STATUSES = ["Collected", "Pending", "Late", "Quarterly", "No source"]


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
    mdd_name: str | None = None  # the fund's current name, when the MDD prints it with the fund's known ISIN


@dataclass
class Issue:
    """One line of a run's exceptions report."""
    fund: str
    kind: str      # Wrong document / Stale copy / Reissued / Date unreadable / PDF unreadable / ...
    detail: str = ""
    month: str | None = None  # None: applies to every month's tracker


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


# A date right after one of these belongs to somebody else's calendar (issue/print dates, inception,
# ESG panels, TER periods, quarterly holdings), not the month the MDD reports on.
_NEG_CUE = re.compile(r"(issue date|date of issue|issued|published|print date|printed|generated|revision|version|"
                      r"updated on|launch|inception|msci|esg|period:|expense ratio|payment date)([^\n]{0,30})", re.I)


def _blank_negative(text: str) -> str:
    return _NEG_CUE.sub(lambda m: m.group(1) + re.sub(r"\d", " ", m.group(2)), text)


def masthead_month(masthead: str, today: date | None = None) -> str | None:
    """The month printed in the masthead (top of page 1): a month-end date ("31 August 2026") or a
    bare month ("August 2026"). A mid-month date there is an inception or issue date, so it doesn't
    count. This is how a person reads an MDD, and it survives stale documents."""
    today = today or date.today()
    text = _blank_negative(decode_cid(masthead or ""))
    hits, spans = [], []
    for m in re.finditer(rf"\b(\d{{1,2}})\s*{_MON}\s*,?\s*(\d{{4}})\d?\b", text, re.I):
        y, mo, d = int(m.group(3)), MONTHS[m.group(2).lower()[:3]], int(m.group(1))
        spans.append(m.span())
        hits.append((y, mo, d == calendar.monthrange(y, mo)[1] if 1 <= mo <= 12 and y >= 2000 else False, False))
    for m in re.finditer(rf"\b{_MON}\s*(\d{{4}})\d?\b", text, re.I):
        if not any(a <= m.start() < b for a, b in spans):
            hits.append((int(m.group(2)), MONTHS[m.group(1).lower()[:3]], False, True))
    for m in re.finditer(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", text):
        y, mo, d = int(m.group(3)), int(m.group(2)), int(m.group(1))
        if 1 <= mo <= 12:
            hits.append((y, mo, d == calendar.monthrange(y, mo)[1], False))
    hits = [h for h in hits if 1 <= h[1] <= 12 and h[0] >= 2000 and (h[0], h[1]) < (today.year, today.month)
            and (h[2] or h[3])]
    if not hits:
        return None
    pool = [h for h in hits if h[2]] or hits
    y, mo = max((h[0], h[1]) for h in pool)
    return f"{y} - {mo:02d}"


def allocation_stamp(text: str) -> str | None:
    """The date the asset-allocation table carries ("Asset allocation as at 31 Aug 2026"). Kept apart from
    the MDD's month: some managers print a quarter-end allocation on every sheet in the quarter."""
    m = re.search(rf"allocation[^a-z0-9\n]{{0,3}}(?:\([^)]{{0,12}}\)\s*)?(?:as\s*at|as\s*of|on)\s*"
                  rf"(?:\d{{1,2}}\s*)?{_MON}\s*(\d{{4}})", decode_cid(text or ""), re.I)
    return f"{m.group(2)} - {MONTHS[m.group(1).lower()[:3]]:02d}" if m else None


_NAME_STOP = {"fund", "funds", "the", "of", "sci", "bci", "fr", "prescient", "class", "rihf", "rhf", "retail", "hedge",
              "investor", "ri", "feeder", "index", "tracker", "and", "unit", "trust", "ip", "snn", "lu", "usd", "zar",
              "fof", "a", "b", "c", "d", "e", "h", "p"}


def _name_norm(s: str) -> str:
    s = s.lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", s)  # drop "[Matrix]" / "(Obsidian)" tags
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def names_itself(text: str, names: list[str]) -> bool | None:
    """Does the MDD name the fund? True if every distinctive word of one of ``names`` appears in the
    text, False if none does, None when the PDF has too little text to tell (image-only pages)."""
    plain = _name_norm(decode_cid(text or ""))
    if len(re.sub(r"[^a-z]", "", plain)) < 200:
        return None
    squashed = plain.replace(" ", "")  # some MDDs extract without spaces
    for name in names:
        words = [w for w in _name_norm(name).split() if w not in _NAME_STOP and not re.fullmatch(r"[a-z]\d", w)]
        if words and all(re.search(rf"\b{re.escape(w)}\b", plain) or w in squashed for w in words):
            return True
    return False


def document_month(text: str, today: date | None = None, filename: str = "",
                   masthead: str | None = None) -> str | None:
    """Month an MDD reports on, as "YYYY - MM".

    MDDs carry several dates (inception, TER period, issue, as-at). The reporting
    date is almost always the first recent date in the document, so in order of
    preference: the first date within the last six months, an explicit "as at/as of"
    date, a YYYY-MM (or YYYYMM) in the file name, then the latest date in the document.
    Dates in the current or a future month are ignored: an MDD reports on a past month-end.
    """
    today = today or date.today()
    if masthead:
        found = masthead_month(masthead, today)
        if found:
            return found
    text = decode_cid(text)
    blanked = _blank_negative(text)
    if blanked != text:  # prefer dates that aren't issue/inception/ESG dates; use those only if nothing else
        return _month_from_text(blanked, today, filename) or _month_from_text(text, today, filename)
    return _month_from_text(text, today, filename)


def _month_from_text(text: str, today: date, filename: str) -> str | None:

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
            months: list[str] | None = None, skip_saved: bool = True,
            issues: list[Issue] | None = None) -> list[Collected]:
    """Fetch each fund's MDD(s), file them under out_dir/"YYYY - MM"/ and write a tracker per month.

    A source may list several URLs and URL templates ({yyyy}, {mm}, {month}, ...), which are
    expanded for each month in ``months`` so earlier months can be back-filled. With ``skip_saved``,
    a fund whose MDD is already in the folder for every month in ``months`` is not searched again.
    """
    out_dir = Path(out_dir)
    months = months or []
    results: list[Collected] = []
    issues = [] if issues is None else issues  # the caller may pass a list to get the exceptions back
    manifest = Manifest(out_dir / MANIFEST)
    for fund in funds:
        src = sources.get(fund.name)
        if src is None or not any([src.url, src.urls, src.page, src.file, src.sanlam_fund, src.mandg_fund]):
            note = (src.note if src and src.note else None) or "no MDD source configured"
            results.append(Collected(fund.name, note=note, isin=src.isin if src else None))
            issues.append(Issue(fund.name, "No source", note))
            continue
        saved = [out_dir / m / f"{_safe_name(fund.name)}.pdf" for m in months]
        if skip_saved and saved and all(p.exists() for p in saved):
            for month, path in zip(months, saved):
                info = _read_pdf(path)
                isins = find_isins(info.get("text", ""))
                results.append(Collected(fund.name, month, path, "already saved - not searched again",
                                         src.note or "", src.isin or (isins[0] if isins else None), info.get("facts"),
                                         confirmed_name(src, info.get("text", ""))))
            log.info("%s: MDDs for %s already saved, not searched again", fund.name, ", ".join(months))
            continue
        got: list[Collected] = []
        errors = []
        plain = dict(urls=None, page=None, sanlam_fund=None, mandg_fund=None)
        fetches = []
        if src.sanlam_fund or src.mandg_fund:  # the manager's own API first, then any backup URLs
            fetches.append(replace(src, url=None, urls=None, page=None))
        fetches += [replace(src, url=u, **plain) for u in candidate_urls(src, months)]
        if src.page:
            pages = (dict.fromkeys(expand_url(src.page, m) for m in months)
                     if _has_placeholder(src.page) else [src.page])
            matches = (dict.fromkeys(expand_url(src.link_match, m) for m in months)
                       if _has_placeholder(src.link_match) else [src.link_match])
            fetches += [replace(src, url=None, urls=None, sanlam_fund=None, mandg_fund=None, page=p, link_match=lm)
                        for p in pages for lm in matches]
        fetches = fetches or [src]
        for one in fetches:
            try:
                if one.page and not one.url:  # resolve the link first so its file name can date the MDD
                    one = replace(one, url=scraper.find_pdf_link(one.page, one.link_match, one.render))
                pdf = scraper.fetch(one)
                where = one.url or one.page or one.file or ""
                filed = _file_mdd(fund, src, Path(pdf), where, out_dir, months, got, issues, manifest)
                if filed:
                    got.append(filed)
            except Exception as exc:  # one bad fund or URL shouldn't stop the run
                errors.append(str(exc))
        if got:
            results.extend(got)
        else:
            results.append(Collected(fund.name, source=src.url or src.page or src.file or "",
                                     note="; ".join(filter(None, [src.note, *errors[:2]])), isin=src.isin))
            if errors:
                issues.append(Issue(fund.name, "Not found", "; ".join(errors[:2])))
            log.warning("%s: %s", fund.name, errors[:1])

    all_months = sorted({r.month for r in results if r.month} | set(months)
                        | {d.name for d in out_dir.glob("20?? - ??") if d.is_dir()})
    results = _with_earlier_runs(funds, results, out_dir, all_months, sources)
    shutdown_pdf_reader()
    for issue in issues:
        log.warning("%s: %s - %s", issue.kind, issue.fund, issue.detail)
    for month in all_months:
        write_tracker(out_dir / month / f"!MDD Tracker {month}.xlsx", month, funds, results,
                      issues=issues, sources=sources)
        (out_dir / month / f"MDD Tracker {month}.xlsx").unlink(missing_ok=True)  # name used before the "!"
    return results


MANIFEST = "_manifest.csv"
REJECTED = "_rejected"
STALE_MONTHS = 3  # an MDD this many months older than the oldest month collected is a stale copy


def _read_pdf(path: Path) -> dict:
    """Text, masthead and facts of a PDF, read in a worker with a time limit ({} if unreadable)."""
    try:
        return analyse_with_timeout(path)
    except Exception as exc:  # corrupt, encrypted or too slow: treat as unreadable
        log.warning("could not read %s: %s", Path(path).name, exc)
        return {}


def _text_digest(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text or "").strip().encode()).hexdigest()


class Manifest:
    """One row per MDD downloaded: when, from where, its fingerprint and what was done with it."""
    FIELDS = ["fetched_at", "fund", "month", "result", "file", "source", "sha256", "text_sha256",
              "allocation_stamp", "detail"]

    def __init__(self, path: Path):
        self.path = path
        self._text_sha: dict[str, str] = {}
        if path.exists():
            with path.open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("result") in ("filed", "reissued") and row.get("file"):
                        self._text_sha[row["file"]] = row.get("text_sha256", "")

    def text_sha(self, file: Path) -> str | None:
        return self._text_sha.get(self._rel(file))

    def _rel(self, file: Path) -> str:
        try:
            return str(Path(file).relative_to(self.path.parent))
        except ValueError:
            return str(file)

    def add(self, **row) -> None:
        if row.get("file"):
            row["file"] = self._rel(row["file"])
            if row.get("result") in ("filed", "reissued"):
                self._text_sha[row["file"]] = row.get("text_sha256", "")
        new = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.FIELDS)
            if new:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in self.FIELDS} | {"fetched_at": datetime.now().isoformat(timespec="seconds")})


def _reject(pdf: Path, fund: Fund, out_dir: Path, why: str) -> Path:
    """Move a refused download to _rejected/ (kept for diagnosis, never filed)."""
    folder = out_dir / REJECTED
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{date.today():%Y-%m-%d} {_safe_name(fund.name)} - {why}.pdf"
    n = 1
    while dest.exists():
        n += 1
        dest = folder / f"{date.today():%Y-%m-%d} {_safe_name(fund.name)} - {why} ({n}).pdf"
    shutil.copyfile(pdf, dest)
    return dest


def confirmed_name(src: FundSource | None, text: str) -> str | None:
    """The name the MDD prints for a renamed fund, when the fund's known ISIN (``isin`` in the config)
    is printed in the same MDD. An ISIN read from the MDD itself proves nothing, so it isn't used."""
    if not src or not src.isin or src.keep_name or not src.doc_names:
        return None
    if src.isin not in find_isins(decode_cid(text or "")):
        return None
    return next((n for n in src.doc_names if names_itself(text, [n])), None)


def _month_index(month: str) -> int:
    y, m = month.split(" - ")
    return int(y) * 12 + int(m) - 1


def _file_mdd(fund: Fund, src: FundSource, pdf: Path, where: str, out_dir: Path, months: list[str],
              got: list[Collected], issues: list[Issue], manifest: Manifest) -> Collected | None:
    """Check a downloaded MDD and file it under the month it reports on. Returns None if refused."""
    info = _read_pdf(pdf)
    text = info.get("text", "")
    sha = sha256(pdf)
    base = dict(fund=fund.name, source=where, sha256=sha, text_sha256=_text_digest(text),
                allocation_stamp=allocation_stamp(text) or "")
    if not info:
        manifest.add(**base, result="rejected", file=_reject(pdf, fund, out_dir, "unreadable"),
                     detail="PDF could not be read")
        issues.append(Issue(fund.name, "PDF unreadable", where))
        return None
    month = document_month(text, filename=Path(where or pdf).name, masthead=info.get("masthead"))
    if month is None:
        manifest.add(**base, result="rejected", file=_reject(pdf, fund, out_dir, "no date"), detail="no date found")
        issues.append(Issue(fund.name, "Date unreadable", where))
        return None
    names = [fund.name, *(src.doc_names or [])]
    named = names_itself(text, names)
    if named is False:
        manifest.add(**base, month=month, result="rejected", file=_reject(pdf, fund, out_dir, "wrong fund"),
                     detail=f"MDD does not name {' / '.join(names)}")
        issues.append(Issue(fund.name, "Wrong document", f"the PDF from {where} does not name the fund", month))
        return None
    if months and _month_index(month) < min(_month_index(m) for m in months) - STALE_MONTHS:
        manifest.add(**base, month=month, result="rejected", file=_reject(pdf, fund, out_dir, f"stale {month}"),
                     detail="older than the months being collected")
        issues.append(Issue(fund.name, "Stale copy", f"{where} still serves the {month} MDD"))
        return None
    if any(g.month == month for g in got):
        return None  # another source already gave this month in this run
    if named is None:
        issues.append(Issue(fund.name, "Name not checked", "the PDF has no readable text", month))
    dest = out_dir / month / f"{_safe_name(fund.name)}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    result, detail = "filed", ""
    if dest.exists():
        old_text_sha = manifest.text_sha(dest)
        if old_text_sha is None:
            old_text_sha = _text_digest(_read_pdf(dest).get("text", ""))
        if sha == sha256(dest) or old_text_sha == base["text_sha256"]:
            result = "unchanged"
        else:  # never overwrite a filed month: keep both and flag it
            copy = dest.with_name(f"{dest.stem} (reissued {date.today():%Y-%m-%d}).pdf")
            if not copy.exists():
                shutil.copyfile(pdf, copy)
                issues.append(Issue(fund.name, "Reissued",
                                    f"a different {month} MDD was downloaded and saved as '{copy.name}'; "
                                    f"the tracker still uses the first one", month))
            result, detail = "reissued", copy.name
            manifest.add(**base, month=month, result=result, file=copy, detail="kept beside the filed MDD")
    else:
        shutil.copyfile(pdf, dest)
    if result != "reissued":
        manifest.add(**base, month=month, result=result, file=dest, detail=detail)
    log.info("%s -> %s (%s)", fund.name, dest, result)
    isins = find_isins(text)
    return Collected(fund.name, month, dest, where, src.note or "", src.isin or (isins[0] if isins else None),
                     info.get("facts"), confirmed_name(src, text))


def _with_earlier_runs(funds: list[Fund], results: list[Collected], out_dir: Path,
                       months: list[str], sources: dict[str, FundSource] | None = None) -> list[Collected]:
    """Count MDDs already in the month folders from earlier runs, so a site being down this
    week doesn't turn a collected fund back into an outstanding one."""
    have = {(r.fund, r.month) for r in results if r.month}
    extra = []
    for fund in funds:
        prev = next((r for r in results if r.fund == fund.name and r.isin), None)
        for month in months:
            path = out_dir / month / f"{_safe_name(fund.name)}.pdf"
            if (fund.name, month) not in have and path.exists():
                info = _read_pdf(path)
                extra.append(Collected(fund.name, month, path, "downloaded in an earlier run", "",
                                       prev.isin if prev else None, info.get("facts"),
                                       confirmed_name((sources or {}).get(fund.name), info.get("text", ""))))
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


def due_date(month: str, src: FundSource | None) -> date:
    """The day an MDD for ``month`` is normally up: month-end plus the manager's usual delay."""
    y, m = (int(x) for x in month.split(" - "))
    lag = (src.lag_days if src and src.lag_days is not None else DEFAULT_LAG_DAYS)
    return date(y, m, calendar.monthrange(y, m)[1]) + timedelta(days=lag)


def outstanding_status(month: str, src: FundSource | None, today: date | None = None) -> str:
    """Why a fund has no MDD for ``month``: not posted yet (Pending), overdue (Late), a quarterly fund
    with nothing due this month (Quarterly), or nothing to search (No source)."""
    today = today or date.today()
    if src is None or not any([src.url, src.urls, src.page, src.file, src.sanlam_fund, src.mandg_fund]):
        return "No source"
    if src.frequency == "quarterly" and int(month[-2:]) % 3:
        return "Quarterly"
    return "Pending" if today <= due_date(month, src) else "Late"


def write_tracker(path: Path, month: str, funds: list[Fund], results: list[Collected],
                  issues: list[Issue] | None = None, sources: dict[str, FundSource] | None = None,
                  today: date | None = None) -> Path:
    sources = sources or {}
    issues = [i for i in (issues or []) if i.month in (None, month)]
    counts = dict.fromkeys(STATUSES, 0)
    by_fund: dict[str, list[Collected]] = {}
    for r in results:
        by_fund.setdefault(r.fund, []).append(r)
    wb = Workbook()
    ws = wb.active
    ws.title = "Tracker"
    _header(ws, 1, ["Fund", "MitonOptimal AUM", "ISIN", *FACT_COLUMNS, "Status", "MDD month",
                    "Other months collected", "File", "Source", "Notes"])
    def shown_name(fund: Fund) -> str:
        """The owner-confirmed current name, else the MDD's name once it prints the fund's known ISIN."""
        src = sources.get(fund.name)
        if src and src.current_name:
            return src.current_name
        rs = sorted((r for r in by_fund.get(fund.name, []) if r.month), key=lambda r: r.month, reverse=True)
        return next((r.mdd_name for r in rs if r.mdd_name), fund.name)

    for i, fund in enumerate(sorted(funds, key=lambda f: shown_name(f).casefold()), start=2):  # A-Z
        name = shown_name(fund)
        rs = by_fund.get(fund.name) or [Collected(fund.name, note="no MDD source configured")]
        this = next((r for r in rs if r.month == month), None)
        dated = sorted((r for r in rs if r.month), key=lambda r: r.month)
        shown = this or (dated[-1] if dated else rs[0])
        isin = next((r.isin for r in rs if r.isin), None)
        src = sources.get(fund.name)
        if this:
            status = "Collected"
        elif not sources:  # called without the sources: fall back to the plain wording
            status = "Late"
        else:
            status = outstanding_status(month, src, today)
        fill = {"Collected": COLLECTED_FILL, "Pending": PENDING_FILL, "Quarterly": QUIET_FILL}.get(status,
                                                                                                 OUTSTANDING_FILL)
        counts[status] += 1
        if status == "Late":
            issues.append(Issue(fund.name, "Late", f"no {month} MDD yet; normally up by "
                                                  f"{due_date(month, src):%d %b %Y}", month))
        others = ", ".join(r.month for r in dated if r.month != month) or None
        note = shown.note
        if not this and dated:
            note = "; ".join(filter(None, [f"latest MDD found is for {dated[-1].month}", note]))
        if status == "Pending" and src:
            note = "; ".join(filter(None, [f"not posted yet - normally up by {due_date(month, src):%d %b %Y}", note]))
        facts = next((r.facts for r in [shown, *reversed(dated)] if r.facts), None) or {}
        if name != fund.name:
            why = "confirmed by the owner" if src and src.current_name else f"ISIN {isin} matches the MDD"
            note = "; ".join(filter(None, [f"renamed - previously '{fund.name}' ({why})", note]))
        row = [name, fund.aum, isin, *(facts.get(c) for c in FACT_COLUMNS),
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
    rows = [("Funds", len(funds)), *((k, counts[k]) for k in STATUSES)]
    for i, (k, v) in enumerate(rows, start=2):
        s.cell(row=i, column=1, value=k)
        s.cell(row=i, column=2, value=v)
    n = len(rows) + 2
    s.cell(row=n, column=1, value="% collected")
    s.cell(row=n, column=2, value="=IF(B2=0,0,B3/B2*100)").number_format = PCT
    s.cell(row=n + 1, column=1, value="Exceptions")
    s.cell(row=n + 1, column=2, value=len(issues))
    _autosize(s)

    e = wb.create_sheet("Exceptions")
    _header(e, 1, ["Fund", "Issue", "Detail"])
    order = {k: i for i, k in enumerate(["Wrong document", "Stale copy", "Reissued", "PDF unreadable",
                                         "Date unreadable", "Not found", "Late", "Name not checked", "No source"])}
    for i, issue in enumerate(sorted(issues, key=lambda x: (order.get(x.kind, 99), x.fund.casefold())), start=2):
        e.cell(row=i, column=1, value=issue.fund)
        e.cell(row=i, column=2, value=issue.kind)
        e.cell(row=i, column=3, value=issue.detail)
    e.freeze_panes = "A2"
    _autosize(e)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def _safe_name(name: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\[\]]+', " ", name)
    return re.sub(r"\s+", " ", clean).strip() or slugify(name)
