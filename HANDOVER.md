# Handover: MDD scraper and tracker

This file is the scraper's memory: the decisions the owner has made, what each manager's website does,
which funds need care, and what has gone wrong before. It is a data source as well as a handover.

## Read this first: the rule for every scan or scrape

1. **Before** any scan, scrape, source change or tracker rebuild, read this whole file. Check §3 (owner
   decisions), §5 (manager notes) and §7 (open issues) for the funds involved.
2. Do the work.
3. **After** the work, update this file with anything new you learned: a site that changed, a fund
   renamed, a source that served the wrong document, a new decision by the owner, an ISIN confirmed.
   - Add a dated line to the learning log (§10).
   - Fix the section it belongs to, so this file stays current rather than only growing.
   - If nothing new was learned, add a one-line log entry saying so.
4. Commit this file with the change it describes.

The detailed general guide this project follows is [`docs/sa-factsheet-scraping-guide.md`](docs/sa-factsheet-scraping-guide.md)
(rules R1–R10 and manager notes, checked Aug–Oct 2026). Where this file and the guide disagree, this file
records what was actually seen for *these* funds and wins.

---

## 1. What this is

- **Owner:** MitonOptimal Portfolio Management (jacquesdk@mitonoptimal.com).
- **Job:** every week, download the latest MDD (minimum disclosure document / fact sheet) of every fund the
  model portfolios hold. File each one under the month it reports on, and keep an **MDD Tracker** per month
  showing what has been collected and what is outstanding.
- **Asset allocation** from the MDDs is handled by a separate agent. This scraper only collects and
  checks documents and reads Fund AUM, Inception Date and Benchmark for the tracker.

## 2. How it runs

| Item | Value |
|---|---|
| Install on the owner's work PC | `C:\Tools\MDD-Scraper`. Until 20 Oct 2026 it was updated by copying the branch ZIP over it (Replace, keep `.venv`). From 20 Oct the owner was given steps to make it a git clone of this branch: `run_weekly.ps1` then runs `git pull --ff-only` before each run, and reinstalls packages when `requirements.txt` changes. **Pushing to this branch updates the PC at the next weekly run.** Check the top of the weekly log for the pull result. |
| Scheduled task | "Fund MDD weekly download", Mondays 07:00, runs `scripts\windows\run_weekly.ps1`; set up by `scripts\windows\setup_weekly_task.ps1` |
| Output folder | `E:\OneDrive - MitonOptimal Portfolio Management (Pty) Ltd\#Webscraper MDDs` (synced by OneDrive) |
| Fund list | `config/mdd_sources.yaml` (192 funds on 19 Oct 2026). **This file defines the tracker.** |
| AUM workbook | `AUM_By_Holding_Fund_Model_Portfolio.xlsx`, sheet "Holding Fund Totals". Only fills the "MitonOptimal AUM" column; it does not add or remove funds. |
| Excluded | `--exclude "^MitonOptimal FR"`: the owner sources the MitonOptimal FR funds directly. |
| Branch | `claude/fund-location-scraper-kvsmox` on GitHub `JacDK777/Fund-Asset-Allocation---Scraper-and-Finder` |
| Manual run | `Start-ScheduledTask -TaskName "Fund MDD weekly download"`, or `run_weekly.ps1 -OutFolder ... -FundsWorkbook ...` |
| Logs | `C:\Tools\MDD-Scraper\logs\weekly-YYYY-MM-DD.log` (last 12 kept) |

