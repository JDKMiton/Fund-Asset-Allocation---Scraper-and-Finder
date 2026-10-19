"""Pull the asset allocation table out of an MDD / fact sheet PDF."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from .config import Template, normalise_label

# "Local Equity 45.20%", "Foreign bonds: 3,1 %", "Cash .......... 2.0%"
PAIR_RE = re.compile(
    r"(?P<label>[A-Za-z][A-Za-z0-9 &/()'’\-.,]*?)\s*[:.\-–]*\s*"
    r"(?P<value>-?\d{1,3}(?:[.,]\d{1,4})?)\s*%"
)
DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}"
    r"|\d{4}[/-]\d{2}[/-]\d{2}|\d{2}[/-]\d{2}[/-]\d{4})\b",
    re.IGNORECASE,
)
SECTION_WINDOW = 30  # lines after an "asset allocation" header to search first


@dataclass
class RawLine:
    label: str
    value: float
    category: str | None


@dataclass
class Extraction:
    fund: str
    allocation: dict[str, float]
    raw: list[RawLine] = field(default_factory=list)
    as_at: str | None = None
    source: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(self.allocation.values()), 4)


def pdf_text(path: str | Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def match_category(label: str, template: Template) -> str | None:
    """Map a label from the PDF to a template category.

    Exact synonym match wins; otherwise the label may end with a synonym
    (e.g. "Asset allocation SA Equity" -> "sa equity"). Longest synonym wins.
    """
    norm = normalise_label(label)
    if not norm:
        return None
    best: tuple[int, str] | None = None
    for cat in template.categories:
        for syn in cat.synonyms:
            if norm == syn:
                return cat.name
            if norm.endswith(" " + syn) and (best is None or len(syn) > best[0]):
                best = (len(syn), cat.name)
    return best[1] if best else None


def _scan(lines: list[str], template: Template) -> list[RawLine]:
    found: list[RawLine] = []
    seen: set[tuple[str, float]] = set()
    for line in lines:
        for m in PAIR_RE.finditer(line):
            label = m.group("label").strip(" .:-–,")
            value = float(m.group("value").replace(",", "."))
            key = (normalise_label(label), value)
            if key in seen:
                continue
            seen.add(key)
            found.append(RawLine(label=label, value=value, category=match_category(label, template)))
    return found


def _section_lines(lines: list[str], template: Template) -> list[list[str]]:
    windows = []
    for i, line in enumerate(lines):
        norm = normalise_label(line)
        if any(h in norm for h in template.section_headers):
            windows.append(lines[i:i + SECTION_WINDOW])
    return windows


def _aggregate(raw: list[RawLine]) -> dict[str, float]:
    alloc: dict[str, float] = {}
    for r in raw:
        if r.category:
            alloc[r.category] = round(alloc.get(r.category, 0.0) + r.value, 4)
    return alloc


def extract_from_text(text: str, fund: str, template: Template, source: str = "") -> Extraction:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    candidates: list[list[RawLine]] = [_scan(w, template) for w in _section_lines(lines, template)]
    candidates.append(_scan(lines, template))  # whole document as a fallback

    # Prefer the candidate whose mapped total is closest to 100%, then the one with
    # the least noise (fees, returns, etc. that don't map to an asset class).
    def score(raw: list[RawLine]) -> tuple[float, int]:
        total = sum(_aggregate(raw).values())
        return (round(abs(100 - total), 4), sum(r.category is None for r in raw))

    best = min(candidates, key=score)
    alloc = _aggregate(best)
    date = DATE_RE.search(text)
    ext = Extraction(fund=fund, allocation=alloc, raw=best, as_at=date.group(0) if date else None, source=source)

    if not alloc:
        ext.notes.append("no asset allocation found - check the PDF or add a manual allocation")
    elif abs(ext.total - 100) > template.tolerance:
        ext.notes.append(f"allocation totals {ext.total:.2f}% (expected ~100%)")
        unmapped = [r.label for r in best if r.category is None]
        if unmapped:
            ext.notes.append("unmapped labels (add to template synonyms?): " + ", ".join(sorted(set(unmapped))[:10]))
    return ext


def extract_from_pdf(path: str | Path, fund: str, template: Template) -> Extraction:
    return extract_from_text(pdf_text(path), fund, template, source=str(path))
