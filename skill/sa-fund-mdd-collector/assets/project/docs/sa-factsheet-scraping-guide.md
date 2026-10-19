# Scraping South African fund factsheets for monthly asset allocation

A field guide for an AI coding assistant. It comes from about two months of building and running a pipeline
that downloads factsheets (MDDs, "minimum disclosure documents") for SA unit trusts each month, from manager
websites, platforms, Morningstar and the Internet Archive, and parses the asset-allocation table out of each
one. That pipeline holds close to 3,000 factsheets, each filed under a month read from its own text. Almost
every rule below exists because something went wrong without it.

The job this guide is for: **each month, fetch the LATEST factsheet for every fund in a set of model portfolios
and extract its asset allocation, reliably.** History is out of scope, except where an archive is the easiest
route to the latest sheet.

Site details were checked between August and October 2026. Websites change. Treat the URL patterns in section 9
as starting points to verify, and the rules in sections 1 to 8 as the durable part.

**For the person using this file:** give it to your assistant at the start of the work. For a coding agent
(Claude Code, Cursor, Codex, Copilot), save it in the project folder and point to it from the project's
`CLAUDE.md` or `AGENTS.md`, so the agent reads it every session. In a chat app, attach it at the start of the
conversation or add it to the project's knowledge files. Then give the assistant your fund list: fund name,
manager, share class, and JSE code or ISIN if you have them.

---

## 0. How the assistant should work

1. **Build a source registry first** (section 5): one row per fund, saying where its latest sheet comes from
   and how it is checked. Agree it with the user before writing the monthly job.
2. **Never fall back silently.** If a fund's usual route returns nothing, or a document that fails a check,
   report it as an exception. Never substitute an older file, a different share class or a cached copy
   without saying so. A wrong month that looks normal is worse than a visible gap.
3. **When a site blocks automation** (CAPTCHA, bot wall, login, a firewall challenge), do not try to defeat it.
   Use another route from section 9, or ask the user to download that sheet by hand and drop it in a folder
   the job reads.
4. **When a date or value is disputed, look at the page.** Render page 1 as an image and read it. Several
   "errors" a regex flagged were the regex being wrong (section 3).
5. **Keep everything you fetch** (section 7). The archive is how you diagnose next month's surprise.

---

## 1. The ten rules

Each rule has a real case behind it.

**R1. A 200 response is not a PDF. Check the bytes.**
Content management systems often answer a missing file with an HTML "not found" page and status 200
(Coronation's old paths, BCI, STANLIB and Sygnia's upload folders all did). Accept a file only if it is at
least about 1 KB and starts with `%PDF-`. Some old archived files wrap the PDF in a multipart envelope with
`%PDF` about 200 bytes in, so search the first KB and cut from there.

**R2. The right URL can serve the wrong fund. The document must name itself.**
Check that the PDF text contains the fund's name **and** the manager's name. Real cases:
- Momentum Wealth's URL for SIM Inflation Plus served *SIM Inflation Linked Income*.
- Momentum's "Defensive Growth" slug served a different fund with a similar name.
- The Allan Gray platform served the Kagiso *Balanced* fund's sheet under the Kagiso *Stable* fund's URL.
- Short names over-match. "absolute fund", "real income" and "inflation plus" each match several managers'
  funds. Namibian sister funds also share names with SA funds.

**R3. The month comes from the document, never from the fetch date, the URL, `Last-Modified` or a folder name.**
Stale serves are common, and every one of them answered 200 with a valid PDF:

| Host | What it served |
|---|---|
| Absa's own "current" file | the February 2020 sheet, in 2026 |
| Momentum Wealth, for funds that left the platform | each fund's last sheet, frozen (2021–2023) |
| Glacier and other platform stores, for delisted share classes | frozen |
| Discovery's download web service | the previous month, on record |
| M&G's old factsheet link | the April 2025 sheet, in October 2026 (section 2) |
| Nedgroup's dated folder for a month never published | a later month's sheet |

Folder dates mislead too. A file in a folder dated `20210131` was the December 2020 sheet, because the folder
date was the posting date.

**R4. Read the right date on the sheet.**
A factsheet carries many dates: the month it reports on, quarterly holdings stamps, the issue or print date,
the fund's inception date, performance-table dates, ESG-panel dates, fee-period dates, and bond maturity dates
in the holdings list. Section 3 has the rule that works and tested code. Also record the
**asset-allocation table's own stamp** separately ("Asset allocation as at 31 Aug 2026"). Some managers print
a quarter-end allocation on every sheet in that quarter, so a stamp older than the sheet's month is normal.

**R5. Do not hard-code the PDF link when the site changes it.**
Many sites give each upload a new link, and the old link keeps serving the old file. Look the link up on the
fund page every month (section 4). If the page has no link, fail loudly. Do not reuse last month's link.

**R6. Pick the right document type.**
A fund page usually offers several PDFs: the factsheet/MDD, a quarterly investor report, a quarterly
commentary, a brochure, sometimes a "comprehensive" and a short sheet, or a holdings report. They can have
near-identical file names. Select by the site's own label or type field, then confirm from the text: the
masthead says "Fact Sheet", "Minimum Disclosure Document" or "MDD", and the document has an allocation table.

**R7. Know the posting lag. "Not posted yet" is not "failed".**
Most managers post a sheet 1–3 weeks after month-end. Some copies take 4–5 weeks: M&G on the Allan Gray
platform, and Sanlam and Abax on Morningstar. Run the job after about the 20th, and on every run retry the
last three months. Mark a fund whose new month is not up yet as `pending`, not as an error, and escalate only
past its normal lag.

**R8. Read tables by word position, not by lines of text.**
Factsheets are multi-column layouts. Plain text extraction interleaves columns and moves numbers away from
their labels. On M&G's current sheet, layout-mode text puts "SA Bonds (ex. ILBs) 12.5%" on one line. The
true value is 30.0%: the numbers print two rows above their labels. Use word coordinates (section 6).

**R9. Check every extraction before using it.**
Run these checks (section 7):
- the lines sum to about 100;
- every label is known;
- the month-on-month change is plausible;
- the file is not byte-identical to last month's;
- share classes agree.

Warn on near misses, stop on structural failures, and never quietly rescale a sheet to 100.

**R10. Keep evidence and never overwrite.**
For every file you fetch, record the source URL, the time, a SHA-256 hash, the sheet month, the allocation
stamp and the result. Never overwrite a filed month: if the same month arrives with different bytes, keep both
and flag it, because managers do reissue sheets. Move rejected files to a `_rejected/` folder instead of
deleting them. That is how the wrong-fund Momentum serve was diagnosed.

