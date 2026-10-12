# Fund Asset Allocation – Scraper and Finder

Downloads fund **Minimum Disclosure Documents (MDDs)** / fact sheets, pulls out each
fund's asset allocation, maps it onto your own asset-class template, and calculates the
**look-through (actual) asset allocation** of a portfolio made up of several funds.
Everything lands in an Excel workbook.

```
sources.yaml ──► scraper ──► PDFs ──► extractor ──► fund allocations ──┐
                                                                       ├─► look-through ──► asset_allocation.xlsx
template.yaml (asset classes + synonyms + portfolio weights) ──────────┘
```

## Quick start

```bash
pip install -r requirements.txt
python examples/make_samples.py          # creates two demo MDD PDFs
python -m fund_allocator run             # -> output/asset_allocation.xlsx
python -m unittest discover -s tests -t .
```

## Setting it up for your funds

1. **`config/sources.yaml`** – one entry per fund, telling the tool where its MDD lives:
   - `url:` a direct PDF link
   - `page:` the fund's web page; the first PDF link whose URL/text matches `link_match`
     (default `mdd|minimum disclosure|fact sheet`) is downloaded. Add `render: true` for
     JavaScript-heavy sites (needs Playwright).
   - `file:` a PDF you downloaded yourself (for sites behind logins / bot protection)
   - `allocation:` type the numbers in by hand

   File paths are relative to the folder you run the command from.

2. **`config/template.yaml`** – your reporting template:
   - `categories` – the asset classes you report on (SA Equity, Foreign Bonds, …) and the
     `synonyms` managers use for them in their MDDs.
   - `portfolios` – each portfolio's funds and weights. Names must match `sources.yaml`.

3. Check a new MDD before relying on it:

   ```bash
   python -m fund_allocator extract path/to/mdd.pdf
   ```

   This lists every `label  xx.x%` pair found and what it mapped to. Anything showing
   `(not mapped)` that is really an asset class → add it to that category's synonyms.

4. Run it: `python -m fund_allocator run [--portfolio "Name"] [--out file.xlsx]`

## Collecting MDDs for a fund list

```bash
python -m fund_allocator collect --funds AUM_By_Holding_Fund_Model_Portfolio.xlsx \
    --sheet "Holding Fund Totals" --exclude "^MitonOptimal FR" \
    --out "C:/Users/<you>/OneDrive/#Webscraper MDDs"
```

Reads the fund names in column A (AUM in column B), downloads each fund's MDD using
`config/sources.yaml` (the `name` there must match the fund name in the workbook), reads the
reporting date from the PDF and files it as `<out>/YYYY - MM/<Fund name>.pdf`. Each month folder
gets an `MDD Tracker YYYY - MM.xlsx` listing every fund as **Collected** or **Outstanding**
(with the reason: no source configured, download failed, or only an older month found).
Add `--month "2026 - 09"` to always create that month's folder and tracker.
Pointing `--out` at your OneDrive-synced folder puts everything straight into OneDrive.

## The workbook

| Sheet | What it shows |
|---|---|
| Look-Through Summary | Asset classes × portfolios – the final answer |
| LT *portfolio* | Each fund's weight and its contribution to every asset class |
| Fund Allocations | Allocation extracted from each MDD, total, as-at date, source, warnings (highlighted) |
| Extracted Lines | Audit trail: every label/percentage read from each PDF and where it was mapped |

## How the calculation works

For each asset class *c*:

    portfolio[c] = Σ  weight(fund) × allocation(fund, c)

- Fund allocations are rescaled to 100% first, so rounding in an MDD doesn't leak through
  (turn off with `--no-rescale`).
- Portfolio weights that don't add to 100% are rescaled and flagged.
- A fund whose allocation couldn't be found shows up as **Unallocated** rather than silently
  disappearing.

## Limitations

- Allocations shown **only as a chart image** (no text in the PDF) can't be read – use a
  manual `allocation:` entry for those funds.
- Some sites block automated downloads or need a login – download the PDF and use `file:`.
- The scraper respects `robots.txt` and waits 1s between requests by default. Only use
  `--ignore-robots` where you have permission.
