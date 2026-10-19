# Handover: MDD collector and tracker

This file is the project's memory: the owner's decisions, what each manager's website does, which funds
need care, and what has gone wrong before. It is a data source as well as a handover.

## Read this first: the rule for every scan or scrape

1. **Before** any scan, scrape, source change or tracker rebuild, read this whole file. Check §3 (owner
   decisions), §5 (site notes) and §7 (open issues) for the funds involved.
2. Do the work.
3. **After** the work, update this file with anything new you learned: a site that changed, a fund
   renamed, a source that served the wrong or a stale document, a new owner decision, an ISIN confirmed.
   Fix the section it belongs to, and add a dated line to the learning log (§10). If nothing new was
   learned, add a one-line log entry saying so.
4. Commit this file (if the project is in git) with the change it describes.

General rules: [`docs/sa-factsheet-scraping-guide.md`](docs/sa-factsheet-scraping-guide.md). Where it and
this file disagree, this file records what was actually seen for *these* funds and wins.

---

## 1. What this is

- **Owner:** {{OWNER}}
- **Job:** download the latest MDD (minimum disclosure document / fact sheet) of every fund in
  `config/mdd_sources.yaml`, file each one under the month it reports on, and keep an MDD Tracker per
  month showing what is collected and what is outstanding.

## 2. How it runs

| Item | Value |
|---|---|
| Project folder | {{PROJECT_DIR}} |
| MDD folder (chosen by the owner) | {{OUT_FOLDER}} |
| Fund list | `config/mdd_sources.yaml`: **this file defines the tracker** |
| Holdings / AUM workbook | {{FUNDS_WORKBOOK}} (only fills the AUM column; optional) |
| Excluded funds | {{EXCLUDE}} |
| Schedule | {{SCHEDULE}} |
| Manual run | `python -m fund_allocator collect --out "{{OUT_FOLDER}}"` (add `--funds <workbook>` for AUM) |

What one run does, the checks it applies, the tracker statuses and the exception kinds are described in
`docs/tracker-and-checks.md`. In short: last two completed months; a fund already saved
for both months is skipped; every download must be a real PDF that names the fund and carries a
readable month; nothing filed is ever overwritten; `_manifest.csv` and `_rejected/` keep the evidence.

## 3. Owner decisions (follow these; ask before changing them)

| Date | Decision |
|---|---|
| {{DATE}} | MDDs are saved in {{OUT_FOLDER}}. |

## 4. Where things are

- `config/mdd_sources.yaml`: the source registry (fields in `docs/registry-fields.md`).
- `fund_allocator/`: the collector (`collector.py`), downloads (`scraper.py`), fund facts (`facts.py`),
  time-limited PDF reading (`pdfinfo.py`).
- `<MDD folder>\_manifest.csv`, `<MDD folder>\_rejected\`: evidence; never delete them during a run.

## 5. Site notes (what was actually seen for these funds)

Start from `docs/manager-notes.md` and record here what differs for these funds.

## 6. Renamed funds

| Name in the config | Now printed as | How confirmed |
|---|---|---|

## 7. Open issues and questions for the owner

- (none yet)

## 8. ISINs: where they come from

- `isin:` in the config wins; otherwise the first ISIN printed in the MDD is used.

## 9. Notes for other agents (e.g. an asset-allocation agent)

- PDFs: `<MDD folder>\<YYYY - MM>\<Fund>.pdf`, filed under the month the MDD reports on.
- `_manifest.csv` has each file's sha256, source and allocation stamp ("Asset allocation as at …").

## 10. Learning log (newest first; add a line after every scan or change)

- **{{DATE}}:** Project set up from the sa-fund-mdd-collector skill.
