---
name: sa-fund-mdd-collector
description: Collect South African unit trust MDDs (minimum disclosure documents / fund fact sheets) for a list of funds, file each one under the month it reports on, and keep a monthly MDD Tracker spreadsheet (Collected / Pending / Late, ISIN, fund AUM, inception date, benchmark, exceptions), optionally downloading them every week on the user's PC. Use this skill whenever someone wants to find, download, scrape, track or organise MDDs or fact sheets for SA funds or offshore funds held by SA investors (Allan Gray, Coronation, Ninety One, M&G, Satrix, Nedgroup, Prescient, Sanlam/Amplify, PSG, STANLIB, 10X and others); asks which funds' fact sheets are outstanding this month; wants an automatic weekly MDD download into a folder or OneDrive; or wants to fix a fund that downloads the wrong or an old document. Also use it to maintain an existing MDD project built with it (one with a HANDOVER.md and config/mdd_sources.yaml).
---

# SA fund MDD collector

Builds and runs a small Python collector that downloads each fund's latest MDD, checks it really is that
fund's sheet for a stated month, files it as `<MDD folder>\<YYYY - MM>\<Fund>.pdf` and writes
`!MDD Tracker YYYY - MM.xlsx` per month. It came out of a real project that tracked 192 funds for an
investment firm. Its checks exist because each one caught a real failure: wrong-fund sheets, stale
copies, misread months, HTML "200" pages.

## Before anything else: the project memory

Every project made with this skill has a `HANDOVER.md`. **Read it in full before any scan, scrape,
source change or tracker rebuild, and update it afterwards** with what you learned (site changes,
renames, wrong or stale documents, owner decisions, ISINs). Then add a dated line to its learning log.
This is how the next session, or another account, avoids repeating the same research. The project's
`CLAUDE.md` says the same, so coding agents pick it up automatically.

If the user already has a project (look for `HANDOVER.md` + `config/mdd_sources.yaml`), skip to
"Running and maintaining".

## Setting up a new project

1. **Ask the user** (in one message):
   - **Where to save the MDDs.** This is the user's choice: a local folder, a OneDrive or SharePoint-synced
     folder, or a network drive. Don't assume one.
   - The fund list: names, ideally with ISINs or share classes. A spreadsheet is fine.
   - Optionally, a holdings workbook with AUM per fund (column A name, column B AUM) and the sheet name.
   - Funds to leave out (e.g. the firm's own funds), as a name pattern.
   - Where it will run weekly (usually their Windows PC), or whether a one-off collection is enough.
2. **Create the project:**
   ```bash
   python <skill>/scripts/init_project.py <project dir> --out-folder "<their folder>" \
       --owner "<name / firm>" [--funds-workbook <path>] [--exclude "<regex>"] --example-registry
   ```
   It copies the collector, the Windows scripts, an empty `config/mdd_sources.yaml`, `HANDOVER.md`
   (filled in with the folder and owner), `CLAUDE.md`, and the reference notes into `docs/`. Then run
   `pip install -r requirements.txt` and `python -m playwright install chromium` (skip the second if a
   Chromium is already available; set `PLAYWRIGHT_CHROMIUM` to its path).
3. **Build the source registry**, one entry per fund in `config/mdd_sources.yaml`. Fields and the search
   order are in `references/registry-fields.md`.
   - Check `config/mdd_sources_example.yaml` first: 192 SA funds verified in October 2026. Copy the
     matching entries, set `isin` to the user's class, and **test each one**, because sites change.
   - For the rest, use `references/manager-notes.md` (what each manager's site does) and
     `references/scraping-guide.md` §4 (how to find where a site keeps its sheets).
   - Test one fund: `python -m fund_allocator collect --exclude '^(?!<Fund>)' --out <scratch folder>`.
4. **Agree the registry with the user** before scheduling. List funds with no source, funds using another
   share class's sheet, and any `ignore_robots` you'd need. robots.txt overrides need the user's explicit
   agreement; record it in HANDOVER.md §3.
5. **First full run** into their folder (or a test folder if you can't reach it). Show the tracker and
   explain the Exceptions sheet.
6. **Weekly schedule** on their machine: follow `references/scheduling.md`. Give the user the PowerShell
   commands with their real paths. They run it, not you.

## Running and maintaining

```bash
python -m fund_allocator collect --out "<MDD folder>" [--funds holdings.xlsx --sheet "<sheet>"] \
    [--exclude "<regex>"] [--aum-label "AUM held"]
```

- What a run does, the checks, the statuses and how to read the exceptions: `references/tracker-and-checks.md`.
- **Wrong document:** look at the PDF in `_rejected/`. A renamed fund gets the new name in `doc_names`
  (once the user confirms it, also `current_name`, so the tracker shows the new name). Otherwise fix
  the source.
- **Late:** the URL probably changed, or a platform copy stopped updating. Re-find the source; record what
  changed in HANDOVER.md §5.
- **Removing or adding funds:** edit `config/mdd_sources.yaml`. The tracker follows it, not the holdings
  workbook. Record removals in HANDOVER.md §3 so nobody adds them back.
- **Changing the code:** the collector lives in the project's `fund_allocator/`. Keep the checks; each one
  exists because of a real failure.

## Principles worth keeping (from `references/scraping-guide.md`)

- **Date the document by its content**, never by URL, folder or download date. Stale sheets come back
  with status 200.
- **The document must name the fund.** The right URL can serve the wrong fund.
- **Never fall back silently.** A visible gap is better than a wrong month that looks normal.
- **Don't defeat bot walls or CAPTCHAs.** Use another route, or ask the user to download that sheet into
  a folder and point `file:` at it.
- **Keep the evidence:** the manifest, `_rejected/`, reissued copies.

## Reference files

- `references/registry-fields.md`: every registry field, and how to find a fund's source.
- `references/manager-notes.md`: what each SA manager's and platform's site does; renamed funds; traps.
- `references/tracker-and-checks.md`: the run, the checks, the tracker columns and statuses.
- `references/scheduling.md`: weekly running on Windows (Task Scheduler) or macOS/Linux (cron).
- `references/scraping-guide.md`: the full field guide, rules R1–R10 (long; read §1, §4 and §9 first).
- `assets/sa_mdd_sources_example.yaml`: the 192-fund example registry.
- `assets/project/`: the project template (copied by `scripts/init_project.py`).
