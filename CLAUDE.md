# Instructions for AI assistants working on this repository

**Before any scan, scrape, source change or tracker rebuild, read [`HANDOVER.md`](HANDOVER.md) in full.**
It holds the owner's decisions, what each manager's website does, the renamed funds, the ISIN choices and
the open issues. Treat it as a data source.

**After the work, update `HANDOVER.md`** with anything new: a site that changed, a fund renamed, a source
that served the wrong or a stale document, an owner decision, an ISIN confirmed. Fix the section it belongs
to and add a dated line to the learning log (§10). Commit it with the change.

General scraping rules: [`docs/sa-factsheet-scraping-guide.md`](docs/sa-factsheet-scraping-guide.md).
Where it and `HANDOVER.md` disagree, `HANDOVER.md` records what was actually seen for these funds.

Run the tests with `python -m unittest tests.test_pipeline` before pushing.
