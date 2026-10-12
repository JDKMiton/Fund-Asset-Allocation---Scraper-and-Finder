"""Command line entry point.

    python -m fund_allocator run      --sources config/sources.yaml --template config/template.yaml
    python -m fund_allocator extract  path/to/mdd.pdf --template config/template.yaml
    python -m fund_allocator collect  --funds holdings.xlsx --out "Webscaper MDDs"
"""

from __future__ import annotations

import argparse
import logging
import sys

from .allocation import look_through
from .collector import collect, load_fund_list
from .config import FundSource, Template, load_sources, load_template
from .extractor import Extraction, extract_from_pdf, match_category
from .report import write_workbook
from .scraper import Scraper, ScrapeError

log = logging.getLogger("fund_allocator")


def gather(sources: list[FundSource], template: Template, scraper: Scraper) -> list[Extraction]:
    extractions = []
    for src in sources:
        if src.allocation:
            alloc: dict[str, float] = {}
            unmapped = []
            for label, value in src.allocation.items():
                cat = match_category(label, template)
                if cat is None:
                    unmapped.append(label)
                    cat = label
                alloc[cat] = alloc.get(cat, 0.0) + float(value)
            ext = Extraction(fund=src.name, allocation=alloc, source="manual (sources.yaml)")
            if unmapped:
                ext.notes.append("labels not in template: " + ", ".join(unmapped))
            extractions.append(ext)
            continue
        try:
            path = scraper.fetch(src)
            ext = extract_from_pdf(path, src.name, template)
        except ScrapeError as exc:
            ext = Extraction(fund=src.name, allocation={}, source=src.url or src.page or src.file or "",
                             notes=[f"download failed: {exc}"])
        except Exception as exc:  # a corrupt PDF shouldn't stop the whole run
            ext = Extraction(fund=src.name, allocation={}, source=str(src.file or src.url or src.page),
                             notes=[f"extraction failed: {exc}"])
        level = logging.WARNING if ext.notes else logging.INFO
        log.log(level, "%s: %s %s", src.name, ext.allocation or "-", "; ".join(ext.notes))
        extractions.append(ext)
    return extractions


def cmd_run(args: argparse.Namespace) -> int:
    template = load_template(args.template)
    sources = load_sources(args.sources)
    scraper = Scraper(args.download_dir, delay=args.delay, respect_robots=not args.ignore_robots)
    extractions = gather(sources, template, scraper)

    by_fund = {e.fund: e.allocation for e in extractions}
    portfolios = template.portfolios
    if args.portfolio:
        portfolios = [p for p in portfolios if p.name == args.portfolio]
        if not portfolios:
            log.error("portfolio '%s' not found in %s", args.portfolio, args.template)
            return 2
    results = [look_through(p, by_fund, template, rescale_funds=not args.no_rescale) for p in portfolios]

    out = write_workbook(args.out, template, extractions, results)
    for r in results:
        print(f"\n{r.portfolio}")
        for cat, pct in r.allocation.items():
            if pct:
                print(f"  {cat:<28}{pct:8.2f}%")
        for w in r.warnings:
            print(f"  ! {w}")
    print(f"\nWorkbook written to {out}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    template = load_template(args.template)
    for pdf in args.pdfs:
        ext = extract_from_pdf(pdf, pdf, template)
        print(f"\n{pdf}  (as at: {ext.as_at or 'unknown'})")
        for r in ext.raw:
            print(f"  {r.label:<40}{r.value:8.2f}%  -> {r.category or '(not mapped)'}")
        print(f"  {'TOTAL (mapped)':<40}{ext.total:8.2f}%")
        for n in ext.notes:
            print(f"  ! {n}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    funds = load_fund_list(args.funds, args.sheet)
    sources = {s.name: s for s in load_sources(args.sources)}
    scraper = Scraper(args.download_dir, delay=args.delay, respect_robots=not args.ignore_robots)
    results = collect(funds, sources, scraper, args.out, months=args.month)
    got = sum(1 for r in results if r.month)
    print(f"{len(funds)} funds: {got} MDDs collected, {len(funds) - got} outstanding")
    for month in sorted({r.month for r in results if r.month} | set(args.month or [])):
        n = sum(1 for r in results if r.month == month)
        print(f"  {args.out}/{month}: {n} MDD(s) + tracker")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fund_allocator", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="download MDDs, extract allocations, write the Excel workbook")
    run.add_argument("--sources", default="config/sources.yaml")
    run.add_argument("--template", default="config/template.yaml")
    run.add_argument("--out", default="output/asset_allocation.xlsx")
    run.add_argument("--download-dir", default="data/downloads")
    run.add_argument("--portfolio", help="only calculate this portfolio from the template")
    run.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    run.add_argument("--ignore-robots", action="store_true", help="skip robots.txt checks")
    run.add_argument("--no-rescale", action="store_true",
                     help="don't scale each fund's allocation to 100%% before weighting")
    run.set_defaults(func=cmd_run)

    ext = sub.add_parser("extract", help="show what would be extracted from local PDFs (for tuning synonyms)")
    ext.add_argument("pdfs", nargs="+")
    ext.add_argument("--template", default="config/template.yaml")
    ext.set_defaults(func=cmd_extract)

    col = sub.add_parser("collect", help="download MDDs for every fund in a holdings workbook into "
                                         "'YYYY - MM' folders with a tracker spreadsheet")
    col.add_argument("--funds", required=True, help="workbook with fund names in column A (AUM in column B)")
    col.add_argument("--sheet", help="worksheet to read (default: first sheet)")
    col.add_argument("--sources", default="config/sources.yaml")
    col.add_argument("--out", default="output/MDDs", help="folder to create the month folders in")
    col.add_argument("--month", action="append", metavar="'YYYY - MM'",
                     help="always create this month's folder and tracker, even if no MDDs are found for it")
    col.add_argument("--download-dir", default="data/downloads")
    col.add_argument("--delay", type=float, default=1.0)
    col.add_argument("--ignore-robots", action="store_true")
    col.set_defaults(func=cmd_collect)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
