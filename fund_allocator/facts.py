"""Fund size, inception date and benchmark read from an MDD.

MDDs lay these out in many ways: "Fund size R256.1bn" on one line, a label with its value
underneath ("SIZE OF FUND:" / "R2.2bn"), or a label column with the values in a second column.
The PDF's word positions are tried first (value to the right of the label on the same line, else
directly below it), then the plain text. A value is only accepted if it looks right: an amount
for the fund size, a date for the inception date, words for the benchmark.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATE = (rf"\d{{1,2}}(?:st|nd|rd|th)?[\s-]*{_MON}[\s-]*,?\s*\d{{4}}|{_MON}\s*\d{{1,2}},?\s+\d{{4}}"
        rf"|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{4}}|\d{{4}}[/.-]\d{{1,2}}[/.-]\d{{1,2}}|\d{{2}}\.\d{{2}}\.\d{{2}}\b"
        rf"|{_MON}\s*\d{{4}}")
_UNIT = r"(?:\s?(?:bn|billion|b|m|mn|million|mil)\b)?"
AMOUNT = (rf"(?:R|ZAR|USD|US\$|\$|£|GBP|€|EUR)\s?\d[\d ,.]*\d{_UNIT}|(?:R|\$|£)\s?\d{_UNIT}"
          r"|\d[\d ,.]*\d\s?(?:bn|billion|m|mn|million)\b|\d[\d ,.]*\d\s(?:USD|ZAR|GBP|EUR)\b")

# fund-level labels first; "AUM", "market value" and a bare "size" can refer to a strategy or class
SIZE_LABEL = (r"fund\s*size|portfolio\s*size|size\s*of\s*(?:the\s*)?(?:fund|portfolio)|fund\s*value|portfolio\s*value"
              r"|total\s*net\s*assets|net\s*assets(?:\s*of\s*(?:the\s*)?fund)?|fund\s*aum")
SIZE_LABEL_LOOSE = r"market\s*value|assets\s*under\s*management|class\s*size|aum|size"
INCEPTION_LABEL = (r"(?:fund\s*|portfolio\s*)?inception\s*date(?:\s*of\s*(?:the\s*)?(?:portfolio|fund))?"
                   r"|date\s*of\s*inception|fund\s*inception|(?:fund\s*|portfolio\s*|strategy\s*)?launch\s*date"
                   r"(?:\s*of\s*(?:the\s*)?(?:portfolio|fund))?|inception|launch")
BENCHMARK_LABEL = r"(?:fund\s*|primary\s*|performance\s*)?benchmark"

_NOT_BENCHMARK = re.compile(
    r"(?i)^(?:fund\b|highest|lowest|return|since|cumulative|annuali[sz]ed|\(?%|year|\d+\s*year|max|performance|"
    r"other fees|r\s?\d|\d[\d.,]*\s*%?\s*(?:p\.?a\.?)?\s*(?:excl|incl)|transaction|total|category|investment|nav\b|"
    r"\d+(?:\.\d+)?$|index\s*$|[-–]$|b$|[a-z]{1,2}$)")


def _norm(v: str) -> str:
    return re.sub(r"\s+", " ", v).strip(" ,;:|")


def _two_digit_year(v: str) -> str:
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2})", v)
    if not m:
        return v
    yy = int(m.group(3))
    return f"{m.group(1)}.{m.group(2)}.{(1900 if yy > 50 else 2000) + yy}"


_BENCH_WORDS = re.compile(
    r"(?i)index|cpi|inflation|stefi|msci|ftse|jse|albi|alsi|swix|capi|sofr|sonia|zaronia|libor|jibar|repo|"
    r"average|category|sector|peer|composite|cash|call|deposit|rate|bond|asisa|s&p|world|treasury|"
    r"benchmark|return|ncd|\d\s*%")


_NOT_START = re.compile(r"(?:These|This|Active|Average|Banks|Sector|Value|High|Sharpe|Related|Rolling|Ranking|Annuali[sz]ed|"
                        r"Minimum|Portfolio|Peergroup$|Benchmark$|Other|When|Sharing|\d+-year)\b")


def _benchmark_ok(v: str | None, lowercase_ok: bool = False) -> str | None:
    if not v:
        return None
    v = v.strip()
    if (not lowercase_ok and not re.match(r"[A-Z0-9(]", v)) or _NOT_START.match(v):
        return None
    v = _norm(re.split(r"\s{2,}|\s\|\s", v)[0])
    v = re.sub(r"^[¹²³*\d]\s+", "", v)
    v = re.split(r"\s+(?:RETURN \(%\)|Transaction costs|Retail Class|Advice initial|INVESTMENT MANDATE|Top five|"
                 r"\d+ Years?\b|1 Year|Fund Benchmark|Fund \(%\)|(?:19|20)\d\d(?:\s+-?\d+\.\d){2}|Minimum|Benchmark \()",
                 v)[0]
    v = re.sub(r"\s+(?:\d+(?:[.,]\d+)?%?\s*){2,}$", "", v)  # trailing performance numbers
    if len(v) < 3 or _NOT_BENCHMARK.match(v) or not re.search(r"[A-Za-z]{3}", v) or "excl. VAT" in v \
            or not _BENCH_WORDS.search(v) or re.match(r"(?i)(the|is|and|or|to|of|in|over|for|with|by)\b", v) \
            or re.search(r"(?i)\bfees?\b|\bVAT\b|\bwe\b|board|gender|fluctuation|exchange rate", v):
        return None
    return v


_UNFINISHED = re.compile(r"(?:[,;(&+–-]|\b(?:and|or|of|in|the|to|plus|from|with|excluding|including|previously)|%"
                         r"|\b[A-Z&]+/[A-Z&]+|\b(?:Developed|Country|All|Global|World|Capped|Emerging|Aggregate))\s*$")
_NEXT_STOP = re.compile(r"(?:returns?\b|class\b|performance|what\b|how\b|low risk|regulation|the fund\b|fund\b|"
                        r"annual|highest|since|benchmark|source|minimum|risk|\d+\s*(?:yr|year))", re.I)
_PROSE = re.compile(r"\b(?:may|portfolios?|schemes?|manager|invest\w*|participation|derivatives?|securities|swaps|"
                    r"aims?|objective|policy|will|should|returns? over)\b", re.I)
_TAIL_STOP = re.compile(r"\s+(?:Annual management fee|management fee|PERFORMANCE|Low risk|Medium|High risk|"
                        r"\(?Net of Fees\)?|\d{6,})", re.I)


def _continued(value: str, text: str, end: int, max_lines: int = 3) -> str:
    """Join the following lines while the benchmark is clearly unfinished (long composites wrap)."""
    value = _TAIL_STOP.split(value)[0].rstrip()
    if re.search(r"\.\s*$", value):
        return value
    for line in text[end:].split("\n")[1:max_lines + 1]:
        line = line.strip()
        starts_inside = bool(re.match(r"\(|Net\b|TR\b", line)) or value.count("(") > value.count(")")
        if not line or not (_UNFINISHED.search(value) or starts_inside) or (_NEXT_STOP.match(line) and not starts_inside) \
                or _PROSE.search(line):
            break
        line = _TAIL_STOP.split(line)[0].rstrip()
        value = f"{value} {line}"
        if re.search(r"\.\s*$", value):
            break
    return value


# --- plain text --------------------------------------------------------------------------

def _from_text(text: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {"Fund AUM": None, "Fund AUM (loose)": None, "Inception Date": None,
                                  "Benchmark": None}
    for key, label in (("Fund AUM", SIZE_LABEL), ("Fund AUM (loose)", SIZE_LABEL_LOOSE)):
        m = re.search(rf"(?:{label})\s*(?:\([^)]{{0,15}}\))?\s*[:=]?\s*(?:as at [^:\n]{{0,25}}:?\s*)?({AMOUNT})",
                      text, re.I)
        out[key] = _norm(m.group(1)) if m else None
    m = re.search(rf"\b(?:{INCEPTION_LABEL})\s*(?:\([^)]{{0,20}}\))?\s*[:\-–]?\s*({DATE})", text, re.I)
    if m:
        out["Inception Date"] = _two_digit_year(_norm(m.group(1)))
    for p in (r"(?:the\s+)?fund[’'`]?s?\s+benchmark\s+(?:index\s+)?is\s+(?:the\s+)?([^\n]{3,}?)(?:\.\s|\.$|\n)",
              rf"{BENCHMARK_LABEL}\s*[¹1*]?\s*:\s*([^\n]{{3,}})",
              rf"(?:^|\n){BENCHMARK_LABEL}\s+(?![\d\-.(])([A-Za-z][^\n]{{2,}})",
              rf"\b{BENCHMARK_LABEL}\s+(?=[A-Z])([A-Z][^\n]{{2,}})"):
        for m in re.finditer(p, text, re.I):
            v = _benchmark_ok(_continued(m.group(1), text, m.end(1)), lowercase_ok=p.startswith("(?:the"))
            if v:
                out["Benchmark"] = v
                break
        if out["Benchmark"]:
            break
    return out


# --- word positions ----------------------------------------------------------------------

def _lines(words: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) < 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _run(words: list[dict], start_x: float, max_gap: float = 14) -> str:
    """Words left to right from start_x, stopping at the first wide gap (next column)."""
    out, last = [], start_x
    for w in words:
        if w["x0"] < start_x - 1:
            continue
        if w["x0"] - last > max_gap and out:
            break
        if not out and w["x0"] - start_x > 40:
            break
        out.append(w["text"])
        last = w["x1"]
    return " ".join(out)


def _from_words(pdf: pdfplumber.PDF, pages: int = 2) -> dict[str, str | None]:
    out = _scan_words(pdf, pages, [("Fund AUM", SIZE_LABEL, rf"^(?:{AMOUNT})"),
                                   ("Inception Date", INCEPTION_LABEL, rf"^(?:{DATE})"),
                                   ("Benchmark", BENCHMARK_LABEL, None)])
    out["Fund AUM (loose)"] = _scan_words(pdf, pages, [("Fund AUM", SIZE_LABEL_LOOSE, rf"^(?:{AMOUNT})")])["Fund AUM"]
    return out


def _scan_words(pdf: pdfplumber.PDF, pages: int, fields: list) -> dict[str, str | None]:
    out: dict[str, str | None] = {"Fund AUM": None, "Inception Date": None, "Benchmark": None}
    for page in pdf.pages[:pages]:
        lines = _lines(page.extract_words(use_text_flow=False, keep_blank_chars=False))
        for li, line in enumerate(lines):
            text = " ".join(w["text"] for w in line)
            for field, label, value_re in fields:
                if out[field]:
                    continue
                for m in re.finditer(rf"(?:^|(?<=\s))(?:{label})\s*(?:\([^)]{{0,15}}\))?\s*[:¹*]?", text, re.I):
                    # the word the label ends on, then the value to its right or below it
                    pos, end_word = 0, None
                    for w in line:
                        pos = text.index(w["text"], pos) + len(w["text"])
                        if pos >= m.end() - 1:
                            end_word = w
                            break
                    if end_word is None:
                        continue
                    first = line[[i for i, w in enumerate(line) if w is end_word][0]:]
                    candidates = [_run(first[1:], end_word["x1"] + 1)]
                    label_x0 = min(w["x0"] for w in line if w["x0"] <= end_word["x0"] and
                                   end_word["x0"] - w["x0"] < 120) if line else end_word["x0"]
                    for below in lines[li + 1:li + 3]:
                        gap = below[0]["top"] - line[0]["bottom"]
                        if gap > 16:
                            break
                        candidates.append(_run(below, label_x0 - 2, max_gap=12))
                    for c in candidates:
                        c = _norm(c)
                        if not c:
                            continue
                        if value_re:
                            mm = re.match(value_re, c, re.I)
                            if mm:
                                out[field] = _two_digit_year(_norm(mm.group(0)))
                        else:
                            out[field] = _benchmark_ok(c)
                        if out[field]:
                            break
                    if out[field]:
                        break
    return out


def mdd_facts(pdf_path: str | Path, text: str | None = None) -> dict[str, str | None]:
    """{"Fund AUM", "Inception Date", "Benchmark"} from an MDD (None where not found)."""
    words: dict[str, str | None] = {}
    try:
        with pdfplumber.open(pdf_path) as pdf:
            words = _from_words(pdf)
            if text is None:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages[:3])
    except Exception:  # an unreadable PDF just leaves the facts blank
        pass
    from_text: dict[str, str | None] = {}
    if text:
        from .collector import decode_cid
        from_text = _from_text(decode_cid(text))

    def first(*values):
        return next((v for v in values if v), None)

    # word positions are more reliable for amounts and dates; benchmarks read better as text
    return {"Fund AUM": first(words.get("Fund AUM"), from_text.get("Fund AUM"),
                              words.get("Fund AUM (loose)"), from_text.get("Fund AUM (loose)")),
            "Inception Date": first(words.get("Inception Date"), from_text.get("Inception Date")),
            "Benchmark": first(from_text.get("Benchmark"), words.get("Benchmark"))}
