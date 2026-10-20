# The source registry: `config/mdd_sources.yaml`

One entry per fund under `funds:`. **The tracker lists exactly these funds.** A holdings workbook only adds
an AUM column. An entry needs at least one of `url`, `urls`, `page`, `file`, `sanlam_fund`, `mandg_fund` or
`note`. An entry with only a `note` shows as "No source" with that note.

## Fields

| Field | Example | What it does |
|---|---|---|
| `name` | `Coronation Balanced Plus Fund` | The fund's name as the owner uses it. File names, AUM matching and the skip rule depend on it, so don't change it once MDDs are saved; use `current_name` instead. |
| `url` | `https://…/latest/CBPF` | One PDF link, tried as is. |
| `urls` | list | More links, or **templates** filled in for each month collected: `{yyyy} {mm} {yyyymm} {month}` (august) `{Month}` (August) `{mon} {Mon} {MON}` (aug/Aug/AUG) `{dd}` (last day) `{bdd}` (last weekday) `{next_yyyy} {next_mm}` (the following month, for upload folders). |
| `page` | `https://www.prescient.co.za/funds/other-funds/` | A web page that links the PDF. |
| `link_match` | `'{yyyy}-{mm}-abax-absolute-fund-mdd'` | Regex the link must match; it may contain the month templates. A fund-specific pattern never falls back to other PDFs on the page. |
| `render` | `true` | Load `page` in the headless browser (JavaScript sites). |
| `browser` | `true` | Always download through the headless browser (bot-protected sites, e.g. Ninety One). |
| `referer` | `https://www.amplify.co.za/` | Send this Referer (some document servers need it). |
| `sanlam_fund` | `Amplify SCI Equity Fund A1` | Look the MDD up in Sanlam Collective Investments' fact-sheet API (exact name and class). |
| `mandg_fund` | `M&G Balanced Fund` | Look the fact sheet up in M&G's all-funds list. |
| `file` | `manual/Fund.pdf` | A PDF downloaded by hand. |
| `isin` | `ZAE000165205` | The share class held. Shown in the tracker; also confirms renames. |
| `note` | free text | Shown in the tracker's Notes column. |
| `doc_names` | list | Other names the MDD may print (renamed fund, platform name). The name check accepts any of them. |
| `current_name` | `Vunani FR Enhanced Income Fund` | An owner-confirmed current name; the tracker shows it, with "previously …" in Notes. |
| `fund_manager` | `Veritas Asset Management` | Who actually manages the money, shown in the tracker's **Fund Manager** column. Set it from the MDD ("Investment manager", "About the fund manager", "Managed by"). For platform and multi-boutique ranges (Amplify, Nedgroup, PPS, Curate, Discovery, Fundrock/Prescient co-named funds) it is a third party, not the name on the fund. Without it the tracker uses the investment manager read from the MDD, which can be blank or, for funds with an offshore partner, name that partner. |
| `fund_folder` | `Coronation Top 20` | The fund's folder inside `<fund_manager>` in the owner's fund-document share. With `--fund-share`, each MDD is also copied to `<share>\<fund_manager>\<fund_folder>\MDDs\YYYY\YYYY-MM - <Fund>.pdf`. Fund folders are never created; a missing one is an exception. |
| `fund_path` | `Lyrical\Curate Global Quality Equity Fund` | The fund's folder relative to the share, only where it isn't under `<fund_manager>`. |
| `keep_name` | `true` | Don't switch to the MDD's name even when the ISIN confirms it (e.g. the MDD prints an *old* name). |
| `lag_days` | `60` | Days after month-end the MDD is normally up (default 30). Before this the fund is **Pending**, after it **Late**. |
| `frequency` | `quarterly` | MDDs only for March, June, September and December; other months show **Quarterly**. |
| `ignore_robots` | `true` | Download even though the site's robots.txt disallows it. **Only with the owner's explicit agreement**; record the decision in HANDOVER.md. |

## Finding a fund's source (work down the list; stop at the first stable, checkable route)

1. Look the fund up in `assets/sa_mdd_sources_example.yaml` (192 SA funds, verified Oct 2026). Copy the
   entry, but **check it still works** and set `isin` to the owner's class.
2. Find the manager in `references/manager-notes.md` and apply its pattern.
3. Fetch the manager's fund page: search the HTML for `.pdf`, `fact`, `mdd`, `minimum disclosure`. If the
   links aren't in the HTML, look in embedded JSON (`__NEXT_DATA__`, `self.__next_f.push`), or render the
   page (`render: true`) and watch its network calls for a JSON API.
4. Platforms (Momentum Wealth, PPS secure, Discovery by JSE code, Fundrock bcis.co.za) are second
   sources. They are current or frozen, never dated, so the content date matters.
5. Search the web for `"<fund name>" minimum disclosure document <year>` or the ISIN.
6. Ask the owner for a link, or have them download the PDF by hand into a folder and use `file:`.

Then test the entry on its own:
`python -m fund_allocator collect --exclude '^(?!<Fund name>)' --out <scratch folder>`.
Check that the PDF names the fund, the month is right and the ISIN is the owner's class, and set
`fund_manager` from what the MDD says.

## Share classes

The asset allocation is the same across share classes; only fees and performance differ. If the owner's
class sheet isn't published, another class's sheet for the same month is fine. Put the owner's class
ISIN in `isin:` and say which class the MDD is in `note:`.