**What one run does** (`python -m fund_allocator collect`):
1. Works out the last two completed months (in October: August and September).
2. **Skips** a fund whose MDD is already saved in **both** month folders (owner's rule, 13 Oct 2026).
3. For the others, tries each source in order (manager API or page, then URLs and backups) and checks every
   download:
   - it really is a PDF: at least 1 KB, with `%PDF-` in the first KB;
   - it names the fund, or one of its `doc_names`; otherwise it goes to `_rejected/` as "Wrong document";
   - its month is read from the document: the masthead (top 15% of page 1) first, then the text, ignoring
     issue, inception, ESG, TER-period and payment dates;
   - it isn't more than 3 months older than the months being collected; otherwise it's rejected as a "Stale copy".
4. Files it as `<YYYY - MM>\<Fund>.pdf`. **Never overwrites:** the same month with different content is
   kept beside the original as `<Fund> (reissued YYYY-MM-DD).pdf` and flagged.
5. Logs every download in `_manifest.csv`: time, fund, month, result, file, source, sha256, text hash and
   allocation stamp.
6. Rewrites `!MDD Tracker YYYY - MM.xlsx` in each month folder.

**The tracker** has three sheets:
- **Tracker**, funds A–Z, with columns: Fund | Fund Manager | MitonOptimal AUM | ISIN | Fund AUM | Inception Date |
  Benchmark | Status | MDD month | Other months collected | File | Source | Notes.
- **Summary**, the counts per status.
- **Exceptions**, one line per problem.

Statuses:

| Status | Meaning |
|---|---|
| Collected | the MDD for this month is in the folder |
| Pending | not posted yet; still within the manager's normal delay (default 30 days after month-end, or `lag_days`) |
| Late | past the normal delay and still missing: look at it |
| Quarterly | `frequency: quarterly` fund; no MDD is due for this month |
| No source | the fund has no download source configured |

Exception kinds: Wrong document, Stale copy, Reissued, PDF unreadable, Date unreadable, Not found, Late,
Name not checked (the PDF has no text layer), No source.

## 3. Owner decisions (follow these; ask before changing them)

| Date | Decision |
|---|---|
| Oct 2026 | Skip the MitonOptimal FR funds (owner sources them). |
| Oct 2026 | Removed from the tracker and weekly grab: MitonOptimal International Managed Flexible, Glacier Money Market, Discovery Life Property Escalator, Baillie Gifford Worldwide EM Leading Companies (for now), Aylett Equity Prescient, Foord Flexible FoF, PSG Wealth Global Moderate Feeder, PSG Wealth Moderate FoF. Don't add them back unless asked. |
| Oct 2026 | Download Marriott (4 funds) and Steyn Capital despite their robots.txt ("Option A"; `ignore_robots: true`). The guide says to honour robots.txt, but this is the owner's decision. |
| 13 Oct 2026 | Only search for a fund when its MDD is missing in either of the last two month folders. |
| Oct 2026 | Tracker file name `!MDD Tracker YYYY - MM.xlsx` (the "!" sorts it to the top); funds A–Z; benchmark not cut off. |
| Oct 2026 | Share classes for ISINs: Allan Gray C where it exists, otherwise A; Satrix B1, except Smartcore A1; Marriott A (or the retail class where there is no A); otherwise use the class that can be found, and the owner corrects it later. The ISINs from the owner's "Funds.xlsx" buy list are the classes actually held. |
| 19 Oct 2026 | Asset allocation goes to a separate agent; this scraper doesn't extract it. |
| 19 Oct 2026 | If the MDD's fund name is the correct one (the ISINs match), show that name in the tracker (§6). |
| 19 Oct 2026 | Confirmed renames: Discovery Aggressive DAO FoF → Cogence Discovery Balanced Dynamic Asset Optimiser Fund of Funds; Mi-Plan IP Enhanced Income → Vunani FR Enhanced Income Fund. Shown in the tracker (`current_name`). |
| 19 Oct 2026 | Use Allan Gray's platform copies as a backup for M&G Balanced, Inflation Plus and Global Balanced, despite Allan Gray's robots.txt (`ignore_robots: true` on those three). |

## 4. Where things are

- `config/mdd_sources.yaml`: **the source registry**, one entry per fund. Fields:
  - `url` / `urls` (with templates `{yyyy} {mm} {yyyymm} {month} {Month} {mon} {Mon} {MON} {dd} {bdd} {next_yyyy} {next_mm}`);
  - `page` + `link_match` (the regex may contain the same templates) + `render`;
  - `sanlam_fund`, `mandg_fund`, `browser`, `referer`, `ignore_robots`;
  - `isin`, `note`, `doc_names`, `current_name`, `lag_days`, `frequency`, `keep_name`, `fund_manager`.
- `fund_allocator/collector.py`: the run, checks, filing, manifest, tracker. `facts.py`: Fund AUM, inception
  and benchmark. `pdfinfo.py`: PDF reading in a worker process with a 120 s limit. `scraper.py`: downloads,
  browser and site APIs.
- `#Webscraper MDDs\_manifest.csv`, `#Webscraper MDDs\_rejected\`: evidence; never delete them during a run.

## 5. Manager and site notes (what was actually seen)

"Stable" means one URL overwritten monthly; "dated" means the URL carries the month. Always date by content.

- **Allan Gray (own funds):** dated `…/fund/factsheet/<Fund Name>/Files/<CODE> - YYYY-MM.pdf`. Codes: AGBF,
  AGSF, AGEF, AGOE, AGGF, AGINA (Income), AGDA (SA Equity), AGTF00 (Tax-Free pack), and others in the config.
  Real 404s for months not up yet.
- **Allan Gray platform store (other managers):** the same store holds other managers' sheets, e.g.
  `M~and~G Inflation Plus Fund (Class B)/Files/PRCB - YYYY-MM.pdf` (dated, 4–5 weeks after month-end), but
  **allangray.co.za/robots.txt disallows them** (`M~and~G*`, `Coronation*`, `Nedgroup*`, `Satrix*`,
  `STANLIB*`, `Prescient*`, `PSG*` and others). The owner approved them **only as the M&G backup** (19 Oct
  2026): M&G Balanced PRAB, Inflation Plus PRCB, Global Balanced USD PRGBFB (B class, dated). Folder names
  for any others are on allangray.co.za/what-we-offer/unit-trusts/; ask before using them.
- **M&G:** the all-funds page embeds JSON (`"files":[{"fileType":"FactSheet","path":…}]`); `mandg_fund`
  reads it. PDFs are served from **mandg.co.za:8082**, which is blocked in the cloud environment but works on
  the owner's PC. The media key changes on every upload, and old keys keep serving old files.
- **Coronation:** `…/comprehensive-fact-sheets/latest/<CODE>` always serves the current sheet (e.g. CNSB
  Bond, CNTF Top 20).
- **Nedgroup:** dated folder `…/factsheets/{yyyymm}/Nedgroup%20Investments%20<Fund>%20Fund%20<Class>.pdf`.
  A folder for a month never published can serve a later month's sheet, so date by content.
- **Ninety One:** bot-protected; needs the browser (`browser: true`). The main source is the H-class
  fact sheet (the class held); the backup is the A-class MDD
  `…/minimum-disclosure-document/91-sa-ut-<fund>-a-zar-mdd.pdf`. H-class MDD URLs don't exist (404).
- **Sanlam Collective Investments (Amplify, Denker, Catalyst and others):** `sanlam_fund` reads Sanlam's
  fact-sheet API (FundPress links, current only).
  - **Its link for Amplify SCI Diversified Income served the Active Equity sheet**, so that fund uses
    Amplify's own fund page.
  - Amplify Multi Strategy is now Amplify SCI Active Equity RHF (AG Capital replaced Obsidian).
- **Prescient (Prescient funds, Abax, Fairtree, Steyn Equity, Vulcan, Bateleur, 36One, Laurium):** links are
  on `prescient.co.za/funds/other-funds/` (rendered) and change monthly. `link_match` with month templates,
  e.g. `{yyyy}-{mm}-abax-absolute-fund-mdd`. Abax "Absolute"/"Balanced" are not the "SA Absolute"/"SA
  Balanced" funds. Fairtree's PDFs have no text layer, so the month comes from the file name and the name
  check can't run.
- **Fundrock (ex-BCI) funds:** static `bcis.co.za/upload/factsheet_categories_folders/funds/<Manager>/<Fund> (<Class>) <CODE>.pdf`.
  The full list is on bcis.co.za/fundrock-collective-investments/funds/funds. Sasfin → **Otto1890 FR**.
- **Discovery (15 funds):** `discovery.co.za/invest-public/ws/documvest-factsheet/download/<JSE code>`, one
  file per code. The guide says it has served the **previous** month; trust the content date. Its PDFs
  extract without spaces.
- **Satrix:** `satrix.co.za/fund/mdd/<CODE>` redirects to the current MDD (e.g. SLEA1).
- **Momentum Wealth platform** (`wealth.momentum.co.za/investments/factsheets/<slug>-(<class>).pdf`): used
  for Curate, STANLIB and others. **Known to serve stale and wrong-fund sheets**; the name check and stale
  check exist for this. STANLIB copies are about a month behind (`lag_days: 60`).
- **PPS / ppsisecure:** PPS Balanced Passive's current sheet is still filed under its **old name** "PPS
  Balanced Index Tracker Fund". STANLIB Absolute Plus, STANLIB Income, STANLIB Enhanced Multi Style and SIM
  Inflation Plus come from ppsisecure copies about a month behind.
- **STANLIB:** its own site blocks automated access; use the platform copies above.
- **Marriott:** robots.txt disallows bots (overridden by the owner). MDDs use cid-encoded fonts (the
  scraper decodes them). Core Income is **monthly**; Dividend Growth, Essential Income and Property Income
  are **quarterly**.
- **10X (ex-CoreShares):** the fund page links the current Class B tracker-fund MDD with unpredictable
  upload folders. Posted about 6 weeks after month-end (`lag_days: 50`).
- **Merchant West (ex-Counterpoint):** `merchantwest.co.za/investments/our-funds/` links monthly MDDs (`SI_Merchant-West-SCI-…-August-2026-1.pdf`).
- **Ranmore:** `ranmorefunds.com/historic-factsheets/` lists every month publicly (`/{Month}-{yyyy}[^/]*\.pdf`).
- **Janus Henderson:** `cdn.janushenderson.com/webdocs/HGLZTI_LU0572952280_MAR191_M_{dd}{mm}{yyyy}_XX(EN-GB).pdf`.
  Only the latest month stays online, so a month can only be collected while it's current.
- **Schroders:** document store `api.schroders.com/document-store/SISF-Global-Sustainable-Growth-A-Acc-FMR-LUEN.pdf`
  (the Luxembourg edition is current; the US edition is from 2022). Dates are written "31.08.2026".
- **BlackRock / iShares:** `…/gls-download/literature/fact-sheet/<name>-<isin>-gb-en-individual.pdf` is
  monthly; the SA MDD is quarterly only.
- **Old Mutual:** `oldmutualinvest.com/om-docs/<asset uid>/<Name>.pdf` redirects to the latest version.
  Each fund has three links (MDD, holdings, risk/return); RAFI 40 uses `blt534f03c64ce9c4b6`.
- **Curate:** curateinvestments.com is behind Cloudflare; its MDD button points at Momentum's
  `curate-momentum-…-(a)-zaf.pdf`.
- **Vulcan Value Equity:** an Irish UCITS fund, fact sheet on Prescient's other-funds page.
- **Foord:** `foord.co.za/sites/default/files/{next_yyyy}-{next_mm}/<Fund>%20Class%20A%20at%20{yyyy}-{mm}-{dd}.pdf`.
- **Gryphon:** stable `gryphon.com/documents/<fund-slug>.pdf`.

## 6. Renamed funds

The config keeps the owner's name: files, the AUM match and the skip rule depend on it. `doc_names` holds
what the MDD prints. `current_name` is a name the owner has confirmed; the tracker always shows it.
Otherwise **the tracker shows the MDD's name** (with a "renamed - previously …" note) once an
MDD prints that name **together with the ISIN we hold for the fund** (`isin:` in the config). An ISIN read
from the MDD itself proves nothing, so it doesn't count. `keep_name: true` stops this for funds whose MDD
prints an *old* name (PPS Balanced Passive). This is the owner's rule from 19 Oct 2026. On 19 Oct only
Sasfin → Otto1890 was confirmed this way; the others need an ISIN on file that is also printed in their MDD.

| Tracker name | Now printed as |
|---|---|
| Sasfin BCI Flexible Income | Otto1890 FR Flexible Income Fund (ISIN ZAE000206397 unchanged) |
| Counterpoint SCI Global Equity Feeder / Worldwide Flexible | Merchant West SCI … |
| CoreShares S&P SA Top 50 Tracker Fund | 10X S&P SA Top50 Tracker Fund |
| Amplify SCI Multi Strategy RIHF (Obsidian) | Amplify SCI Active Equity Retail Hedge Fund (AG Capital) |
| PPS Balanced Passive Fund | file still named "PPS Balanced Index Tracker Fund" |
| Ninety One Global Multi Asset Income Feeder | Ninety One Global Managed Income Feeder |
| SIM Inflation Plus Fund | SCI Inflation Plus; from 9 Oct 2026 SCI Ninety One Cautious Managed Fund |
| Momentum Capped SWIX Index Fund | Momentum Capped All Share Fund |
| Mi-Plan IP Enhanced Income | Vunani FR Enhanced Income Fund (code MIPEI); confirmed by the owner, shown in the tracker |
| Discovery Aggressive Dynamic Asset Optimiser FoF | Cogence Discovery Balanced Dynamic Asset Optimiser FoF (code DADAOF); confirmed by the owner, shown in the tracker |
| Old Mutual RAFI 40 Index Fund | balloting a rename to Old Mutual RAFI SA Index Fund |

### Fund managers (owner's request, 20 Oct 2026)

The tracker's **Fund Manager** column shows `fund_manager` from the config. If a fund has no `fund_manager`,
it shows the investment manager the MDD names. All 192 funds were set on 20 Oct 2026, checked against each
fund's latest MDD ("Investment manager", "About the fund manager", "Managed by", "Asset managers"). The rule:
where the manager is the one in the fund's name, that manager; otherwise the third party. Third parties
found:

| Range | Who manages it |
|---|---|
| Amplify (Sanlam) | each fund's boutique: Matrix (Defensive Balanced, Income Plus, Absolute), Terebinth (Strategic Income, Diversified Income), Truffle (Wealth Protector), Oyster Catcher (Managed Equity, Equity), Marble Rock (Real Income), Acumen Capital (Absolute Income), All Weather (Enhanced Equity), AG Capital (Multi Strategy, ex-Obsidian) |
| Nedgroup | Taquanta + BlackRock (Core Guarded, Diversified, Accelerated), BlackRock (Core Global), Abax (Flexible Income, Opportunity, Entrepreneur), Truffle (Balanced), Foord (Stable), Veritas (Global Equity), Pyrford (Global Cautious), Laurium (SA Equity), First Pacific Advisors (Global Flexible) |
| Discovery | Ninety One SA, for all 8 Discovery funds; the DAO fund is Cogence, with asset allocation advised by BlackRock |
| PPS (multi-manager) | Managed: 36ONE (exclusive manager); Equity: Truffle, 36ONE, STANLIB, Oyster Catcher, Fairtree; Flexible Income: Prescient, Ninety One; Balanced Passive: Prescient. Underlying managers can change quarterly. |
| Allan Gray Orbis feeders | Orbis Investment Management (Allan Gray's own funds are Allan Gray) |
| Curate (Momentum) | Enhanced Yield: Momentum Fixed Income; Flexible Property: Sesfikile Capital |
| Others | Old Mutual Global Equity: Jupiter Fund Management; STANLIB Global Balanced Feeder: J.P. Morgan (underlying fund); SIM Inflation Plus: Ninety One investment team (management outsourced to SIM; renamed SCI Ninety One Cautious Managed from 9 Oct 2026); Mi-Plan Enhanced Income: Vunani Fund Managers; Mi-Plan Global Macro and Multi Asset Balanced Defensive: sub-investment manager Think Cell; Sasfin: Otto1890; Counterpoint: Merchant West; CoreShares: 10X; iShares: BlackRock; PR Truffle: Truffle |

Check these when a fund changes manager (e.g. Amplify Multi Strategy: Obsidian → AG Capital in Nov 2024).

## 7. Open issues and questions for the owner

- **No ISIN:** Bateleur Long Short, Bateleur Special Opportunities and M&G Property Fund D.
- **ISINs from one source or another class:**
  - CoreShares/10X uses the ETF class A ISIN ZAE000204327, because the unit-trust class B ISIN wasn't found;
  - Allan Gray Optimal C and Tax-Free Balanced C come only from SA Shares;
  - SIM Inflation Plus ZAE000021283 has no class stated.
- **M&G port 8082** is unreachable from the cloud environment (it works on the owner's PC). Balanced,
  Inflation Plus and Global Balanced have the Allan Gray backup; Dividend Maximiser, Property D and the two
  feeders have none (Allan Gray doesn't host them).
- **Fund details:**
  - Fund AUM, inception date and benchmark are read automatically and can be blank or imperfect;
  - Discovery benchmarks run together without spaces;
  - a few long composite benchmarks stop where the MDD mixes in text from another column.
- **Old files:** if `2026 - 09\Marriott Core Income.pdf` exists from an early run, it is the August sheet
  and should be moved.

## 8. ISINs: where they come from

- `isin:` in the config wins. Otherwise the first ISIN printed in the MDD is used.
- **19 Oct 2026:** 50 ISINs were added from the owner's Funds.xlsx buy list. Each was checked against the
  MDD; where the MDD shows another class, the owner's class was kept.
- Further ISINs were found online; all pass the ISIN check-digit test:
  - Allan Gray Bond A, Money Market A, Optimal C, Tax-Free Balanced C;
  - Satrix ALSI, RAFI 40 and MSCI World B1; Smartcore A1;
  - Marriott Core Income A, Dividend Growth R, Property Income A, Essential Income C;
  - PPS Equity B, PPS Flexible Income (probably A2);
  - Gryphon, 10X, Curate B3, Sygnia A, 36One;
  - M&G Balanced A, Inflation Plus B, Global Balanced (Irish).

## 9. For the asset-allocation agent

- PDFs: `#Webscraper MDDs\<YYYY - MM>\<Fund>.pdf`, filed under the month the MDD reports on.
- `_manifest.csv` has each file's sha256, source and `allocation_stamp` (the "Asset allocation as at …"
  date when printed), which can differ from the MDD month for quarter-end allocations.
