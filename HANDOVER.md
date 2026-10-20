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
| Fund list | `config/mdd_sources.yaml` (233 funds on 20 Oct 2026: 191, plus 42 added from Linka's folders, all with a source). **This file defines the tracker.** |
| AUM workbook | `AUM_By_Holding_Fund_Model_Portfolio.xlsx`, sheet "Holding Fund Totals". Only fills the "MitonOptimal AUM" column; it does not add or remove funds. |
| Excluded | `--exclude "^MitonOptimal FR"`: the owner sources the MitonOptimal FR funds directly. |
| Branch | `claude/fund-location-scraper-kvsmox` on GitHub `JDKMiton/Fund-Asset-Allocation---Scraper-and-Finder` (moved from the personal account JacDK777 on 20 Oct 2026) |
| Manual run | `Start-ScheduledTask -TaskName "Fund MDD weekly download"`, or `run_weekly.ps1 -OutFolder ... -FundsWorkbook ...` |
| Logs | `C:\Tools\MDD-Scraper\logs\weekly-YYYY-MM-DD.log` (last 12 kept) |

**What one run does** (`python -m fund_allocator collect`):
1. Works out the last two completed months (in October: August and September).
2. **Skips** a fund whose MDD is already saved for **every month due** (owner's rule, 13 Oct 2026; widened
   20 Oct 2026). An MDD already in the fund folder (`MDDs\YYYY\YYYY-MM - <Fund>.pdf`) counts: it is copied
   back to the month folder and the fund isn't searched. A quarterly fund only needs its quarter-end month
   (in an Aug/Sep run, September), so it isn't searched at all in a Jul/Aug run. The tracker is rebuilt
   from these files every run, so this is the same as "Collected" in the tracker.
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
   allocation stamp; and each run's start time and the funds it searched in `_runs.csv` (for the timing below).
6. **Copies every MDD to its fund folder** in Linka's share (owner, 20 Oct 2026):
   `<share>\<fund_manager>\<fund_folder>\MDDs\YYYY\YYYY-MM - <Fund>.pdf`, where Fund is the tracker name
   (`current_name`, else `name`). It goes over **all** month folders each run, so earlier months are
   back-filled. Never overwrites (a different file is kept beside it as `(reissued YYYY-MM-DD)`); never
   creates a fund folder (a missing one is the exception "Fund folder missing"; a failed copy is "Fund
   folder copy failed" and doesn't stop the run). Set by `--fund-share`; `run_weekly.ps1` passes Linka's
   share by default (`-FundShare`) and skips it if the share isn't there. The month-folder copies stay:
   the skip rule, reissue check, `_rejected` and the asset-allocation agent use them.
7. Rewrites `!MDD Tracker YYYY - MM.xlsx` in each month folder (they stay in `#Webscraper MDDs`).

**The tracker** has three sheets:
- **Tracker**, funds A–Z, with columns: Fund | Fund Manager | MitonOptimal AUM | ISIN | Fund AUM | Inception Date |
  Benchmark | Status | MDD month | Collected on | Usually available | Other months collected | File | Fund folder
  copy | Source | Notes.
  **Collected on** is the day the MDD was first collected (the manifest's first "filed" row; for MDDs from
  before the manifest, the saved file's date). **Usually available** is the fund's average number of days
  after month-end, learned (owner, 20 Oct 2026): a month counts only if an earlier run searched for the fund
  after month-end and didn't find it, so first-run back-fills don't count. It is accurate to about a week
  (the run is weekly) and fills in over the coming months.
  "Fund folder copy" is where this month's MDD was copied, relative to Linka's share (or why it wasn't).
- **Summary**, the counts per status.
- **Exceptions**, one line per problem.

Statuses:

| Status | Meaning |
|---|---|
| Collected | the MDD for this month is in the folder |
| Pending | not posted yet; still within the normal delay: the fund's learned average plus 7 days once 2 months are learned, otherwise `lag_days` (default 30) |
| Late | past the normal delay and still missing: look at it |
| Quarterly | `frequency: quarterly` fund; no MDD is due for this month |
| No source | the fund has no download source configured |

Exception kinds: Wrong document, Stale copy, Reissued, PDF unreadable, Date unreadable, Not found, Fund folder
copy failed, Fund folder missing, Late,
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
| 20 Oct 2026 | Fund-folder MDDs are named `YYYY-MM - <Fund>.pdf` (date first, so they sort). An MDD already in the fund folder means the fund isn't searched again for that month. |
| 20 Oct 2026 | Every run also saves each MDD in its fund folder: `MDDs\YYYY\YYYY-MM - <Fund>.pdf` (tracker name; all earlier months back-filled), and the tracker shows where. Month-folder copies and the trackers stay in `#Webscraper MDDs`. |
| 20 Oct 2026 | Removed Sprott Silver Miners & Physical Silver ETF (fact sheet site behind Cloudflare) from the tracker and weekly grab. Don't add it back unless asked. |
| 20 Oct 2026 | Keep a list of folder and name mismatches for the owner and Linka to fix, as a spreadsheet in `# TO DO LIST` in Linka's share (see §4). No "who" column. Rows marked Done are removed by the next weekly run (moved to its Done sheet); others stay. |
| 20 Oct 2026 | The tracker records when each MDD was collected, and learns per fund how long after month-end its MDD usually appears. |
| 20 Oct 2026 | Removed Sanlam Multi-Strategy (no public fact sheet) from the tracker and weekly grab. Don't add it back unless asked. |
| 20 Oct 2026 | Share classes for the funds added from Linka's folders: keep the A class for Fairtree FR Income Plus, Curate Global Quality and Global Value, Old Mutual Global Managed Alpha and RAFI (the rand feeders), and Nedgroup Rainmaker; Omba A USD Acc; Laurium Enhanced Growth the ZAR feeder; Peregrine Retail class A (buy list); Flagship FR Worldwide Flexible Feeder accepted as the IP Worldwide Flexible fund. From Linka's packs: Camissa SA Equity C class, Curate Global EM R Class USD (only the A sheets are published; same portfolio). |
| 20 Oct 2026 | Removed Riscura BCI China Equity Feeder (wound up 4 Sep 2026) from the tracker and weekly grab. Don't add it back unless asked. |
| 20 Oct 2026 | Removed SIM Inflation Plus (SCI Ninety One Cautious Managed) from the tracker and weekly grab; use Ninety One Cautious Managed instead. Don't add it back unless asked. |
| 19 Oct 2026 | Use Allan Gray's platform copies as a backup for M&G Balanced, Inflation Plus and Global Balanced, despite Allan Gray's robots.txt (`ignore_robots: true` on those three). |

## 4. Where things are

- `config/mdd_sources.yaml`: **the source registry**, one entry per fund. Fields:
  - `url` / `urls` (with templates `{yyyy} {mm} {yyyymm} {month} {Month} {mon} {Mon} {MON} {dd} {bdd} {next_yyyy} {next_mm}`);
  - `page` + `link_match` (the regex may contain the same templates) + `render`;
  - `sanlam_fund`, `mandg_fund`, `browser`, `referer`, `ignore_robots`;
  - `isin`, `note`, `doc_names`, `current_name`, `lag_days`, `frequency`, `keep_name`, `fund_manager`, `fund_folder`,
    `fund_path` (the fund folder relative to the share, only where it isn't under `fund_manager`: Curate
    Global Quality, under Lyrical).
- `fund_allocator/collector.py`: the run, checks, filing, manifest, tracker. `facts.py`: Fund AUM, inception
  and benchmark. `pdfinfo.py`: PDF reading in a worker process with a 120 s limit. `scraper.py`: downloads,
  browser and site APIs.
- **`# TO DO LIST\Folder and tracker fixes.xlsx`** in Linka's share: the mismatches between the folders,
  the tracker and the MDDs (and the buy list) for the owner and Linka to fix. **Append a row** whenever a
  scan or change finds a new one; never rewrite the workbook or their Status/Notes. Each weekly run moves
  rows marked Done to the workbook's **Done** sheet (`--todo-list`; `run_weekly.ps1 -TodoList`). Check the
  Done sheet for items that need the config to follow (renamed or moved folders, confirmed names). How:
  [`docs/fix-list.md`](docs/fix-list.md). The `# TO DO LIST` folder is not a manager.
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

Sources found on 20 Oct 2026 for the 45 funds added from Linka's folders:

- **Franklin Templeton (FTIF, I (acc) USD, ZA edition MDD):** `franklintempleton.co.za/download/en-za/factsheet/<document id>/Factsheet-<Fund>-I(acc)USD-<code>-J-FF-ZA-en-GB.PDF`.
  The document id stays the same month to month (seen Dec 2025 to Oct 2026), so a fixed `url` works. Links
  come from the public literature API `franklintempleton.co.za/api/literature/v1/documents?channel=en-za&docTypeCode=FF`.
  The browser site shows a terms gate; the download links don't. MDDs print "U.S." (doc_names).
- **iShares US ETFs (IGF, IYJ, SLV, ILIT):** `ishares.com/us/literature/fact-sheet/<ticker>-<name>-fund-fact-sheet-en-us.pdf`.
  **Quarterly**, dated US style "as of June 30, 2026"; the month reader now handles that form (it read
  IGF as 2007 and IYJ as 2000 before). The UCITS ETFs (INGB, Copper Miners, LITM) are monthly at
  `ishares.com/gls-download/literature/fact-sheet/<ticker>-<name>-fund-fact-sheet-en-gb.pdf`.
- **Old Mutual global feeders:** links on the rendered `/individual/funds/global-funds/` table. Global
  Managed Alpha is the rand feeder `bltc5262aa7fb355d6d`; RAFI All World is now **RAFI Select Global Index
  Feeder** `blt92b726bac5247d33`. Other blt links on those rows are holdings and risk/return reports.
- **Flagship:** moved from IP to Fundrock on 19 Sep 2025; now `Flagship FR …` on bcis.co.za. The Flexible
  Value masthead prints "3oSEPTEMBER2026" (a letter o); the month reader now accepts that.
- **Prescient other-funds page** also has Omba (quarterly Irish ICAV MDDs, `{yyyy}-q2-omba-…-mdd`), Artisan
  Global Value (`globalvalue-mdd-MMYY-vucits-zaf.pdf`; Pzena and T. Rowe Price "Global Value" sheets sit
  beside it), PPS Global Equity (Irish ICAV, A1), Laurium Enhanced Growth feeder (the MDD prints "Laurium
  Enh Growth") and Bateleur Market Neutral.
- **Camissa:** fund pages on camissa-am.com (rendered); `link_match: _\d{4}\.pdf` picks the monthly MDD.
- **Perspective:** quarterly only since Dec 2020, `perspectiveim.co.za/downloads/mdd/Perspective-<Balanced|Equity>-Fund-MDD-{yyyy}-{mm}.pdf`.
  A missing month answers 200 with HTML, so non-quarter months show "did not return a PDF".
- **Peregrine Capital:** left H4 on 7 Aug 2025; `peregrinecapital.co.za/factsheets` links Azure blob PDFs
  with a hash in the name that changes monthly (Retail and QI classes). Momentum and Discovery copies are the
  stale H4 ones.
- **RealFin (RCIS: CAEP, AIP):** stable `realfin.co.za/fund-files/mdd-files/MDD-<fund>.pdf`. AIP's text
  reads "PUBLISHED ON 9 OCTOBER 2026 SEPTEMBER 2026"; it dates correctly as September.
- **Novare CIS (Southern Cross Market Neutral):** stable `novarecis.co.za/docs/mdd/<fund>-MDD.pdf`, listed on
  `/third-party-funds/`. Southern Cross's own site is stale.
- **Curate global funds (Luxembourg MGF SICAV, A Class USD):** Momentum `…/factsheets/curate-global-<fund>-a-usd.pdf`
  (not the `curate-momentum-…-(a)-zaf` pattern).
- **Jupiter (UK funds):** permalink by ISIN on `dms-api.jupiteram.instinctcentral.io/documents/permalink?group.name=Factsheet&systemMetadata={"shareClassIds":["<ISIN>"]}…`
  redirects to the current fact sheet. It also serves Jupiter Merian World Equity (IE00B42HMS87), a
  possible backup for that fund.
- **Schroders QEP Global Core:** only C Acc and C Dis have fact sheets (`SISF-QEP-Global-Core-C-Acc-FMR-LUEN.pdf`).
- **UBS KeyInvest (Coherent CCMGCZ):** a JSE-listed UBS note, not a unit trust; the rendered product page
  links a monthly "AMC SALES FACTSHEET" (the link has no .pdf).
- **STANLIB Global Select:** only the Momentum copy of the rand feeder (B2), 2 to 3 months behind
  (`lag_days: 90`). `stanlib.literaturehub.co.za` has `Disallow: /`. stanlib.com itself answered plain
  requests on 20 Oct 2026 and its robots.txt allows all.
- **Removed for having no reachable source:** Sprott SLVR (sprott.com and sprottetfs.com
  behind a Cloudflare challenge; quarterly US sheet). Riscura BCI China Equity Feeder was wound up on 4 Sep
  2026 and removed from the tracker (§3). Sanlam Multi-Strategy (Irish UCITS, now Sanlam Ninety One Multi
  Strategy; not in Sanlam's API, Ninety One behind Cloudflare) was removed for having no public sheet (§3).

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
| Old Mutual RAFI All World Index Fund | Old Mutual RAFI Select Global Index Feeder Fund (not yet confirmed by the owner) |
| Fairtree Flexible Income Fund | Fairtree FR Income Plus Fund (ex Fairtree Flexible Income Plus Prescient, ex MET Income Plus) |
| Flagship IP Flexible Value / Worldwide Flexible / Worldwide Flexible FoF | Flagship FR Flexible Value Fund / FR Worldwide Flexible Feeder Fund / FR Worldwide Flexible Fund of Funds |

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

**Names follow Linka Henning's folders (owner, 20 Oct 2026).** `fund_manager` uses the folder names in
`E:\OneDrive - MitonOptimal Portfolio Management (Pty) Ltd\Linka Henning's files - Asset Management (FRA-DD Documents)`
exactly, so MDDs can be filed by name: e.g. "Coronation", "M & G", "Terebinth (Amplify)", "36One Asset
Management". Don't rename Linka's folders; change the config. Owner's filing decisions (20 Oct 2026):

| Funds | Fund Manager |
|---|---|
| Nedgroup Core Guarded, Core Diversified, Core Accelerated, Core Global Feeder | Nedgroup |
| Nedgroup Global Equity | Veritas Asset Management (a Veritas folder is needed) |
| All 6 STANLIB funds, incl. STANLIB Global Balanced Feeder (not J.P. Morgan) | Stanlib |
| PPS Managed / PPS Balanced Passive | 36One Asset Management / Prescient (the single underlying manager) |
| PPS Equity, PPS Flexible Income (several managers) | PPS |
| Jupiter Merian World Equity, Old Mutual Global Equity [Jupiter Merlin] | Jupiter Merian Fund Management |
| Mi-Plan IP Global Macro, Multi Asset IP Balanced Defensive | Mi-Plan |
| Mi-Plan IP Enhanced Income (Vunani FR) | Vunani Fund Managers (no folder yet) |
| Curate Flexible Property / Curate Enhanced Yield | Sesfikile / Momentum Fixed Income (underlying managers; not Lyrical) |
| Old Mutual RAFI 40 | Old Mutual Wealth - OMI |
| Catalyst SCI Global Real Estate | Catalyst Fund Managers (Linka's "Catalyx Capital" is a different firm) |

| Foord funds incl. Nedgroup Stable [Foord] | Foord (folder created by the owner) |
| Orbis funds incl. the 2 Allan Gray Orbis feeders | Orbis Investment Management (folder created by the owner) |
| Amplify boutiques | AG Capital, Acumen Capital, Marble Rock Asset Management, Oyster Catcher Investments (empty folders created by Claude) |
| Momentum Capped SWIX, Curate Enhanced Yield | Momentum (folder created by Claude) |
| Discovery Aggressive DAO FoF (Cogence) | Cogence (folder created by Claude) |
| Nedgroup Rainmaker (owner, 20 Oct 2026) | Ninety One, the investment manager named on the MDD (Quality team): same rule as Nedgroup Stable to Foord. Claude created `Ninety One\Nedgroup Rainmaker Fund\MDDs`. Linka's `Nedgroup\Nedgroup Rainmaker Fund` (empty DD and MDDs folders) is left as it is: two folders for one fund, like Nedgroup Global Equity. |
| CAEP RCIS Fixed Income RHF (owner, 20 Oct 2026) | Cartesian: Cartesian Capital (Anthea Gardner) runs it under CAEP Asset Managers' Category IIA licence, so the MDD names CAEP. |
| Curate Global Quality Equity (owner, 20 Oct 2026) | Evenlode, the adviser named on the fact sheet (empty folder created by Claude). **Exception:** its fund folder stays under Lyrical Asset Management (Curate-Momentum), with Linka's DD pack. |

The other 16 managers got empty folders named exactly as in the config (created by Claude at the
owner's request). **Every fund's Fund Manager now matches a folder (192 of 192).** When a fund is
added or changes manager, use an existing folder name, or create the folder with the same name.

### Fund folders (owner's request, 20 Oct 2026)

Inside each manager folder there is one folder per fund (holding Linka's **FRA** and **DD** packs) and
usually a "General - Fund Manager Info" folder. `fund_folder` in the config names the fund's folder inside
`<fund_manager>`; **all 191 funds have one, and every one exists.** 69 matched folders Linka already had
(often under a shorter name, e.g. "Nedgroup Core Guarded Fund", "Truffle Flexible Fund" for PR Truffle,
"Otto1890 BCI Flexible Fund" for Sasfin); the owner renamed two to match ("Marriott Core Income", "M&G
Global Inflation Plus Feeder Fund"). Claude created the other 122 as empty folders named after the fund
(the tracker's `current_name` where set; "Baille" and "Marriot" typos corrected). Not the same fund, so
kept apart: Jupiter Merian World Equity vs. "Jupiter Merian Global Equity Fund", PPS Equity vs. "PPS
Global Equity Fund", Ranmore Global Equity vs. the BCI Ranmore feeder. **On 20 Oct 2026 an empty `MDDs` folder was
created in each of the 191 fund folders** (owner's request). Since 20 Oct 2026 every run copies the MDDs
into it, one folder per year (§2, step 6).

**Fund folders in Linka's share that were not in the tracker** (71 on 20 Oct 2026). The owner went
through them one by one:
- **Added (45)**, each with `fund_folder` and an `MDDs` folder. Sources were found on 20 Oct 2026 for 42
  (§5); Sprott SLVR and Sanlam Multi-Strategy (no reachable sheet) and Riscura China (wound up) were
  removed (§3): Templeton Emerging Markets, Templeton EM Smaller
  Companies, Franklin Technology, Franklin US Opportunities; iShares Global Infrastructure, US Industrials,
  India Govt Bond, Silver Trust, Copper Miners, Lithium Miners and Producers, Lithium and Battery Producers;
  Old Mutual Global Managed Alpha, Old Mutual RAFI All World Index; Sanlam Multi-Strategy; Flagship IP
  Flexible Value, Worldwide Flexible, Worldwide Flexible FoF; Omba Global Equity, Global Thematic; Camissa
  Protector, Camissa SA Equity; CAEP RCIS Fixed Income RHF; Curate Global Quality Equity, Global Value
  Equity, Global EM Equity; Nedgroup Rainmaker; Peregrine High Growth, Pure Hedge; Perspective Balanced,
  Executive Equity; Coherent Capital Global Commodity; AIP RCIS Multi-Strategy; Artisan Global Value;
  Bateleur Market Neutral; Coronation Active Income Plus; Fairtree Flexible Income; Jupiter Merian Global
  Equity; Laurium Enhanced Growth; PPS Global Equity; Portfoliometrix FR Income; Riscura BCI China Equity
  Feeder; Schroder ISF QEP Global Core; Southern Cross Market Neutral; Sprott Silver Miners & Physical
  Silver ETF; STANLIB Global Select. None is in the AUM workbook.
- **Waiting:** "MitonOptimal BCI Interest Plus Fund" (Cartesian folder), which looks like the AUM workbook's
  "MitonOptimal FR Interest Plus Fund", a MitonOptimal FR fund the owner sources directly (§3).
- **Left out (24):** Templeton BRIC; Franklin India, Biotechnology Discovery, Alternative Strategies,
  Flexible Alpha Bond, EM Corporate Debt; FTGT Brandywine Global Income Optimiser; BGF World Real Estate;
  the two Old Mutual private equity funds; Sanlam AI Global Managed Risk, Global High Quality, Real Assets;
  Causeway Defined Growth, Defined Return; Levendi Thornbridge Defined Return; Omba Moderate Risk Global
  Allocation; UBS Solactive China Technology ETF; Denker UBS DNKOPP 30Nov27; Invesco S&P MidCap Momentum
  ETF; SPDR S&P Pan Asia Dividend Aristocrats; MO BCI Worldwide Growth, MO FR Active Beta, MO FR Worldwide
  Active Beta.
- **Duplicates:** Linka's "Nedgroup \ Nedgroup Global Equity Fund" is the tracker's Nedgroup Global Equity,
  which the owner filed under Veritas; and "Nedgroup \ Nedgroup Rainmaker Fund" (empty), now filed under
  Ninety One (two folders for one fund each; not resolved).

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
- **Folder and name mismatches** for the owner and Linka: `# TO DO LIST\Folder and tracker fixes.xlsx` (§4).
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

- **2026-10-20, collection dates and timing; to-do clean-up** (owner): tracker columns Collected on and
  Usually available, new `_runs.csv`; Pending/Late use a fund's learned timing once 2 months are known.
  Copies to and from the fund folders keep the file's date. The to-do workbook lost its Who column
  (regenerated; nobody had edited it), and the weekly run moves Done rows to its Done sheet. On the real
  data, Collected on starts from the manifest (from 20 Oct 2026); Usually available is empty until next
  month's runs. Tests pass (42).

- **2026-10-20, fund-folder names, skip rule, to-do spreadsheet** (owner): fund-folder MDDs renamed to
  `YYYY-MM - <Fund>.pdf` (nothing had been written to the share yet, so nothing to rename). An MDD already
  in the fund folder now counts as downloaded; quarterly funds are only searched for quarter-end months.
  The fix list became `# TO DO LIST\Folder and tracker fixes.xlsx` (52 items, incl. 14 tracker names to
  confirm, one a typo: "Baille Gifford"). Tests pass (39).

- **2026-10-20, MDDs copied to the fund folders** (owner): new step 6 (§2), `--fund-share`, tracker column
  "Fund folder copy", config field `fund_path` (Curate Global Quality). Rehearsed on copies of `#Webscraper
  MDDs` and a folders-only mirror of Linka's share: 350 MDDs (Jun to Sep 2026) filed into 231 funds'
  `MDDs\YYYY` folders, no fund folder missing, every collected row shows its path. Not copied: 5 old files
  of removed funds (Aylett, SIM, Foord FoF, two PSG Wealth). The real share is first written by the next
  weekly run. About 40 worst-case paths (reissued copies) pass 260 characters; long paths are enabled on
  the PC and OneDrive allows 400.

- **2026-10-20, Sprott removed; fix list started** (owner): Sprott SLVR out of the config (233 funds, all
  with a source). Compared every `fund_manager\fund_folder` with Linka's share: all exist except Curate
  Global Quality (under Lyrical by choice). Mismatches found (duplicates, typos, old BCI/IP names, folders
  of removed funds, out-of-date buy list names) are in `docs/fix-list.md`.

- **2026-10-20, Nedgroup Rainmaker to Ninety One** (owner): the manager named on the MDD, same rule as the
  other Nedgroup third-party funds. Created `Ninety One\Nedgroup Rainmaker Fund\MDDs`; Linka's empty Nedgroup
  folder for it left in place (§6). The three Fund Manager questions from the added funds are settled.

- **2026-10-20, CAEP stays under Cartesian** (owner): Cartesian's DD pack (12 Oct 2026) shows the fund is
  Cartesian Capital's, run under CAEP Asset Managers' licence. Note added to the config; no change to the run.

- **2026-10-20, Curate Global Quality → Evenlode** (owner): `fund_manager` set to Evenlode, the adviser on
  the fact sheet; empty Evenlode folder created in Linka's share. The fund folder stays under Lyrical (§6).

- **2026-10-20, share classes for the added funds** (owner, one by one; §3). Evidence used: the buy list
  (`!MitonOptimal Buy Lists\MitonOptimal Buy List MASTER.xlsx`: Peregrine class A on every platform;
  Fairtree B1/A1/B2 by platform) and Linka's packs (Camissa SA Equity C class ZAE000313128; Curate Global
  EM R Class USD LU2377870212). Only A class sheets are published for those, so the ISIN shown is the
  class held and the note says so. Sanlam Multi-Strategy removed (owner). 234 funds in the config.

- **2026-10-20, Riscura China removed** (owner): the feeder was wound up on 4 Sep 2026, so it is out of the
  config (235 funds). Its folder in Linka's share is left as it is. No scraping change.

- **2026-10-20, sources for the 45 added funds:** 42 now have a source (§5), each tested with `collect`
  into a scratch folder: 41 MDDs filed (Jun to Sep 2026), every one passing the name and month checks; the
  two Perspective funds are quarterly and their September sheet isn't up yet (June verified). No source:
  Sanlam Multi-Strategy, Sprott SLVR (Cloudflare), Riscura China (wound up). Month reader fixes, with
  tests, also copied to the skill: US dates "June 30, 2026" (iShares US) and "3oSEPTEMBER2026" (Flagship).
  US iShares and Perspective and Omba are `frequency: quarterly`. Owner questions in §7.

- **2026-10-20, 45 funds added to the tracker** from Linka's folders (owner's choices, §6). They have no
  download source yet (status No source); finding one per fund is the next job. 236 funds in the config.

- **2026-10-20, MDDs folders:** created an empty `MDDs` folder in each of the 191 fund folders. Listed the
  71 fund folders in Linka's share that aren't in the tracker (§6). Found: Linka has a "Nedgroup Global
  Equity Fund" folder under Nedgroup, while the owner filed that fund under Veritas earlier today.

- **2026-10-20, fund folders:** each tracker fund matched to its fund folder in Linka's share (§6, Fund
  folders); new config field `fund_folder` (also copied to the skill). The owner reviewed the doubtful
  ones one by one and removed SIM Inflation Plus (§3). 69 existing folders, 122 created empty. Tests pass.

- **2026-10-20, all managers have a folder:** created 16 more empty folders (10X Investments, 4D Wealth
  Management, Baillie Gifford, Catalyst Fund Managers, First Pacific Advisors (FPA), Ginsglobal Index
  Funds, Janus Henderson Investors, Merchant West Investments, Northstar Asset Management, Obsidian
  Capital, Pyrford International, Sygnia Asset Management, Veritas Asset Management, Visio Fund
  Management, Vulcan Value Partners, Vunani Fund Managers). All 192 funds now match a folder.

- **2026-10-20, more manager folders:** the owner created Orbis Investment Management and Foord;
  at the owner's request Claude created empty folders AG Capital, Acumen Capital, Marble Rock Asset
  Management, Oyster Catcher Investments, Momentum and Cogence in Linka's Asset Management folder.
  SIM Inflation Plus set to Ninety One. 45 managers / 173 funds now match; 16 / 19 still need folders.

- **2026-10-20, Fund Manager mismatches decided** (owner, one by one; table in §6). Also corrected:
  the first pass had missed that "STANLIB Asset Management" (5 funds) matches the Stanlib folder; now
  "Stanlib". BlackRock needed no change once Nedgroup Core Global moved to Nedgroup. 37 managers / 155
  funds now match a folder; 26 managers / 37 funds have none.

- **2026-10-20, Fund Manager names set to the folder names:** the owner approved matching the 29 managers
  that have a folder. 88 `fund_manager` values changed in 23 names (e.g. Coronation Asset Management →
  Coronation, M&G Investments → M & G, Terebinth Capital → Terebinth (Amplify)); Allan Gray, Denker
  Capital, Laurium Capital, Rezco Asset Management, Schroders and Steyn Capital Management already matched.
  Variants with extra text (e.g. "Prescient Investment Management (via PPS Multi-Managers)", "Sesfikile
  Capital (for Curate Investments)") were left for the owner's PPS and Curate decisions.

- **2026-10-20, full run on the PC after the move:** started from Task Scheduler; the pull from JDKMiton
  worked ("Already up to date"). The first run stopped while writing the trackers: `!MDD Tracker 2026 -
  09.xlsx` was open in Excel (PermissionError), so September's tracker was not rewritten. **Task Scheduler
  still showed result 0**, because `run_weekly.ps1` doesn't pass on Python's exit code; only the log's
  "finished with exit code 1" shows the failure. Rerun with the file closed: exit code 0, all four trackers
  rewritten. New: Fairtree Silver Oak and Momentum Capped SWIX for September. August 181 of 192 collected
  (Baillie Gifford Managed Late; 7 STANLIB/SIM/10X Pending; 3 Marriott Quarterly). September 117 collected,
  75 Pending (still within the 30-day delay). Open: keep trackers closed at 07:00 on Mondays, or make the
  tracker write survive a locked file and the task report failures (offered to the owner).
- **2026-10-20, Fund Manager names vs. Linka Henning's "Asset Management (FRA-DD Documents)" folders:**
  the owner wants the tracker's Fund Manager column to match those folder names. 29 folders match a
  tracker manager (mostly the folders use a short name, e.g. "Coronation" for "Coronation Asset
  Management"). Mismatches waiting for the owner: Nedgroup Core funds and Global Equity (folder: Nedgroup;
  tracker: Taquanta/BlackRock, Veritas), STANLIB Global Balanced (folder: Stanlib; tracker: J.P. Morgan),
  the 4 PPS funds, Jupiter and BlackRock spelled two ways, Mi-Plan (Think Cell, Vunani), Curate (folder
  says Lyrical), Old Mutual (folder "Old Mutual Wealth - OMI"), Catalyx folder is not Catalyst. 27 tracker
  managers have no folder (Orbis, Foord, Oyster Catcher and others). Nothing changed yet; renaming
  Linka's folders was advised against.

- **2026-10-20, repository moved:** transferred from the personal GitHub account JacDK777 to the work
  account JDKMiton, now `JDKMiton/Fund-Asset-Allocation---Scraper-and-Finder` (§2). The PC's clone at
  `C:\Tools\MDD-Scraper` has `origin` pointing at JDKMiton, and `git pull` works there, so the weekly
  self-update keeps working. No scraping change.

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