**And be a polite client.** Allow 1–2 seconds between requests to one host, honour `robots.txt` and the
site's terms, and download each file once. Do not defeat CAPTCHAs, bot walls or login walls. Never use an API
key or client id that belongs to someone else, even if it appears in public search results.

---

## 2. Worked example: "M&G gives me an old factsheet"

We reproduced this on 13 October 2026.

**How the M&G site works now**
- Fund pages live at `https://www.mandg.co.za/all-funds/<fund-slug>`, for example
  `/all-funds/mg-inflation-plus-fund`. Every slug is listed in `https://www.mandg.co.za/sitemap.xml`.
- The site is a Next.js app. **The page's HTML has no `<a href="...pdf">` links at all.** The document links
  sit inside the page's embedded data, in `<script>self.__next_f.push([...])</script>` chunks with the quotes
  escaped as `\"`.
- The links form a list called `fundDownloadItems`. On 13 October it held:

  | type | label | link | what it was |
  |---|---|---|---|
  | `Fact Sheet` | Fact Sheet | `https://mandg.co.za:8082/media/nxrnijcf/mandg-inflation-plus-fund.pdf` | **August 2026** sheet, uploaded 14 Sep 2026 |
  | `Commentary` | Quarterly Commentary | `.../media/twdlq2yl/mandg-inflation-plus-fund-commentary.pdf` | quarterly |
  | `Investor Report` | Quarterly Investor Report | `.../media/czbd1qka/mandg-inflation-plus-fund-general-investor-report.pdf` | **June 2026** report |
  | `null` | Fund brochure | `.../media/apxbohlf/mg-inflation-plus-fund.pdf` | marketing brochure (Oct 2025) |

- Documents are served from **`mandg.co.za:8082`**, a non-standard port. Corporate firewalls and proxies
  sometimes block such ports, so that is worth checking if fetches fail on an office network.
- The 8-character media key changes whenever M&G uploads a new file. **Old keys keep working.** The older
  link `https://mandg.co.za:8082/media/34294/mandg-inflation-plus-fund.pdf` still answers 200 with a valid
  PDF: the **April 2025** sheet, last modified 23 June 2025.

**Three ways to land on a June document, which is "three months ago" in mid-October:**
1. **Taking the wrong link.** The quarterly investor report is the June 2026 document. A scraper that picks
   the first PDF, or matches a file-name keyword, can take it.
2. **Reading the wrong date.** Page 1 of the August sheet has the masthead "August 2026" and
   "Asset allocation as at 31 Aug 2026". It also has "**Top 10 holdings as at 30 Jun 2026**", a quarterly
   stamp. A regex for the first "as at …" date reads the August sheet as June.
3. **Using a stale link.** A hard-coded or remembered link, or one taken from a search engine, keeps serving
   whatever file it pointed to. The `34294` link gives April 2025.

Also, on 13 October the September sheet was not up yet: the August sheet was posted 14 September. So
"latest" in mid-October means August. That is R7.

**The fix, as tested code in section 10:** fetch the fund page, unescape `\"`, find `fundDownloadItems`, take
the item whose `type` is `Fact Sheet`, download it, then check four things:
- the bytes are a PDF;
- the text names "M&G Inflation Plus Fund";
- the sheet month is read from the masthead;
- the allocation stamp agrees.

Then read the legend by coordinates. It gives SA Bonds (ex. ILBs) 30.0, SA Equity 26.4, SA ILBs 12.5,
Foreign Bonds 10.8, Foreign Equity 10.3, SA Cash 5.6, SA Listed Property 3.9 and Foreign Cash 0.3, summing
to 99.8.

**A second, dated route for M&G Inflation Plus:** the Allan Gray platform's document store keeps a dated
monthly archive for the fund's Class B: folder `Prudential Inflation Plus Fund (Class B)`, code `PRCB`
(section 9). It runs about 4–5 weeks after month-end.

---

## 3. Reading the month a sheet is for

**The rule that works.** It came out of filing close to 3,000 sheets, with every disputed date settled by
looking at the page.
1. Collect every date on the first two pages, in four forms: `31 August 2026`, `August 2026`, `31/08/2026`
   (SA order is day/month/year) and `2026-08-31`. Allow a footnote digit glued to a spelled-out year: Allan
   Gray prints "asset allocation on 30 june 2024⁷", which extracts as `20247`.
2. Drop any date after today. A sheet cannot report a month that has not ended.
3. Drop dates whose preceding ~30 characters say *issue date, date of issue, issued, published, print date,
   printed, generated, revision, version, updated on, launch, inception, MSCI, ESG, period:, expense ratio*
   or *payment date*. Sheets are issued 2–3 weeks after the month they report, so a rule that takes "the
   latest cued date" files every sheet one month too late. ESG panels stamp their own "as of" date,
   fee-disclosure periods end on a month-end right where an as-at date would sit, and distribution tables
   list payment dates.
