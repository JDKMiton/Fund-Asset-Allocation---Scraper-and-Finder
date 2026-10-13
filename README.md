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
    --sources config/mdd_sources.yaml \
    --month "2026 - 07" --month "2026 - 08" --month "2026 - 09" \
    --out "C:/Users/<you>/OneDrive - MitonOptimal/#Webscraper MDDs"
```

Tracks every fund listed in `config/mdd_sources.yaml` (add or remove a fund there to change the
tracker; funds are listed alphabetically). The `--funds` workbook is optional: its AUM (column B)
fills the tracker's AUM column, matched on fund name. Each fund's MDD is downloaded, the
reporting month is read from the PDF and it is filed as `<out>/YYYY - MM/<Fund name>.pdf`. Each month folder
gets an `!MDD Tracker YYYY - MM.xlsx` listing every fund with its **ISIN**, **Collected** or
**Outstanding** status, other months collected, the source link and notes (renamed fund,
quarterly MDD, not found, ...). Pointing `--out` at your OneDrive-synced folder puts everything
straight into OneDrive.

`config/mdd_sources.yaml` records, for each tracked fund, where its MDD is published:

| Source type | Example | How it is used |
|---|---|---|
| `url` | Coronation `…/comprehensive-fact-sheets/latest/CORB` | always serves the latest MDD |
| `urls` template | Allan Gray `…/Files/AGBF%20-%20{yyyy}-{mm}.pdf`, Nedgroup `…/factsheets/{yyyymm}/…` | filled in for every `--month`, so back months can be collected |
| `page` + `link_match` | Foord forms & documents, Prescient other funds, Rezco monthly pages | the MDD link is found on the page (`render: true` needs Playwright) |
| `note` only | M&G (served on port 8082), offshore funds without a known factsheet | fund shows as Outstanding with the reason |

The month an MDD covers is read from the document itself: an "as at end <month>" / "as of
<date>" header, otherwise the first date in the last six months (inception, TER-period and
issue dates are skipped), otherwise a YYYY-MM in the file name.

Notes from the first run:
- Some sites block scripts (Ninety One) or need a browser session/referrer (Sanlam
  Collective Investments' MDD links need `Referer: https://www.sanlaminvestments.com/`).
- Marriott and Aylett publish quarterly MDDs, so they only have quarter-end months.
- Allan Gray, Satrix and a few others don't print an ISIN on the MDD - add `isin:` in the
  sources file to fill the tracker column.

## Weekly automatic download to OneDrive (Windows)

A Windows scheduled task runs the collector every week and saves the newest MDDs straight into
your OneDrive-synced `#Webscraper MDDs` folder, so they appear in OneDrive automatically.

**One-time setup** (needs Python 3.11+ from python.org with "Add to PATH" ticked):

1. Get this repository onto your PC (GitHub Desktop, or *Code -> Download ZIP* on GitHub and unzip it).
2. Open PowerShell in the repository folder and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\windows\setup_weekly_task.ps1 `
       -FundsWorkbook "C:\path\to\AUM_By_Holding_Fund_Model_Portfolio.xlsx"
   ```

   This installs the Python packages and a headless Chromium, finds your OneDrive folder, and
   registers the task **"Fund MDD weekly download"** for Mondays at 07:00. Change it with
   `-Day Friday -Time 06:30`, or point at another folder with `-OutFolder "..."`.
   Every fund in `config/mdd_sources.yaml` is collected; `-FundsWorkbook` is optional and only
   fills in the AUM column (left blank without it).
3. Test it straight away: `Start-ScheduledTask -TaskName "Fund MDD weekly download"`.

**What each weekly run does**
- Looks for the MDDs of the last two completed months (e.g. a run in mid-October collects
  August and September) and saves each one as `#Webscraper MDDs\YYYY - MM\<Fund>.pdf`.
  A fund whose MDD is already saved in both month folders is not searched again (its Source
  column reads "already saved - not searched again"); add `--refetch` to the collect command
  to search for every fund anyway.
- Rewrites every month's `!MDD Tracker YYYY - MM.xlsx` (ISIN, Collected/Outstanding, notes). MDDs
  saved in earlier weeks stay counted even if a site is down this week.
- Pulls the latest `config/mdd_sources.yaml` from GitHub first (if git is installed), so source
  fixes reach the scheduled job automatically.
- Logs to `logs\weekly-YYYY-MM-DD.log` (last 12 kept).

The task runs as you while you're logged on (OneDrive must be running to sync). If the PC is
off at the scheduled time it runs as soon as it's back on.

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
