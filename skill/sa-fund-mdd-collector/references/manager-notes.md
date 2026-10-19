# Manager and site notes for South African MDDs (seen Aug–Oct 2026)

What each manager's or platform's site actually did when this collector was built for 192 funds. Websites
change, so treat URL patterns as starting points to verify. `assets/sa_mdd_sources_example.yaml` has a
working entry for every fund mentioned here. "Stable" means one URL overwritten each month; "dated" means
the URL carries the month. Always date the MDD by its content, never by the URL.

## Contents
- Managers A–Z
- Platforms that host other managers' sheets
- Renamed funds seen in 2025–26
- Traps that caught this collector

## Managers

- **10X (ex-CoreShares):** the fund page `assetmanagement.10x.co.za/fund/10x-sp-south-africa-top50-index-etf/`
  links the current Class B "Top50 Tracker Fund" MDD; upload folders are unpredictable, so use `page` +
  `link_match: Top50-Tracker-Fund-.*MDD-Class-B`. Posted about 6 weeks after month-end (`lag_days: 50`).
- **Allan Gray (own funds):** dated:
  `allangray.co.za/globalassets/documents-repository/fund/factsheet/<Fund Name>/Files/<CODE> - YYYY-MM.pdf`.
  - Codes include AGBF (Balanced), AGSF (Stable), AGEF (Equity), AGOE (Orbis Global Equity Feeder),
    AGGF (Orbis Global Balanced Feeder), AGINA (Income), AGDA (SA Equity) and AGTF00 (Tax-Free pack).
  - Real 404s for months not posted yet.
