# What a run does: checks, filing, tracker

`python -m fund_allocator collect --out "<MDD folder>" [--funds holdings.xlsx --sheet "Sheet1"]
[--exclude REGEX] [--recent 2] [--month "2026 - 08"] [--refetch] [--aum-label "AUM held"]`

## Steps

1. **Months:** the last `--recent` completed months (default 2; in October: August and September), plus
   any `--month`.
2. **Skip rule:** a fund whose MDD is already saved in every one of those month folders isn't searched
   (`--refetch` overrides this). Its tracker row reads "already saved - not searched again".
3. **Fetch:** each source in order (Sanlam or M&G API, then `url`/`urls`, then `page` links). Templates are
   expanded per month.
4. **Checks, on every download:**
   - **Real PDF:** at least 1 KB, with `%PDF-` in the first KB (sites answer missing files with HTML and
     status 200).
   - **Readable:** read in a worker process with a 120 s limit, so one bad PDF can't hang the run.
   - **Month:** from the masthead (top 15% of page 1, by position) first, then the text. Dates labelled
     issue, inception, launch, ESG/MSCI, TER period or payment are ignored unless nothing else is found;
     the file name is the last resort.
   - **Names the fund:** every distinctive word of `name` or of a `doc_names` entry must appear. If not,
     the file goes to `_rejected/` as **Wrong document**. A PDF without a text layer is accepted and listed
     as "Name not checked".
   - **Not stale:** an MDD more than 3 months older than the oldest month collected is rejected as a
     **Stale copy**.
5. **Filing:** `<MDD folder>\<YYYY - MM>\<name>.pdf`. **Never overwrites:**
   - the same content again counts as "unchanged" (bytes or text identical);
   - different content for an already filed month is kept beside it as
     `<name> (reissued YYYY-MM-DD).pdf` and flagged **Reissued**.
6. **Manifest:** `<MDD folder>\_manifest.csv` gets one row per download: fetched_at, fund, month, result
   (filed/unchanged/reissued/rejected), file, source, sha256, text_sha256, allocation_stamp, detail.
7. **Trackers:** `!MDD Tracker YYYY - MM.xlsx` in every month folder. The "!" sorts it to the top.
8. **Fund folders (optional, `--fund-share <folder>`):** every MDD in every month folder is also copied to
   `<folder>\<fund_manager>\<fund_folder>\MDDs\YYYY\YYYY-MM - <Fund>.pdf` (Fund = `current_name`, else
   `name`), so a fund's sheets sort by month. Earlier months are back-filled; nothing is overwritten (a
   different file is kept beside it as a reissue); a missing fund folder is reported, never created.

## The tracker

**Tracker sheet:** one row per fund, A–Z.

| Column | Contents |
|---|---|
| Fund | `current_name`, else the MDD's name if the MDD prints the fund's known ISIN, else `name` |
| Fund Manager | `fund_manager`, else the investment manager named in the MDD (blank if none is found) |
| AUM held | from the holdings workbook (label set by `--aum-label`) |
| ISIN | `isin`, else the first ISIN printed in the MDD |
| Fund AUM, Inception Date, Benchmark | read from the MDD by word position, with a text fallback; blank when unsure |
| Status | see below |
| MDD month | |
| Collected on | the day the MDD was first collected (manifest; else the saved file's date) |
| Usually available | how many days after month-end the fund's MDD usually appears, learned from earlier runs |
| Other months collected, File | |
| Fund folder copy | where this month's MDD was copied, relative to `--fund-share` (or why it wasn't) |
| Source, Notes | |

**Status values:**

| Status | Meaning |
|---|---|
| Collected | this month's MDD is in the folder |
| Pending | not posted yet; within the fund's learned timing plus a week, or `lag_days` (default 30) until 2 months are learned |
| Late | past the normal delay: look at it |
| Quarterly | quarterly fund, nothing due this month |
| No source | no download source configured |

**Summary sheet:** the counts per status, % collected and the number of exceptions.

**Exceptions sheet:** one row per issue, most serious first: Wrong document, Stale copy, Reissued, PDF
unreadable, Date unreadable, Not found, Fund folder copy failed, Fund folder missing, Late, Name not checked,
No source.

## Reading the results

- **Wrong document:** look at the PDF in `_rejected/`.
  - If it is the right fund under a new name, add that name to `doc_names` (and to HANDOVER.md §6).
  - Otherwise fix the source.
- **Reissued:** the manager published a corrected sheet. The tracker keeps the first one; ask the owner
  which to use.
- **Late:** check the manager's site by hand. A changed URL is the usual cause, then a platform copy that
  stopped updating.
- **Not found** for every fund of one manager points to a site or network problem (e.g. M&G's port 8082).