- Reissued copies sit beside the original. Use the original unless the owner says otherwise.
- Read `docs/sa-factsheet-scraping-guide.md` §6–7, on reading tables by word position and the checks.

## 10. Learning log (newest first; add a line after every scan or change)

- **2026-10-20, self-updating install:** extracting the branch ZIP into Downloads failed with "Path too long"
  (0x80010135) on the deep `skill\...\scripts\windows\setup_weekly_task.ps1`. The owner was told to
  extract to a short folder, then given one-time steps (install Git, turn `C:\Tools\MDD-Scraper` into a clone,
  sign in to GitHub once) so the weekly task pulls updates itself. `run_weekly.ps1` now pulls only in a
  git clone, and reinstalls packages if `requirements.txt` changed.

- **2026-10-20, Fund Manager column:** added to every tracker (second column) at the owner's request. Each
  fund's latest MDD was read for its manager, and the result is in `fund_manager` for all 192 funds (§6).
  If `fund_manager` isn't set, the MDD's investment manager is used; it is read for 79 of the 175 MDDs.
  It only takes a capitalised company name straight after the label, because a looser pattern picked up
  table headings and sentences. Seen: Discovery's funds are all managed by Ninety One; the SIM Inflation
  Plus MDD already names the Ninety One team; Allan Gray's balanced MDDs mention Orbis for the offshore
  part. The weekly run rewrites every month folder's tracker, so June and July get the column too.

