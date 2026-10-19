"""Loading and validating the YAML configuration files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Category:
    name: str
    synonyms: list[str]


@dataclass
class Holding:
    fund: str
    weight: float


@dataclass
class Portfolio:
    name: str
    holdings: list[Holding]


@dataclass
class Template:
    categories: list[Category]
    portfolios: list[Portfolio] = field(default_factory=list)
    section_headers: list[str] = field(default_factory=lambda: ["asset allocation"])
    tolerance: float = 2.0  # how far from 100% a fund total may be before it is flagged

    @property
    def category_names(self) -> list[str]:
        return [c.name for c in self.categories]


DEFAULT_LAG_DAYS = 30  # most managers post an MDD 1-3 weeks after month-end


@dataclass
class FundSource:
    name: str
    url: str | None = None          # direct link to a PDF
    page: str | None = None         # web page that links to the PDF
    link_match: str = r"mdd|minimum.?disclosure|fact.?sheet"
    file: str | None = None         # local PDF (manual download)
    allocation: dict[str, float] | None = None  # manual override, skips extraction
    render: bool = False            # render page with Playwright (JS-heavy sites)
    urls: list[str] | None = None   # extra URLs / URL templates ({yyyy}, {mm}, {yyyymm}, {month}, {mon})
    referer: str | None = None      # some document servers only answer requests sent from their site
    isin: str | None = None         # ISIN to report when the MDD doesn't print it
    note: str | None = None         # shown in the tracker (renamed fund, quarterly MDD, ...)
    browser: bool = False           # always download through the headless browser (bot-protected sites)
    sanlam_fund: str | None = None  # fund name in Sanlam Collective Investments' fact sheet API
    mandg_fund: str | None = None   # fund name in M&G's all-funds list (mandg.co.za)
    ignore_robots: bool = False     # download even though the site's robots.txt asks bots not to
    doc_names: list[str] | None = None  # other names the MDD may print (renamed fund, platform name)
    lag_days: int | None = None     # days after month-end the MDD is normally up (default DEFAULT_LAG_DAYS)
    frequency: str = "monthly"      # "quarterly": MDDs only for March, June, September and December
    keep_name: bool = False         # don't show the MDD's name in the tracker (e.g. the MDD prints an old name)
    current_name: str | None = None  # owner-confirmed current name, shown in the tracker


def normalise_label(text: str) -> str:
    """Lower-case and strip punctuation / extra whitespace so labels compare cleanly."""
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_template(path: str | Path) -> Template:
    data = yaml.safe_load(Path(path).read_text()) or {}
    categories = []
    for c in data.get("categories", []):
        synonyms = [normalise_label(s) for s in c.get("synonyms", [])]
        synonyms.append(normalise_label(c["name"]))
        categories.append(Category(name=c["name"], synonyms=sorted(set(synonyms), key=len, reverse=True)))
    if not categories:
        raise ValueError(f"{path}: template must define at least one category")

    portfolios = []
    for p in data.get("portfolios", []):
        holdings = [Holding(fund=h["fund"], weight=float(h["weight"])) for h in p.get("holdings", [])]
        portfolios.append(Portfolio(name=p["name"], holdings=holdings))

    return Template(
        categories=categories,
        portfolios=portfolios,
        section_headers=[normalise_label(h) for h in data.get("section_headers", ["asset allocation"])],
        tolerance=float(data.get("tolerance", 2.0)),
    )


def load_sources(path: str | Path) -> list[FundSource]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    sources = []
    for f in data.get("funds", []):
        src = FundSource(**f)
        if not any([src.url, src.urls, src.page, src.file, src.allocation, src.note, src.sanlam_fund, src.mandg_fund]):
            raise ValueError(f"{path}: fund '{src.name}' needs one of url, urls, page, file, allocation or note")
        sources.append(src)
    return sources