- **Amplify (Sanlam-hosted):** use `sanlam_fund` (Sanlam's fact-sheet API).
  - Sanlam's link for Amplify SCI Diversified Income served the Active Equity sheet. Use Amplify's own
    fund page instead (`page` + `link_match: retrieveDocument`, `referer: https://www.amplify.co.za/`).
- **BlackRock / iShares (LU funds):** monthly fact sheet
  `ishares.com/gls-download/literature/fact-sheet/<name>-<isin>-gb-en-individual.pdf` (or `blackrock.com/...`).
  The SA "MDD" version is quarterly only.
- **Camissa (ex-Kagiso):** fund page `camissa-am.com/funds/<fund>`, rendered, with `link_match: _\d{4}\.pdf`.
- **Coronation:** `coronation.com/en/personal/funds/factsheet/comprehensive-fact-sheets/latest/<CODE>`
  always serves the current comprehensive sheet (e.g. CNSB Bond, CNTF Top 20).
- **Curate (Momentum):** curateinvestments.com sits behind Cloudflare. Its MDD button points at Momentum's
  `wealth.momentum.co.za/investments/factsheets/curate-momentum-<fund>-(a)-zaf.pdf`.
- **Discovery:** `discovery.co.za/invest-public/ws/documvest-factsheet/download/<JSE code>`, one file per code.
  - It has served the previous month, so trust the content date.
  - Its PDFs extract without spaces, which affects text matching.
- **Foord:** dated by the next month's upload folder:
  `foord.co.za/sites/default/files/{next_yyyy}-{next_mm}/<Fund>%20Class%20A%20at%20{yyyy}-{mm}-{dd}.pdf`.
- **Fundrock (ex-BCI) funds** (Otto1890, Granate, Centaur, Methodical, Visio, 36ONE BCI, 4D, Northstar,
  Reitway, Vunani…): static
  `bcis.co.za/upload/factsheet_categories_folders/funds/<Manager>/<Fund> (<Class>) <CODE>.pdf`.
  - The full list is on `bcis.co.za/fundrock-collective-investments/funds/funds`.
  - It once returned 0-byte files for a week; the 1 KB PDF check refused them.
- **Gryphon:** stable `gryphon.com/documents/<fund-slug>.pdf`.
- **Janus Henderson (Horizon SICAV):**
  `cdn.janushenderson.com/webdocs/<code>_<ISIN>_<code>_M_{dd}{mm}{yyyy}_XX(EN-GB).pdf`.
  - Only the latest month stays online.
  - Add a `{bdd}` (last weekday) variant for weekend month-ends.
- **M&G (ex-Prudential):** the all-funds page `mandg.co.za/all-funds?type=funds` embeds JSON with each
  fund's `FactSheet` path; `mandg_fund: <name>` reads it.
  - PDFs are served from **mandg.co.za:8082**, which some networks block.
  - The media key changes on every upload, and old keys keep serving old files.
- **Marriott:** stable `marriott.co.za/downloads/factsheets/<Fund>_Fact_Sheet.pdf`.
  - **robots.txt disallows bots**; only override it with the owner's agreement (`ignore_robots`).
  - The PDFs use cid-encoded fonts, which the collector decodes.
  - Core Income is monthly; Dividend Growth, Essential Income and Property Income are **quarterly**.
- **Merchant West (ex-Counterpoint):** `merchantwest.co.za/investments/our-funds/` links monthly MDDs
  (`SI_Merchant-West-SCI-<Fund>-<Month>-<yyyy>-1.pdf`); use `page` + `link_match`.
- **Nedgroup Investments:** dated folder
  `nedgroupinvestments.com/content/dam/NGISingleSiteContent/south-africa/pdfs/factsheets/{yyyymm}/Nedgroup%20Investments%20<Fund>%20Fund%20<Class>.pdf`.
  A folder for an unpublished month can serve a later month's sheet.
- **Ninety One (ex-Investec):** bot-protected, so use `browser: true`.
  - Fact sheets: `ninetyone.com/-/media/documents/factsheet/91-sa-ut-<fund>-<class>-zar-factsheet.pdf`.
  - Official MDDs exist for the **A class only**:
    `…/minimum-disclosure-document/91-sa-ut-<fund>-a-zar-mdd.pdf`. H-class MDD URLs return 404.
- **Old Mutual:** `oldmutualinvest.com/om-docs/<asset uid>/<Name>.pdf` redirects to the latest version.
  - Each fund page has three such links (MDD, holdings, risk/return), so take the MDD's uid from the
    fund table.
  - Old uids can serve another fund.
- **Orbis:** fact sheets on Orbis' and Allan Gray's sites (see the example registry).
- **PPS:** `pps.co.za/sites/default/files/invest-documents/fund-fact-sheets/PPS%20Monthly%20FactSheets/<Fund>_%20A%20&%20A2.pdf`.
  Renamed funds can keep their **old file name** (PPS Balanced Passive is still "PPS Balanced Index Tracker").
- **Prescient** (Prescient funds and many third-party funds: Abax, Fairtree, Steyn Equity, Vulcan,
  Bateleur, 36ONE Prescient, Laurium):
  - Links are on `prescient.co.za/funds/other-funds/` (rendered) and change monthly.
  - Use `link_match` with month templates, e.g. `{yyyy}-{mm}-abax-absolute-fund-mdd`.
  - Abax "Absolute"/"Balanced" are different funds from "SA Absolute"/"SA Balanced".
  - Fairtree's PDFs have no text layer, so the month comes from the file name and the name check can't run.
- **PSG:** `download.psg.co.za/files/asset-management/fund-fact-sheets/PSG-<Fund>-Class-<X>.pdf`, current only.
- **Ranmore:** `ranmorefunds.com/historic-factsheets/` lists every month publicly (`link_match: /{Month}-{yyyy}[^/]*\.pdf$`).
- **Rezco:** monthly pages on rezco.com (see the example registry).
- **Sanlam Collective Investments** (Amplify, Denker, Catalyst, Matrix, Obsidian, Truffle…):
  `sanlam_fund: <exact fund name and class>` reads the public JSON API behind
  sanlaminvestments.com/fund-fact-sheets (FundPress links, current only). Needs the browser.
- **Satrix:** `satrix.co.za/fund/mdd/<CODE>` redirects to the current MDD (e.g. SLEA1, STRTA1, SAAIF).
- **Schroders:** document store `api.schroders.com/document-store/SISF-<Fund>-<Class>-FMR-LUEN.pdf`.
  - The Luxembourg edition is current; others (US) can be years old.
  - Dates are written "31.08.2026".
- **STANLIB:** the website blocks automated access. Use platform copies (`ppsisecure.co.za` or Momentum
  Wealth), which run about a month behind (`lag_days: 60`).
- **Steyn Capital:** dated `steyncapitalmanagement.com/wp-content/uploads/...-{Mon}-{yyyy}-MDD.pdf`;
  robots.txt disallows bots.
- **Sygnia:** fund page with `link_match` on the class code (e.g. `SIRGA.*FFS`), rendered.
- **Vulcan Value Partners (UCITS):** fact sheet on Prescient's other-funds page.

## Platforms that host other managers' sheets

- **Allan Gray platform store:** dated `…/fund/factsheet/<Manager Fund (Class X)>/Files/<CODE> - YYYY-MM.pdf`.
  - Examples: M&G Balanced B **PRAB**, Inflation Plus B **PRCB**, Global Balanced USD B **PRGBFB**.
  - **allangray.co.za/robots.txt disallows** M&G, Coronation, Nedgroup, Satrix, STANLIB, Prescient, PSG
    and others. Use these only with the owner's agreement (`ignore_robots: true` on those funds); one
    owner approved them as an M&G backup.
- **Momentum Wealth:** `wealth.momentum.co.za/investments/factsheets/<slug>-(<class>).pdf`. Many managers.
  **It has served stale sheets and the wrong fund**, so the name and stale checks matter here.
- **PPS secure:** `ppsisecure.co.za/SecureDocuments/FundFactSheets/<Fund> - <Class>.pdf`, about a month behind.
- **EasyEquities:** `resources.easyequities.co.za/Unit%20Trusts/<CODE>.pdf`, often stale.

## Renamed funds seen in 2025–26 (keep the old name in `name`, add the new one to `doc_names`)

| Old name | Now |
|---|---|
| Sasfin BCI Flexible Income | Otto1890 FR Flexible Income Fund (Sasfin Wealth became Otto1890) |
| Counterpoint SCI … | Merchant West SCI … |
| CoreShares S&P SA Top 50 | 10X S&P SA Top50 Tracker Fund |
| Amplify SCI Multi Strategy RHF (Obsidian) | Amplify SCI Active Equity RHF (AG Capital) |
| PPS Balanced Index Tracker | PPS Balanced Passive (the file keeps the old name) |
| Ninety One Global Multi-Asset Income Feeder | Ninety One Global Managed Income Feeder |
| SIM Inflation Plus | SCI Inflation Plus; SCI Ninety One Cautious Managed (from 9 Oct 2026) |
| Momentum Capped SWIX Index | Momentum Capped All Share |
| Mi-Plan IP Enhanced Income | Vunani FR Enhanced Income Fund |
| Discovery (Aggressive) Dynamic Asset Optimiser FoF | Cogence Discovery Balanced Dynamic Asset Optimiser FoF |
| Prudential / Kagiso / Investec AM / H4 | M&G / Camissa / Ninety One / CAM |

## Traps that caught this collector

- **A page link falling back to "any PDF on the page".** When a fund's own link wasn't posted yet,
  Prescient's page handed four funds another fund's MDD. The fix: fund-specific `link_match` patterns
  never fall back. The name check caught it.
- **Quarterly holdings stamps** ("Top 10 holdings as at 30 Jun") and issue dates misdated sheets until
  the masthead rule was added.
- **0-byte or HTML "200" responses.** The 1 KB `%PDF` check refuses them.
- **A source that lists the wrong document:** Sanlam's Amplify Diversified Income link; old Old Mutual uids.
