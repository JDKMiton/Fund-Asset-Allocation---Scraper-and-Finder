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

    def test_document_month_ignores_older_period_and_issue_dates(self):
        from datetime import date
        from fund_allocator.collector import document_month
        today = date(2026, 10, 12)
        # TER period end (Dec 2025) before the reporting month
        self.assertEqual(document_month("31 December 2025 August 2026 FUND INFORMATION", today), "2026 - 08")
        # an earlier holdings date in the text, but an explicit "as at end" header
        self.assertEqual(document_month("Top holdings 30 April 2026\nAs at end August 2026", today), "2026 - 08")
        # issue date in the current month is never the reporting month
        self.assertEqual(document_month("Issued 2 October 2026. Fund information on 30 September 2026", today),
                         "2026 - 09")
        # file name is used when the text has no recent date
        self.assertEqual(document_month("Launched 1 May 2001", today, "AGBF - 2026-07.pdf"), "2026 - 07")

    def test_document_month_reads_dotted_dates(self):
        from datetime import date
        from fund_allocator.collector import document_month
        text = "Launch date 23.11.2010\nBenchmark changed 01.08.2022\nAs at 31.08.2026 benchmark is MSCI"
        self.assertEqual(document_month(text, date(2026, 10, 13)), "2026 - 08")

    def test_document_month_decodes_cid_font_text(self):
        from datetime import date
        from fund_allocator.collector import document_month
        # "31 August 2026" encoded as glyph ids offset by 30, as in Marriott's MDDs
        enc = "".join(f"(cid:{ord(c) - 30})" for c in "31 August 2026")
        text = f"Marriott Core Income Fund\n{enc}\nmore text ... September 2026 fee change"
        self.assertEqual(document_month(text, date(2026, 10, 13)), "2026 - 08")

    def test_expand_url_templates(self):
        from fund_allocator.collector import candidate_urls
        from fund_allocator.config import FundSource
        src = FundSource("X", urls=["https://x/{yyyymm}/f.pdf", "https://x/{yyyy}/{month}/f-{mm}.pdf"])
        self.assertEqual(candidate_urls(src, ["2026 - 08"]),
                         ["https://x/202608/f.pdf", "https://x/2026/august/f-08.pdf"])

    def test_mandg_fact_sheets(self):
        from fund_allocator.scraper import mandg_fact_sheets
        html = (r'{\"name\":\"M\u0026G Balanced\",\"fundId\":\"GLOBALCOMP\",\"files\":[{\"fileType\":\"FactSheet\",'
                r'\"path\":\"https://x/inst.pdf\"}]},{\"name\":\"M\u0026G Balanced Fund\",\"fundId\":\"PRUA\",'
                r'\"files\":[{\"fileType\":\"FactSheet\",\"path\":\"https://x/mandg-balanced-fund.pdf\"},'
                r'{\"fileType\":\"Commentary\",\"path\":\"https://x/c.pdf\"}]}')
        self.assertEqual(mandg_fact_sheets(html)["m&g balanced fund"], "https://x/mandg-balanced-fund.pdf")

    def test_expand_url_keeps_regex_braces(self):
        from fund_allocator.collector import expand_url
        self.assertEqual(expand_url(r"/{Month}-{yyyy}-\d{4}", "2026 - 08"), r"/August-2026-\d{4}")

    def test_expand_url_last_weekday(self):
        from fund_allocator.collector import expand_url
        # 31 October 2026 is a Saturday, 31 August 2026 a Monday
        self.assertEqual(expand_url("{dd}{bdd}", "2026 - 10"), "3130")
        self.assertEqual(expand_url("{dd}{bdd}", "2026 - 08"), "3131")

    def test_find_isins(self):
        from fund_allocator.collector import find_isins
        self.assertEqual(find_isins("ISIN Code ZAE000019808 and IE00B2RGGV79, again ZAE000019808"),
                         ["ZAE000019808", "IE00B2RGGV79"])

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
            ws = load_workbook(out / "2026 - 09" / "!MDD Tracker 2026 - 09.xlsx")["Tracker"]
            status = {ws.cell(row=i, column=1).value: ws.cell(row=i, column=4).value for i in range(2, 5)}
            self.assertEqual(status, {"Balanced": "Collected", "Feeder": "Collected", "No Source": "Outstanding"})
            self.assertEqual(sum(1 for r in results if r.month), 2)

    def test_collect_skips_funds_already_saved_for_all_months(self):
        from fund_allocator.collector import Fund, collect
        from fund_allocator.config import FundSource
        from fund_allocator.scraper import Scraper
        with tempfile.TemporaryDirectory() as tmp:
            balanced, _ = make_all(Path(tmp) / "pdfs")
            out = Path(tmp) / "MDDs"
            (out / "2026 - 08").mkdir(parents=True)
            (out / "2026 - 08" / "Balanced.pdf").write_bytes(balanced.read_bytes())
            (out / "2026 - 08" / "MDD Tracker 2026 - 08.xlsx").write_bytes(b"old")  # replaced by the "!" name
            src = {"Balanced": FundSource("Balanced", file=str(balanced))}
            # September is missing, so the fund is searched and September is filed
            collect([Fund("Balanced")], src, Scraper(Path(tmp) / "dl"), out, months=["2026 - 08", "2026 - 09"])
            self.assertTrue((out / "2026 - 09" / "Balanced.pdf").exists())
            self.assertEqual(sorted(p.name for p in (out / "2026 - 08").glob("*.xlsx")), ["!MDD Tracker 2026 - 08.xlsx"])
            # both months saved: the source isn't touched (a missing file would otherwise be an error)
            src = {"Balanced": FundSource("Balanced", file=str(Path(tmp) / "gone.pdf"), isin="ZAE000000001")}
            results = collect([Fund("Balanced")], src, Scraper(Path(tmp) / "dl"), out,
                              months=["2026 - 08", "2026 - 09"])
            self.assertEqual(sorted(r.month for r in results), ["2026 - 08", "2026 - 09"])
            self.assertTrue(all(r.source.startswith("already saved") for r in results))
            ws = load_workbook(out / "2026 - 09" / "!MDD Tracker 2026 - 09.xlsx")["Tracker"]
            self.assertEqual([c.value for c in ws[2]][2:4], ["ZAE000000001", "Collected"])

    def test_collect_tracks_sources_and_takes_aum_from_workbook(self):
        from openpyxl import Workbook
        make_all()
        with tempfile.TemporaryDirectory() as tmp:
            holdings = Path(tmp) / "aum.xlsx"
            wb = Workbook()
            ws = wb.active
            for row in [("Fund", "AUM"), ("Removed Fund", 5.0), ("Feeder", 7.0), ("Balanced", 100.0)]:
                ws.append(row)
            wb.save(holdings)
            sources = Path(tmp) / "sources.yaml"
            sources.write_text(f"funds:\n- name: Feeder\n  file: {ROOT / 'examples/sample_global_equity_mdd.pdf'}\n"
                               f"- name: Balanced\n  file: {ROOT / 'examples/sample_balanced_mdd.pdf'}\n"
                               f"- name: alpha fund\n  note: no MDD\n")
            out = Path(tmp) / "MDDs"
            main(["collect", "--funds", str(holdings), "--sources", str(sources), "--out", str(out),
                  "--download-dir", tmp, "--month", "2026 - 09"])
            ws = load_workbook(out / "2026 - 09" / "!MDD Tracker 2026 - 09.xlsx")["Tracker"]
            rows = [(r[0], r[1]) for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]
            self.assertEqual(rows, [("alpha fund", None), ("Balanced", 100.0), ("Feeder", 7.0)])


if __name__ == "__main__":
    unittest.main()