- **2026-10-19, reusable skill:** the collector is packaged as the `sa-fund-mdd-collector` skill in
  `skill/` (for other projects and accounts). It asks where to save the MDDs, then
  `scripts/init_project.py` creates a project with its own HANDOVER.md, CLAUDE.md, empty registry and
  this registry as an example. The AUM column heading is now `--aum-label` (default "AUM held"; this
  project's weekly script passes "MitonOptimal AUM"). **When `fund_allocator/` changes, copy it to
  `skill/sa-fund-mdd-collector/assets/project/fund_allocator/`** so the skill stays in step. Quick check:
  a new 2-fund project collected Coronation Balanced Plus and Allan Gray Balanced into the chosen folder.
  Seen: Coronation's benchmark is cut at "ASISA fund category average (excluding" (the line wraps); still open.

- **2026-10-19:** The owner confirmed the Discovery DAO → Cogence and Mi-Plan → Vunani renames (now
  `current_name`) and approved the Allan Gray M&G backup. Test: with mandg.co.za:8082 unreachable, M&G
  Balanced, Inflation Plus and Global Balanced collected both August and September from Allan Gray.

- **2026-10-19, second test run** (cloud): 192 funds, MDDs for 185. No wrong documents after the link
  fix. Fundrock served 36ONE and 4D normally again (the 0-byte files were temporary). The only "Not found"
  funds were the 7 M&G funds (port 8082, cloud only). The tracker showed "Otto1890 FR Flexible Income
  Fund" in place of Sasfin, as intended.

- **2026-10-19:** The tracker now shows a renamed fund's MDD name when the MDD prints the ISIN we hold.
  Of the 11 funds with `doc_names`, only Sasfin (→ Otto1890 FR Flexible Income Fund, ISIN ZAE000206397)
  qualifies today. Merchant West Worldwide Flexible, 10X, Amplify Active Equity and SIM have an ISIN on
  file, but their MDDs don't print it as text. Discovery DAO, Mi-Plan/Vunani, Momentum Capped, Merchant West
  Global Equity and Baillie Gifford LTGG print an ISIN, but none is on file. PPS Balanced Passive is set
  to `keep_name` (its MDD prints the old name).

- **2026-10-19, test run with the new checks** (cloud copy of the folder; 192 funds; MDDs for 185):
  - **Bug found and fixed:** a page with no link matching the fund's pattern fell back to any PDF on the
    page. On Prescient's other-funds page, Abax Absolute, Abax Balanced, Fairtree SA Equity and Steyn
    Equity were handed the *Prescient Sigma Select Global Leaders Feeder* MDD while September wasn't
    posted. The name check rejected all four (now in `_rejected/`). Fund-specific patterns no longer fall
    back.
  - Allan Gray's robots.txt disallows its M&G copies, so that backup was removed.
  - Fundrock (bcis.co.za) returned **0-byte** files for 36ONE BCI Equity, 36ONE Flexible Opportunity and
    4D Moderate FoF; refused by the 1 KB check. August was already saved; watch next week.
  - Manifest: 77 filed, 95 unchanged, 4 rejected, 0 reissued.

- **2026-10-19:**
  - Implemented the guide's checks:
    - the fund-name check (all 208 readable MDDs in the corpus pass);
    - masthead month detection, which agreed with the previous rule on all 213 MDDs and dates 161 of
      them from the masthead alone;
    - never-overwrite with reissue copies, `_manifest.csv`, `_rejected/` and the stale-copy rule;
    - Pending/Late/Quarterly statuses and the Exceptions sheet;
    - PDF reading in a worker with a time limit, and the `%PDF` check within the first KB.
  - Added the Ninety One A-class MDD backups.
  - The name check surfaced the Discovery DAO and Mi-Plan/Vunani name mismatches (§7).
- **2026-10-19:** Removed Aylett, Foord Flexible FoF and the two PSG Wealth funds (owner). Tracker renamed
  "!MDD Tracker"; Fund AUM, Inception Date and Benchmark columns added (MitonOptimal AUM column renamed).
- **2026-10-13 to 19:** Sources found for M&G, Janus Henderson, Otto1890, PPS, Amplify, Merchant West, Vulcan, 10X,
  Old Mutual RAFI, Curate, iShares (2), Ranmore and Schroders; skip-if-saved rule; tracker built from the
  sources file, not the AUM workbook.