4. **Masthead first.** Take the words printed in the **top 15% of page 1**, by position, read top to bottom.
   If they hold a month-end date ("31 August 2026") or a bare month ("August 2026"), that is the sheet's
   month. This is how a person reads a factsheet, and it is the only rule that survives a stale document.
   - Define the masthead by **position, not by "the first N characters of the text"**. A PDF's text order is
     its drawing order, which often starts with a side panel. On Camissa sheets that is the Top-10 list; on
     Ninety One sheets it is the income-distribution dates. In our test the character-count version misdated
     26 of 40 Camissa sheets.
   - Use individual **words**, not text blocks. A block can start near the top and run down the page, and
     splitting blocks separates a date from the words that disqualify it ("produced by MSCI ESG research as
     of" | "31/12/2021").
   - Ignore a **mid-month** date in the masthead ("1 July 2000"). In two-column mastheads that is an
     inception or issue date whose label sits in the other column.
5. Otherwise take the **most recent month-end date** (day = last day of its month). "17 March" is somebody's
   diary; month-ends are reporting dates. Bond maturity dates in a holdings list are month-ends too, which is
   why step 2 matters. Without it, a 2010 sheet read as 2022.
6. Otherwise take the latest date preceded by "as at" or a similar cue, otherwise any date.

**Separately, read the allocation table's own stamp:** "asset allocation as at …" or "asset allocation on …".
Store both values:
- **file the sheet under its sheet month;**
- **label the data with its allocation stamp.**

A stamp one or two months older than the sheet month is normal for Ashburton, whose allocation is a
quarter-end figure carried within the quarter. It is not a stale document.

**Known exceptions:**
- Some sheets print no "as at" at all. CAM/H4 is one: the only "as of" on it is the ESG panel's, so date it
  from performance-table dates or from the source's own dating.
- Camissa sheets have had typos in their mastheads ("Jannuary", "Decmber", "Febuary").
- Allan Gray once printed "Asset allocation on 28 February" with no year.
- Scanned sheets have no text, so date them by eye.

**Our track record with this rule:**
- A naive "as at DD Month YYYY" check once disagreed with it on 37 files. **Every one of those disagreements
  was a quarterly holdings stamp**, so the rule was right each time. Two correct filings were undone on the
  regex's say-so and had to be restored after looking at the page images.
- The Python code in section 10 dated **906 of 908** sheets to the right month (99.8%). The sheets came
  from 28 fund series and about 20 managers, mostly from 2015–2026 with a few back to
  2006. For each sheet, only dates up to two months after its month counted, to mimic fetching it as the
  latest sheet.
  - The two misses: a CAM/H4 sheet whose only masthead date is the ESG panel's, and a 2007 fund-launch
    sheet that prints no month-end date.
  - The same test using "first 260 characters" as the masthead scored 868 of 908.

---

## 4. Finding where a site keeps its latest factsheet

Work down this list for each manager. Stop at the first step that gives a stable, checkable route.

1. **Sitemap and robots.txt.** `https://<site>/sitemap.xml` usually lists every fund page (M&G's does).
2. **The fund page's HTML.** Fetch it and search for `.pdf`, `fact`, `mdd` and `minimum disclosure`. If real
   links are there, select by the link's label (R6).
3. **Embedded page data.** Modern sites (Next.js, Nuxt, Gatsby) build links in the browser from data embedded
   in the page. Look in `<script id="__NEXT_DATA__">` (JSON), `self.__next_f.push(...)` chunks (escaped JSON),
   or `window.__NUXT__`. Unescape the text and search it for PDF paths and field names like `type` or `label`.
4. **The site's own data API.** Open the fund page in a browser with developer tools. On the **Network** tab,
   filter to Fetch/XHR, click the factsheet button, and see which request returns the link. It is often a
   JSON API listing documents per fund. For example, Sanlam's fund pages call a public JSON endpoint whose
   `mdd_urls` field holds the current sheets. Call that endpoint directly.
5. **Gates and cookies.** Some sites need a region or investor-type choice first. Coronation redirects to
   an error page without that cookie. Either send the cookie the site sets, or drive a headless browser
   (Playwright) to click through and collect the links.
6. **A listing page with unguessable links.** Ashburton's document links contain a GUID, so scrape the
   listing page each month and match the file names.
7. **Redirect endpoints.** Some sites have a stable "latest" URL that redirects to the current file (Satrix:
   `/fund/mdd/<CODE>` redirects to `/media/<id>`). That is fine, as long as you still date the content.
8. **Dated URL templates.** Where a manager files sheets under dated paths, build the URL for the target
   month and try a few variants in order (section 5). Watch for an upload-month folder that differs from the
   sheet month (Abax, CAM).
9. **Second sources** (section 9), when the manager's own site fails:
   - the **Allan Gray platform** store (dated and monthly, for funds on that platform, in AG's share class);
   - other platform stores keyed by JSE code (Momentum, Glacier, EasyEquities, PPS, Discovery), which are
     current or frozen, so always date the content;
   - Morningstar's document library, if your firm licenses it.
10. **Ask the manager.** Client services routinely email factsheets on request. For a fund you cannot reach
    any other way, that is the cheapest route.

**Share classes.** The asset allocation is a property of the portfolio and is identical across share
classes; only fees and performance differ. If your class's sheet is unavailable, another class's sheet
for the same month gives the same allocation. Record which class you used. Comparing two classes of the same
fund over more than 100 overlapping months, we found 0.00 percentage-point differences.

**Names change.** Prudential became M&G, Kagiso became Camissa, H4 became CAM, and Investec Asset Management
became Ninety One. Platform folders often keep the old name: Allan Gray's folders still say "Prudential" and
"Kagiso". Write name checks that accept both the old and new names where a source lags, but always require the
manager.

---

## 5. The source registry

One row per fund, kept as a CSV or YAML file the job reads. Suggested fields:

| field | example | notes |
|---|---|---|
| `fund_id` | `mg_inflation_plus` | your key |
| `fund_name`, `manager`, `share_class`, `jse_code`, `isin` | | for name checks and platform lookups |
| `route` | `page_link` / `dated_template` / `stable_url` / `listing_page` / `redirect` / `platform` / `manual` | how the latest sheet is found |
| `page_url` | `https://www.mandg.co.za/all-funds/mg-inflation-plus-fund` | for page_link and listing_page |
| `selector` | `fundDownloadItems[type="Fact Sheet"]` | how the link is picked, in words or code |
| `url_template` | `https://…/{Y}/{m}/{ym}-Fund-MDD.pdf \| https://…/{nY}/{nm}/{ym}-Fund-MDD.pdf` | candidates separated by `\|`, tried in order |
| `name_patterns` | `m&g inflation plus fund` ; `m&g\|prudential` | ALL must match the PDF text |
| `expected_lag_days` | 21 | when "not posted yet" becomes "late" |
| `parser` | `mg_donut_legend` | which extraction layout to use |
| `fallbacks` | AG platform PRCB | second route, used only with a flag in the output |
| `notes` | | quirks, the last time it broke |

Useful template tokens, all relative to the target month:
- `{Y} {m} {ym}`: the month itself (2026, 08, 2026-08);
- `{pY} {pm} {pym}`: the previous month;
- `{nY} {nm} {nym}`: the next month (for upload-month folders).

Also allow a lower-case month name (`august`) and `YYYYMM`.

---

## 6. Extracting the asset allocation

**Tools.** In Python, use **PyMuPDF** (`pip install pymupdf`; `page.get_text("words")` gives
`x0, y0, x1, y1, text`). It is fast and opens files that poppler-based tools hang on. pdfplumber is an
alternative. Whatever you use, **run extraction with a timeout** (a subprocess or worker): one corrupt PDF
can hang a parser forever.

**Method, per layout:**
1. **Find the heading** with its exact wording and case, for example "Asset allocation as at", "ASSET
   ALLOCATION", "Effective asset allocation exposure" or "Portfolio structure". Body prose also says "asset
   allocation" in lower case, and ASISA category names such as "Asset Allocation – Targeted" are decoys.
   Search every page; do not assume a page number.
2. **Bound a box** around the table relative to the heading, because neighbouring panels share the same rows.
3. **Group words into rows by y** (a tolerance of about 3 pt), and pair each value with the label words in its
   row. If labels wrap onto two or three lines, merge sub-lines that sit closer than about 7 pt.
4. **Map each label** to your standard asset classes with an ordered keyword list (below).
5. **Run the checks** in section 7.

**Look-alike panels that sit next to the allocation and share its rows or vocabulary:**
- M&G's "monthly asset class returns" panel uses the same class names with small ± values;
- performance tables with % values directly above the legend (M&G, Nedgroup);
- Top-10 holdings bar charts to the right (Nedgroup) or a Top-10 table whose names get swept into labels
  (Kagiso);
- the income-distributions table (Ninety One);
- side-by-side asset, sector and region charts (Discovery);
- a "Portfolio composition" list of underlying *funds*, which is not the allocation (PSG);
- mandate prose such as "maximum equity exposure of 40%".

**Number traps:**
- **Footnote digits glued on.** Allan Gray prints `28.911` for 28.9 with footnote 11. If a manager uses one
  decimal, keep only the first decimal.
- **One vs two decimals.** Ashburton, Satrix, Sanlam and others print two decimals. Know per layout.
- **Negatives:** `(4.6)` means −4.6 (Coronation); watch for Unicode minus `−`. Real negatives exist:
  currency futures, FX overlays, derivatives, and occasionally foreign cash. Keep them as printed.
- **Comma decimals:** `28,57%` (Personal Trust; Absa 2016–19). Convert only tokens that are wholly a
  comma-decimal percentage, so `2,082,263,544` is never mangled.
- **No % sign, integer percentages, `.5%`, `29.%`**: each appears on some layout.
- **Chart axis ticks** (`0`, `10`, `20` …) look like values. Skip all-numeric rows and tokens without a
  decimal point where the layout always prints decimals.

**Text-layer traps:**
- Some sheets **print text twice**, about 1 pt apart (early Old Mutual). Remove duplicate (label, value)
  pairs, or every slice doubles.
- **Ligatures:** "allocation" can come out as `alloca<U+FB01>on`, `allocaon` or `inflaon`. Match on a
  letters-only skeleton and include the collapsed forms in keyword lists.
- A heading may have no text layer while the table under it does (anchor on a nearby heading instead), and
  vice versa.

**Layout traps:**
- **Two columns, current and previous quarter.** Abax 2022–23 and H4 print both; the current column was
  left. Ashburton's "Statement of changes" swapped column order between years, so choose the column by the
  position of the word "Current" in its header, never by assumed order. One of our parsers silently took the
  stale column for three months before a before/after comparison caught it.
- **Pie charts with scattered labels:** assign each value to the nearest label, and require every value to
  find a label. Two slices' labels can share a baseline.
- **Bar charts print the value at the end of the bar,** so its x position varies. Take the last
  value-shaped token on the row, not a fixed column.
- **Tiered tables** (Coronation, Ninety One): totals → classes → sub-breakdowns. Skip the sub-breakdown tier.
  Recognise tiers by label, not indent, because indents drift between years.
- **Line items appear, disappear and get renamed** between years: "Net equity" vs "Net equities", "Money
  market and bank deposits" vs "Money market and cash", and a hyphen added to "Inflation-linked". Pair by
  label, never by row index.

**Image-only allocations.** Some sheets draw the whole allocation panel as a picture, with no text:
- M&G from November 2022 to December 2023;
- Ashburton 2018–2022, and its L-class sheets;
- some Stanlib, Momentum, Sygnia and Absa years.

Detect it (heading found, no value tokens in the box) and route the sheet to a person or a vision model.
Do not guess. If you use a vision model:
- use a capable one; small models misread dense small print;
- render at 200 dpi, and zoom to 300 dpi or crop when in doubt (26.57 was misread as 28.57 at 200 dpi);
- run **two independent passes** that cannot see each other's numbers;
- reconcile by position on the page, not by label text;
- **never estimate values from bar lengths or slice angles**; if values are not printed, record "not
  transcribable";
- check the transcription sums like any other.

Some charts do not print values at all, and some bar charts that look like pictures do have text. Check
each file.

**Mapping labels to asset classes.** A workable target set has ten blocks: SA equity, SA property, SA bonds,
SA inflation-linked bonds, SA cash, foreign equity, foreign property, foreign bonds, foreign cash, commodities.
Add three holding categories for lines that cannot be split honestly:
- **combined offshore**: a single "Offshore" or "International" line;
- **unclassified fund**: a holding in another unit trust with no look-through;
- **other**.

Test keywords **in order**, because the first match wins:
- "hedged" before "equity". Allan Gray's hedged equity behaves like cash, so decide how to treat it
  deliberately.
- "currency futures", "derivative" and "overlay": a cash-like overlay, often negative.
- "preference": legally equity but traded like income; many treat it as bonds. Decide once.
- "SA Bonds (ex. ILBs)" must hit "ex." before "inflation", or nominal bonds land in ILBs.
- "inflation" or "ILB" → ILBs; "bond", "gilt", "FRN", "fixed interest", "credit", "interest bearing" → bonds.
- "property" or "real estate" → property; "cash", "money market" or "liquid" → cash; "commodit", gold,
  Krugerrand ETFs → commodities.
- Geography: "foreign", "global", "international", "offshore", "intl" or "fgn" → foreign. "Africa ex-SA"
  counts as foreign.

**Keep the vocabulary closed.** An unknown label should stop that fund's extraction and ask for a decision,
not fall into "other". New lines usually mean a layout change you need to see.

---

## 7. Checks and monthly operation

**Per sheet:**
- **Sum:** within ±0.6 of 100 is normal rounding. Warn, do not fail, up to about ±2: some sheets genuinely
  print 98.5 (a missing slice label) or are short by up to 2 points. Never rescale to 100; record as printed.
- **Sub-totals:** if the sheet prints totals (Domestic / Foreign / Total), check that the parts reconcile
  (±0.3–0.6).
- **Jump screen:** a block moving more than about 15 points month on month means look at both sheets.
- **Stale copy:** a SHA-256 equal to last month's file means the host re-served the old sheet. One platform
  served an exact copy of March as "April". But an *identical allocation* in a *different* file is fine for
  quarter-end managers (Ashburton).
- **Duplicates:** two different files claiming the same fund and month must stop the run for a human; never
  pick one silently.
- **Cross-class witness:** if you have two classes' sheets for the same month, their allocations should
  agree within about 1 point (two one-decimal roundings can stack). A difference means a wrong document or a
  parser bug.

**Per run:**
- **Completeness check:** every fund in every model portfolio has a sheet for the target month, or an
  explicit `pending` / `exception` status. Without this check, a fund that fails just drops out and the
  portfolio weights still sum to 100, so nobody notices. This happened to us: two funds went missing for three
  months.
- **Retry window:** retry anything missing from the last three months on every run, because sheets are
  posted late. Keep a list of slots known to be permanently wrong or absent (a URL that always serves the
  wrong fund), so the job stops retrying them.
- **Exceptions report**, one line per issue: not posted yet / late beyond lag / wrong document / stale copy /
  name mismatch / parse failed / image-only / sum off / unknown label / blocked by site.
- **Output table:** `fund_id, sheet_month, allocation_stamp, share_class_used, label_raw, block, weight_pct,
  source_url, sha256, fetched_at, parser, qc_status`.
- **Storage:** file each PDF under the month it says it is, for example `archive/<YYYY-MM>/<fund_id>.pdf`,
  plus a manifest CSV. Never overwrite.
- **Insurance (optional):** sheets on "one URL, overwritten monthly" hosts exist only until next month.
  Asking the Internet Archive to capture them (`https://web.archive.org/save/<url>`, about 15 seconds apart,
  429 is normal) creates a permanent copy.

---

## 8. Time-wasters to skip

- **Date or version parameters on "latest" URLs.** They were ignored everywhere we tried them: Morningstar
  LatestDoc, Discovery's web service, Coronation's `DownloadFundFactSheet`, Satrix, Old Mutual's
  `?sfvrsn=`, PSG's generator, Glacier. A "latest" URL serves the latest file whatever you append.
- **Vendor asset-allocation data fields** for SA funds (Morningstar's data feed). They stopped being
  maintained around 2012. Factsheets are the source.
- **Old Mutual's asset store**: links contain a version id that cannot be enumerated. Use the fund page's
  current link.
- **Search engines as an automated source.** They block after a handful of queries. They are fine by hand
  for finding where a manager keeps its files.
- **Common Crawl and archive.today** hold almost no fund PDFs.
- **Platform stores for history.** They are current-or-frozen per share class, never dated.
- **The Wayback Machine** (useful for a gap, not routine): query
  `https://web.archive.org/cdx/search/cdx?url=<url>&output=json&filter=statuscode:200&filter=!mimetype:text/html&collapse=digest`
  and fetch raw bytes with `https://web.archive.org/web/<timestamp>id_/<url>` (the `id_` matters).
  - **Do not filter on `mimetype:application/pdf`**: SA CDNs serve PDFs as `application/octet-stream` and
    similar.
  - A capture's timestamp is not the sheet month; date the content.
  - Use `matchType=domain` to include subdomains.

---

## 9. Manager and platform notes (as observed Aug–Oct 2026)

"Dated" means the URL encodes the month. "Stable" means one URL overwritten each month. For every route, date
the content and check the name.

**Allan Gray (own funds).** Dated. Real 404s for missing months.
- URL: `https://www.allangray.co.za/globalassets/documents-repository/fund/factsheet/<Fund%20Name>/Files/<CODE>%20-%20YYYY-MM.pdf`,
  for example `Allan%20Gray%20Stable%20Fund/Files/AGSF%20-%202026-08.pdf`. Also `…/<Fund Name>/Latest/<Fund Name> Latest.pdf`.
- Allocation on page 2, "Asset allocation on DD Month YYYY", with columns Total | SA | Foreign (an
  Africa ex-SA column in older years).
- Watch for the hedged-equity line and glued footnote digits.

**Allan Gray platform (other managers' funds).** Dated, monthly.
- URL: the same store, with platform folders and codes, for example:
  - `Prudential%20Inflation%20Plus%20Fund%20(Class%20B)/Files/PRCB%20-%20YYYY-MM.pdf` (M&G)
  - `Ninety%20One%20Cautious%20Managed%20Fund%20(Class%20H)/Files/CMFH…`
  - `Coronation%20Balanced%20Defensive%20Fund%20(Class%20P)/Files/CBDB4…`
  - `Nedgroup%20Investments%20Stable%20Fund%20(Class%20A2)/Files/NISA…`
  - `Kagiso%20Stable%20Fund%20(Class%20B)/Files/KASCB…` (Camissa, still under its old name)
- Find folder names in Allan Gray's "Local Investment Platform Fund List" PDF.
- Posts a few weeks after month-end (M&G's sheets took 4–5 weeks).
- It deletes a fund's whole folder when the fund leaves the platform.
- It has served the wrong fund and a byte-identical previous month at valid URLs, so always run R2 and R9.

**Coronation.** Dated archive.
- URL: `https://www.coronation.com/globalassets/asset-library/comprehensive-fact-sheets/{YYYY}/{month}/{YYYY}-{month}-<fund-slug>-comprehensive.pdf`
  (`{month}` = lower-case full name). Variants seen across years add `/personal/`, `/retail/`, a `_<code>`
  suffix, a `monthly-fact-sheets/` path for the short sheet, and even a typo folder (`2013/decemebr/`).
  Generate all variants and try them in order.
- The fund page needs a region/investor-type cookie (without it you get `/en/global-error/`). Once through,
  it has a `#histDataDrop` select listing archived sheets with exact paths, which is the most reliable source
  of paths.
- `DownloadFundFactSheet?fundCode=…` always serves the current sheet.
- Allocation on page 2, "Effective asset allocation exposure": tiered; negatives in parentheses; a negative
  currency-futures line.

**Nedgroup Investments.** Dated folder; the archive is a rolling window starting 2024.
- URL: `https://www.nedgroupinvestments.com/content/dam/NGISingleSiteContent/south-africa/pdfs/factsheets/{YYYYMM}/Nedgroup%20Investments%20<Fund>%20Fund%20<CLASS>.pdf`.
  Class names can contain spaces and parentheses, for example `B2%20(INST)`.
- **Trap:** for a month that was never published, the URL served a later month's sheet. Date by content.
- Allocation on page 2, a "Portfolio structure" bar chart; a Top-10 bar chart shares its rows, so use a tight
  box. Header "As At DD Month YYYY". Mid-month pricing dates also appear.

**Ninety One.** Stable URL, current only (Sitecore).
- URL: `https://ninetyone.com/-/media/documents/minimum-disclosure-document/91-sa-ut-<fund-slug>-<class>-zar-mdd.pdf`,
  for example `…cautious-managed-fund-a-zar-mdd.pdf`. Holdings PDFs refused even browser-like requests.
- Allocation on page 1, "Asset allocation (%)": tiered, no indents (recognise tiers by label), an FX line
  that can be negative. Date "As at end <Month> <YYYY>".

**M&G (formerly Prudential).** See section 2.
- Route: fund page → `fundDownloadItems` → `type == "Fact Sheet"`. Documents on `mandg.co.za:8082/media/<key>/…`.
- Allocation on page 1: a bulleted donut legend; "Asset allocation as at"; quarterly Top-10 stamp.
- Older sheets (to 2021) had a list-style "ASSET ALLOCATION" table with a look-alike "monthly asset class
  returns" panel beside it.

**Ashburton.** A listing page with unguessable links.
- Listing pages (Next.js): `https://www.ashburtoninvestments.com/za/funds-and-performance/fund-factsheets`
  (current) and `/archived-fund-factsheets` (about 5 MB, every fund and class back to 2013).
- Documents: `/api/assets/{GUID}/<FundName>_{CLASS}_{Month}_{YYYY}_SA_ALL[_ISIN].pdf`. Scrape the listing
  and match file names.
- The archive page stalls for non-browser clients: send a normal browser User-Agent and allow a long
  timeout (about 4 minutes).
- From May 2026 the share classes were restructured: the old retail A1 sheet stopped and the fund continued
  under B4/B5. L-class sheets have image-only allocations.
- The allocation (page 2, "Statement of changes of holdings") is a quarter-end figure, so consecutive months
  are often identical. Choose the column by its "Current" header.

**Satrix.** Redirect, current only.
- Route: `https://satrix.co.za/fund/mdd/<CODE>` (for example `SLEA1`) redirects to `/media/{id}`.
- Ids are sequential site-wide. `HEAD /media/{id}?inline=true` returns the original file name in
  `Content-Disposition`, which is handy for finding a month you missed. Query strings are ignored.
- The EasyEquities mirror (`resources.easyequities.co.za/Unit%20Trusts/<CODE>.pdf`) was stale.
- Allocation on page 2: a bar chart with two-decimal values; axis ticks look like numbers.

**Abax (Prescient).** Dated by file name.
- URL: `https://www.abax.co.za/wp-content/uploads/{uploadY}/{uploadM}/{YYYY-MM}-Abax-Absolute-Fund-MDD.pdf`.
  The file name's month is the sheet month; the folder is the **upload** month, usually the next month, so
  try next month's folder, then the same month's, then two months later.
- The site sits behind a Cloudflare challenge. Copies also appear in Prescient's media library under names
  without "abax" (`prescient.co.za/media/<id>/YYYY-MM-absolute-fund-mdd.pdf`). Some months were never posted.
- Older sheets print current and previous columns; current is on the left.

**CAM (formerly H4).** Dated, with variants.
- URL: `https://cam.co.za/wp-content/uploads/{Y}/{m}/{YYYY-MM}-H4-Stable-Fund-B1-MDD.pdf`. The same sheet
  has also appeared in the previous month's folder with a `-1` suffix. Try the previous, same and next
  month's folders.
- The sheets print no "as at"; the ESG panel's "as of" is a decoy.
- The old h4ci.co.za redirect has a malformed `Location` header: rewrite it, do not follow it.

**Old Mutual.** Current only.
- The `oldmutualinvest.com/om-docs/<asset_uid>/<FundName>.pdf` redirect goes to a versioned asset store that
  cannot be enumerated. Each fund has three such links (MDD, holdings, risk/return), so pick the MDD.
- Legacy `oldmutual.co.za` paths serve the same current file whatever `?sfvrsn=` you send.
- Some months were published only as a one-page chart-only "General Investor Report" with no values.

**Sanlam, and funds hosted by Sanlam (Amplify and others).**
- sanlaminvestments.com's factsheet page calls a public JSON API whose `mdd_urls` are tokenised FundPress
  links, current only. `sanlam.com/productcatalog/…` returned 503 for weeks.
- Amplify: a stable URL at `truffle.co.za/docs/SI_<Fund_Name>.pdf`, and a dated archive at
  `truffle.co.za/docs/Historical/{YYYY}/{YYYYMMDD}/…`. The folder date is the posting date, not the sheet
  month. The dated archive refused non-browser User-Agents (403); the stable URL did not.
- The Matrix-hosted copy ran a month behind.
- Sanlam-template sheets: the legend on page 2, with two-decimal values.

**Sygnia.** WordPress behind a bot filter.
- Sheets are re-uploaded each month into a fixed folder with the month in the file name
  (`wp-content/uploads/2025/03/{YYYY}-{MON}-<CODE>-…-Fund-Fact-Sheet.pdf`) and overwritten.
- Empty upload folders answer 200 with a tiny stub (R1). Legends were images in some years.

**PSG.** `download.psg.co.za/files/wealth/fund-fact-sheets/<Fund>-Class-{A..E}.pdf`: undated, current.
"Portfolio Composition" lists underlying funds and is not the allocation. A ligature turns "Allocation" into
"Allocaon".

**Absa.** absainvestments.co.za sits behind a bot wall. An older `absa.co.za/…/ffs/<Fund>.pdf` served a
frozen 2023 sheet, and another Absa "current" file was frozen at February 2020. Values used comma decimals
in 2016–19.

**STANLIB.** Legacy paths return HTML "not found" pages with status 200. A literature hub kept a frozen set
for a closed fund.

**Discovery.** `discovery.co.za/invest-public/ws/documvest-factsheet/download/<JSE code>` serves one file and
ignores date parameters; on record it served the **previous** month. Charts sit side by side; a negative
local-cash line occurred.

**Personal Trust.** Stable URL, `personaltrust.co.za/reports/FS-PT-<Fund>.pdf`; a bar chart with comma
decimals.

**Camissa (formerly Kagiso).** Pie charts with the value under the label until 2025, and a bar with a
two-column legend in 2026. Sidebar prose leaks into legend labels. Masthead typos.

**Platform stores keyed by JSE code** (current for live classes, frozen at delisting for others; date the
content):
- Momentum Wealth: `wealth.momentum.co.za/investments/factsheets/<slug>-(<class>).pdf`. Many managers;
  wrong-fund serves on record; sometimes a month behind.
- Glacier: `transact.glacier.co.za/SECURE/GLC_downloads/<JSE code>.pdf`.
- EasyEquities: `resources.easyequities.co.za/Unit%20Trusts/<code>.pdf`.
- PPS: `ppsisecure.co.za/SecureDocuments/FundFactSheets/<Fund> - <Class>.pdf`.

**Morningstar document library** (only if your firm licenses Morningstar):
- `https://doc.morningstar.com/DocHistory.aspx?clientid=<YOUR_ID>&key=<YOUR_KEY>&language=451&investmentid=<share-class id, e.g. F0000…>&documenttype=52&investmenttype=1&format=PDF&frame=0`
  lists every factsheet version the vendor received, with effective and post dates and direct links.
  `LatestDoc.aspx` with the same query gives the current one.
- Leave out the `market` parameter: it returned more months without it.
- Traps:
  - effective dates are occasionally a month off (Discovery's ran a month late; Stanlib's 1–3 months);
  - class tags are loose;
  - several versions per month (take the one posted nearest month-end + 3 weeks);
  - one id was attached to the wrong fund.
- Use only a client id and key issued to your firm.

---

## 10. Reference code (Python, tested)

Two small modules, standard library plus PyMuPDF. They are tested as follows:
- `factsheet_dates.py` dated 906 of 908 sheets with known months correctly (section 3).
- `factsheet_fetch.py` was run end to end against the live M&G site on 13 October 2026. It found the link,
  fetched the August 2026 sheet, passed the name check, read the month as 2026-08 and the stamp as 2026-08,
  and returned eight legend lines summing to 99.8.

Adapt them; don't treat them as finished. The legend reader's box is tuned to M&G.

### factsheet_dates.py

```python
"""Read the month a fund factsheet (MDD) is FOR from its own text.

Rules distilled from a pipeline that has dated close to 3,000 South African
factsheets, plus a separate reader for the asset-allocation table's own date stamp.
"""
import calendar
import datetime as dt
import re

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
MON3 = [m[:3] for m in MONTHS]
_MON_ALT = "|".join(MONTHS + MON3)

# A date whose preceding ~30 characters match CUE_NEG belongs to somebody
# else's calendar (issue/print dates, inception, MSCI ESG panels, TER periods).
CUE_POS = re.compile(r"as at|as of|as-at|month end|month-end|monthend|period end|"
                     r"ended|data to|reporting date|factsheet date")
CUE_NEG = re.compile(r"issue date|date of issue|issued|published|print date|printed|"
                     r"generated|revision|version|updated on|launch|inception|msci|esg|"
                     r"period:|expense ratio|payment date")
# "asset allocation as at 31 aug 2026" / "asset allocation on 31 july 2026"
CUE_AA = re.compile(r"allocation[^a-z0-9]{0,3}(?:\([^)]{0,12}\)\s*)?(?:as at|as of|on)\s*$")

HEAD_CHARS = 260    # fallback masthead: first characters of page 1's text
HEAD_FRACTION = 0.15  # masthead by position: top 15% of page 1


def normalise(pages):
    """First pages' text -> lower case, runs of spaces collapsed, blank lines dropped."""
    s = "\n".join(pages)
    s = re.sub(r"[ \t]+", " ", s.lower())
    return re.sub(r"\n[ \n]*", "\n", s).strip()


def masthead_text(page, fraction=HEAD_FRACTION):
    """Text printed in the top `fraction` of a PyMuPDF page, read top to bottom.

    Use this rather than 'the first N characters': a PDF's text order is
    its drawing order, which on many sheets starts with a side panel (Top-10
    list, income distributions) rather than the title."""
    cut = page.rect.height * fraction
    # Words, not text blocks: a block can start near the top and run far down
    # the page, and splitting blocks separates a date from the words before it
    # ('produced by msci esg research as of' | '31/12/2021') that disqualify it.
    words = [w for w in page.get_text("words") if w[3] <= cut]
    words.sort(key=lambda w: (round(w[1]), w[0]))
    return normalise([" ".join(w[4] for w in words)])


def _dates(txt):
    """Every date in the text: (position, year, month, day or None).

    Spelled-out forms tolerate a footnote digit glued to the year: Allan Gray
    prints 'asset allocation on 30 june 20247' (2024 + footnote 7)."""
    out, spans = [], []
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({_MON_ALT})[a-z]*\.?\s+(\d{{4}})\d?\b", txt):
        out.append((m.start(), int(m.group(3)), MON3.index(m.group(2)[:3]) + 1, int(m.group(1))))
        spans.append(m.span())
    for m in re.finditer(rf"\b({_MON_ALT})[a-z]*\.?\s+(\d{{4}})\d?\b", txt):
        if any(a <= m.start() < b for a, b in spans):   # 'july 2026' inside '31 july 2026'
            continue
        out.append((m.start(), int(m.group(2)), MON3.index(m.group(1)[:3]) + 1, None))
    for m in re.finditer(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", txt):   # SA: d/m/y
        out.append((m.start(), int(m.group(3)), int(m.group(2)), int(m.group(1))))
    for m in re.finditer(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b", txt):
        out.append((m.start(), int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return [(p, y, mo, d) for p, y, mo, d in out if 1 <= mo <= 12 and 2000 <= y]


def _ctx(txt, pos, n=30):
    return txt[max(0, pos - n):pos]


def _hits(txt, max_ym):
    hits = []
    for p, y, mo, d in _dates(txt):
        if (y, mo) > max_ym:
            continue
        eom = calendar.monthrange(y, mo)[1]
        c = _ctx(txt, p)
        hits.append({"pos": p, "ym": (y, mo), "month_end": d == eom, "bare": d is None,
                     "cued": bool(CUE_POS.search(c)), "neg": bool(CUE_NEG.search(c))})
    return hits


def sheet_month(txt, not_after=None, masthead=None):
    """The month the sheet is FOR, as 'YYYY-MM' (None if no readable date).

    txt:      normalised text of the first two pages.
    masthead: normalised text of the top of page 1 (masthead_text()); if
              omitted, the first HEAD_CHARS characters of txt stand in.

    Rules, in order:
      1. Drop dates after `not_after` (a sheet cannot report a month that has
         not ended) and dates cued as issue/print/inception/ESG/TER dates.
      2. MASTHEAD: if the masthead holds a month-end date ('31 August 2026')
         or a bare month ('August 2026'), it wins, month-ends first. This is
         how a human reads a factsheet, and the only rule that survives a
         stale document. A mid-month date in the masthead ('1 July 2000') is
         an inception or issue date whose label sits in another column, so
         it does not count.
      3. Otherwise take the most recent month-END date (a reporting date;
         '17 March' is somebody's diary). Bond maturities are month-ends too,
         which is why rule 1's not_after matters.
      4. Otherwise the most recent 'as at'-cued date, otherwise any date.
    """
    if not txt:
        return None
    not_after = not_after or dt.date.today()
    max_ym = (not_after.year, not_after.month)
    hits = _hits(txt, max_ym)
    if not hits:
        return None
    ok = [h for h in hits if not h["neg"]] or hits
    if masthead is not None:
        mh = _hits(masthead, max_ym)
        head = [h for h in mh if not h["neg"]]
    else:
        head = [h for h in ok if h["pos"] <= HEAD_CHARS]
    head = [h for h in head if h["month_end"] or h["bare"]]
    if head:
        pool = [h for h in head if h["month_end"]] or head
    else:
        pool = ([h for h in ok if h["month_end"]] or [h for h in ok if h["cued"]] or ok)
    y, mo = max(h["ym"] for h in pool)
    return f"{y:04d}-{mo:02d}"


def allocation_stamp(txt):
    """The date the ASSET ALLOCATION table carries, e.g. 'asset allocation as at
    31 aug 2026' -> '2026-08'. None when the sheet prints no such stamp.

    Keep it separate from sheet_month(): some managers print a quarter-end
    allocation on every sheet in the quarter, so a stamp older than the
    sheet month is normal, not a stale document."""
    for p, y, mo, d in sorted(_dates(txt)):
        if CUE_AA.search(_ctx(txt, p, 40)):
            return f"{y:04d}-{mo:02d}"
    return None
```

### factsheet_fetch.py

```python
"""Fetch a factsheet safely, find M&G's current factsheet link, read a legend by coordinates."""
import hashlib
import json
import re
import urllib.error
import urllib.request

import pymupdf as fitz  # PyMuPDF

from factsheet_dates import masthead_text, normalise

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def http_get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA,
                                               "Accept": "*/*",
                                               "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), b""


def fetch_pdf(url):
    """GET a URL and accept it only if the BYTES are a PDF.

    A 200 is not a PDF: CMSs answer missing files with an HTML page and
    status 200. Old multipart-wrapped files put %PDF a few hundred bytes in,
    so search the first KB and slice from there."""
    status, headers, body = http_get(url)
    out = {"url": url, "status": status, "ok": False,
           "last_modified": headers.get("Last-Modified"), "bytes": None, "sha256": None}
    if status != 200:
        out["reason"] = f"HTTP {status}"
        return out
    at = body[:1024].find(b"%PDF-")
    if len(body) < 1024 or at < 0:
        out["reason"] = "200 but not a PDF (magic bytes)"
        return out
    body = body[at:]
    out.update(ok=True, reason="ok", bytes=body, sha256=hashlib.sha256(body).hexdigest())
    return out


def pdf_text(pdf_bytes, pages=2):
    """(text of the first pages, text of page 1's masthead), both normalised.
    Run this in a worker with a timeout in production: one bad PDF can hang."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        txt = normalise([doc[i].get_text("text") for i in range(min(pages, doc.page_count))])
        return txt, masthead_text(doc[0])


def names_itself(text, patterns):
    """True when EVERY pattern (fund name, manager...) appears in the text.
    The right URL can serve the wrong fund, so the document must name itself."""
    t = re.sub(r"\s+", " ", text.lower())
    return all(re.search(p, t) for p in patterns)


def mandg_factsheet_url(fund_slug):
    """Current factsheet link for an M&G (South Africa) fund.

    The fund page (https://www.mandg.co.za/all-funds/<slug>) is a Next.js
    page: the PDF links are NOT <a href> tags in the HTML but entries of a
    'fundDownloadItems' list inside the embedded data payload. The media key
    in the link changes every time a new sheet is uploaded, and old keys keep
    serving old sheets, so look the link up fresh every run."""
    status, _, body = http_get(f"https://www.mandg.co.za/all-funds/{fund_slug}")
    if status != 200:
        raise RuntimeError(f"fund page HTTP {status}")
    html = body.decode("utf-8", "replace").replace('\\"', '"')
    m = re.search(r'"fundDownloadItems":(\[.*?\])', html)
    if not m:
        raise RuntimeError("no fundDownloadItems on the page -- layout changed?")
    items = json.loads(m.group(1))
    sheets = [i["path"] for i in items if (i.get("type") or "").lower() == "fact sheet"]
    if len(sheets) != 1:
        raise RuntimeError(f"expected one 'Fact Sheet' item, got {items}")
    return sheets[0]


VALUE = re.compile(r"^\(?-?\d{1,3}(?:[.,]\d{1,2})?%?\)?$")


def _find_heading(words, phrase):
    """First word that starts `phrase` (e.g. ['Asset', 'allocation', 'as']) on
    one line. Prose also says 'asset allocation', so anchor on the full
    heading wording (and its case), never a single common word."""
    for i in range(len(words) - len(phrase) + 1):
        run = words[i:i + len(phrase)]
        if ([w[4] for w in run] == phrase
                and all(abs(w[1] - run[0][1]) < 2 for w in run)):
            return run[0]
    raise LookupError(f"heading {' '.join(phrase)!r} not found")


def legend_rows(pdf_bytes, heading=("Asset", "allocation", "as"), page=0,
                dx=(0, 200), dy=(0, 140), ytol=3.0):
    """(label, value) pairs from a legend/table under a heading, paired by
    WORD COORDINATES. Text-line extraction is not safe: on M&G sheets the
    values print two rows away from their labels in layout mode."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        words = doc[page].get_text("words")  # x0, y0, x1, y1, text, ...
    head = _find_heading(words, list(heading))
    x_lo, x_hi = head[0] + dx[0], head[0] + dx[1]
    y_lo, y_hi = head[1] + dy[0], head[1] + dy[1]
    box = sorted((w for w in words if x_lo <= w[0] <= x_hi and y_lo < w[1] <= y_hi),
                 key=lambda w: (w[1], w[0]))
    rows, cur = [], []
    for w in box:                      # group words into rows by y
        if cur and abs(w[1] - cur[-1][1]) > ytol:
            rows.append(cur)
            cur = []
        cur.append(w)
    rows.append(cur)
    out = []
    for r in rows:
        vals = [w for w in r if VALUE.match(w[4]) and ("%" in w[4] or "." in w[4])]
        labels = [w[4] for w in sorted(r, key=lambda w: w[0])
                  if w not in vals and w[4] not in {"l", "n", "•", "■"}]
        if vals and labels:
            v = vals[-1][4].strip("%()").replace(",", ".")
            out.append((" ".join(labels), float(v)))
    return out


if __name__ == "__main__":
    from factsheet_dates import allocation_stamp, sheet_month

    url = mandg_factsheet_url("mg-inflation-plus-fund")
    print("link:", url)
    r = fetch_pdf(url)
    print("fetch:", r["status"], r["reason"], r["last_modified"])
    txt, head = pdf_text(r["bytes"])
    print("names itself:", names_itself(txt, [r"m&g inflation plus fund"]))
    print("sheet month:", sheet_month(txt, masthead=head),
          "| allocation stamp:", allocation_stamp(txt))
    rows = legend_rows(r["bytes"])
    for lab, v in rows:
        print(f"  {lab:28s} {v:6.1f}")
    print("  sum", round(sum(v for _, v in rows), 1))
```
