import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.make_samples import make_all  # noqa: E402
from fund_allocator.allocation import look_through  # noqa: E402
from fund_allocator.cli import main  # noqa: E402
from fund_allocator.config import Holding, Portfolio, load_template  # noqa: E402
from fund_allocator.extractor import extract_from_pdf, extract_from_text, match_category  # noqa: E402
from fund_allocator.scraper import find_matching_links  # noqa: E402

TEMPLATE = load_template(ROOT / "config" / "template.yaml")


class MatchCategoryTest(unittest.TestCase):
    def test_synonyms(self):
        self.assertEqual(match_category("Local Equity", TEMPLATE), "SA Equity")
        self.assertEqual(match_category("GLOBAL EQUITIES", TEMPLATE), "Foreign Equity")
        self.assertEqual(match_category("Cash & Money Market", TEMPLATE), "SA Cash")
        self.assertEqual(match_category("Offshore cash", TEMPLATE), "Foreign Cash")

    def test_noise_not_mapped(self):
        self.assertIsNone(match_category("Total Expense Ratio (TER)", TEMPLATE))
        self.assertIsNone(match_category("Microsoft", TEMPLATE))


class ExtractTextTest(unittest.TestCase):
    def test_prefers_allocation_section(self):
        text = """Fund X MDD 31 August 2026
        TER 1.5%  1 year return 12.0%
        Asset Allocation
        SA Equity 60.0%   Foreign Equity 30.0%
        Cash 10.0%
        Max offshore 45%"""
        ext = extract_from_text(text, "X", TEMPLATE)
        self.assertEqual(ext.allocation, {"SA Equity": 60.0, "Foreign Equity": 30.0, "SA Cash": 10.0})
        self.assertEqual(ext.as_at, "31 August 2026")
        self.assertEqual(ext.notes, [])

    def test_flags_bad_total(self):
        ext = extract_from_text("Asset allocation\nLocal equity 50%\nForeign equity 20%", "Y", TEMPLATE)
        self.assertTrue(any("70.00%" in n for n in ext.notes))

    def test_nothing_found(self):
        ext = extract_from_text("No numbers here", "Z", TEMPLATE)
        self.assertEqual(ext.allocation, {})
        self.assertTrue(ext.notes)


class PdfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.balanced, cls.feeder = make_all(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_two_column_pdf(self):
        ext = extract_from_pdf(self.balanced, "Balanced", TEMPLATE)
        self.assertAlmostEqual(ext.total, 100.0)
        self.assertEqual(ext.allocation["SA Equity"], 38.5)
        self.assertEqual(ext.allocation["SA Property"], 4.3)

    def test_comma_decimals(self):
        ext = extract_from_pdf(self.feeder, "Feeder", TEMPLATE)
        self.assertEqual(ext.allocation, {"Foreign Equity": 95.5, "Foreign Cash": 3.0, "SA Cash": 1.5})


class LookThroughTest(unittest.TestCase):
    def test_weighted_sum(self):
        p = Portfolio("P", [Holding("A", 50), Holding("B", 50)])
        funds = {"A": {"SA Equity": 100}, "B": {"SA Equity": 40, "Foreign Equity": 60}}
        r = look_through(p, funds, TEMPLATE)
        self.assertAlmostEqual(r.allocation["SA Equity"], 70)
        self.assertAlmostEqual(r.allocation["Foreign Equity"], 30)
        self.assertEqual(r.warnings, [])

    def test_rescales_weights_and_fund_totals(self):
        p = Portfolio("P", [Holding("A", 30), Holding("B", 30)])
        funds = {"A": {"SA Equity": 99}, "B": {"SA Bonds": 101}}
        r = look_through(p, funds, TEMPLATE)
        self.assertAlmostEqual(r.allocation["SA Equity"], 50)
        self.assertAlmostEqual(sum(r.allocation.values()), 100)
        self.assertTrue(r.warnings)

    def test_missing_fund_is_unallocated(self):
        p = Portfolio("P", [Holding("A", 80), Holding("Missing", 20)])
        r = look_through(p, {"A": {"SA Equity": 100}}, TEMPLATE)
        self.assertAlmostEqual(r.allocation["Unallocated"], 20)


class ScraperLinkTest(unittest.TestCase):
    def test_finds_mdd_link(self):
        html = """<a href="/docs/annual-report.pdf">Annual report</a>
                  <a href="/docs/bal-2026-09.pdf">Minimum Disclosure Document</a>
                  <a href="/docs/fund-factsheet.pdf">Download</a>"""
        links = find_matching_links(html, "https://example.com/fund", r"minimum.?disclosure|fact.?sheet")
        self.assertEqual(links, ["https://example.com/docs/bal-2026-09.pdf",
                                 "https://example.com/docs/fund-factsheet.pdf"])


class EndToEndTest(unittest.TestCase):
    def test_run_writes_workbook(self):
        make_all()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.xlsx"
            rc = main(["run", "--sources", str(ROOT / "config/sources.yaml"),
                       "--template", str(ROOT / "config/template.yaml"),
                       "--out", str(out), "--download-dir", tmp])
            self.assertEqual(rc, 0)
            wb = load_workbook(out)
            self.assertEqual(wb.sheetnames[0], "Look-Through Summary")
            self.assertIn("Fund Allocations", wb.sheetnames)
            ws = wb["Look-Through Summary"]
            values = {ws.cell(row=i, column=1).value: ws.cell(row=i, column=2).value for i in range(2, 14)}
            self.assertAlmostEqual(values["SA Equity"], 23.1)
            self.assertAlmostEqual(values["SA Cash"], 8.625)


class CollectorTest(unittest.TestCase):
    def test_document_month_picks_latest_past_date(self):
        from datetime import date
        from fund_allocator.collector import document_month
        text = "Inception date 1 March 2004\nDate of issue: 30 September 2026\nNext review 2027/01/31"
        self.assertEqual(document_month(text, today=date(2026, 10, 12)), "2026 - 09")
        self.assertIsNone(document_month("no dates", today=date(2026, 10, 12)))

    def test_collect_files_by_month_and_tracks_outstanding(self):
        from fund_allocator.collector import Fund, collect
        from fund_allocator.config import FundSource
        from fund_allocator.scraper import Scraper
        with tempfile.TemporaryDirectory() as tmp:
            balanced, feeder = make_all(Path(tmp) / "pdfs")
            funds = [Fund("Balanced", 100.0), Fund("Feeder", 50.0), Fund("No Source", 10.0)]
            sources = {"Balanced": FundSource("Balanced", file=str(balanced)),
                       "Feeder": FundSource("Feeder", file=str(feeder))}
            out = Path(tmp) / "MDDs"
            results = collect(funds, sources, Scraper(Path(tmp) / "dl"), out)
            self.assertTrue((out / "2026 - 09" / "Balanced.pdf").exists())
            ws = load_workbook(out / "2026 - 09" / "MDD Tracker 2026 - 09.xlsx")["Tracker"]
            status = {ws.cell(row=i, column=1).value: ws.cell(row=i, column=3).value for i in range(2, 5)}
            self.assertEqual(status, {"Balanced": "Collected", "Feeder": "Collected", "No Source": "Outstanding"})
            self.assertEqual(sum(1 for r in results if r.month), 2)


if __name__ == "__main__":
    unittest.main()
