# Fix list: mismatches for the owner and Linka

Things that don't line up between the tracker (`config/mdd_sources.yaml`), Linka Henning's Asset Management
folders and the buy list. None of them stops the weekly download; they are tidy-ups for when there is time.
Tick an item when it's done, and tell Claude so the config can follow (for a renamed folder, `fund_folder`
or `fund_manager` must change to match). Claude adds new items here as they are found.

Share: `E:\OneDrive - MitonOptimal Portfolio Management (Pty) Ltd\Linka Henning's files - Asset Management (FRA-DD Documents)`
Started 20 Oct 2026.

## 1. One fund, two folders

| Fund | Folder the tracker uses | Leftover folder | Suggested fix |
|---|---|---|---|
| Nedgroup Investments Global Equity | `Veritas Asset Management\Nedgroup Investments Global Equity Fund` | `Nedgroup\Nedgroup Global Equity Fund` | Move anything useful to the Veritas folder, then delete the Nedgroup one |
| Nedgroup Rainmaker | `Ninety One\Nedgroup Rainmaker Fund` (created 20 Oct 2026) | `Nedgroup\Nedgroup Rainmaker Fund` (empty DD and MDDs) | Delete the Nedgroup one |

## 2. Fund folder not under its manager

| Fund | Fund Manager in the tracker | Where the folder is | Suggested fix |
|---|---|---|---|
| Curate Global Quality Equity | Evenlode (empty folder created 20 Oct 2026) | `Lyrical Asset Management (Curate-Momentum)\Curate Global Quality Equity Fund` | Move the fund folder into `Evenlode` |

## 3. Folder names with typos

| Folder | Should be |
|---|---|
| `Franklin Templeton\Franklin US Opportunites Fund` | Franklin US Opportunities Fund |
| `Bateleur\Bateleur Market Neutral Prescienr RIHF` | Bateleur Market Neutral Prescient RIHF |
| `Omba\Omba Moderate Risk Global Allocattion Fund` (not tracked) | Omba Moderate Risk Global Allocation Fund |
| `Peregrine\Peregrine Capital Pure Hedge\Additioal information` | Additional information |

## 4. Folders that still use a fund's old name

Fundrock (FR) took over the BCI funds and, in Sep 2025, the IP funds; the MDDs now print "FR".

| Folder | Fund's name now |
|---|---|
| `Flagship\Flagship IP Flexible Value Fund` | Flagship FR Flexible Value Fund |
| `Flagship\Flagship IP Worldwide Flexible Fund` | Flagship FR Worldwide Flexible Feeder Fund |
| `Flagship\Flagship IP Worldwide Flexible FOF` | Flagship FR Worldwide Flexible Fund of Funds |
| `Fairtree\Fairtree Flexible Income` | Fairtree FR Income Plus Fund |
| `Old Mutual Wealth - OMI\Old Mutual RAFI All World Index Fund` | Old Mutual RAFI Select Global Index Feeder Fund (rename not yet confirmed) |
| `Otto1890\Otto1890 BCI Flexible Fund` | Otto1890 FR Flexible Income Fund |
| `36One Asset Management\36ONE BCI Equity` | 36ONE FR Equity Fund |
| `4D Wealth Management\4D BCI Moderate FoF` | 4D FR Moderate Fund of Funds |
| `Centaur\Centaur BCI Flexible` | Centaur FR Flexible Fund |
| `Ginsglobal Index Funds\BCI Ginsglobal Global Equity Index Feeder Fund` | FR GinsGlobal Global Equity Index Feeder Fund |
| `Granate\Granate BCI Balanced`, `Granate BCI Flexible`, `Granate BCI Multi Income` | Granate FR Balanced / Flexible / Multi Income |
| `Northstar Asset Management\Northstar BCI Income Fund`, `Northstar BCI Managed Fund` | Northstar FR Income / Managed |
| `Ranmore\BCI Ranmore Global Value Equity Feeder Fund` | FR Ranmore Global Value Equity Feeder Fund |
| `Reitway\Reitway BCI Global Property Fund` | Reitway FR Global Property Feeder Fund |
| `Visio Fund Management\Visio BCI Unconstrained Fixed Interest` | Visio FR Unconstrained Fixed Interest Fund |
| `Mi-Plan\Mi-Plan IP Global Macro Fund`, `Multi Asset IP Balanced Defensive` | Mi-Plan FR Global Macro / Multi Asset FR Balanced Defensive |

Optional: renaming is cosmetic. If a folder is renamed, Claude updates `fund_folder` to match.

## 5. Folders for funds the tracker no longer follows

| Folder | Why |
|---|---|
| `Riscura\Riscura BCI China Equity Feeder` | Fund wound up on 4 Sep 2026; removed from the tracker |
| `Sanlam\Sanlam Multi-Strategy Fund` | No public fact sheet; removed from the tracker |
| `Sprott Asset Management\Sprott Silver Miners & Physical Silver ETF` | Fact sheet site blocks automated downloads; removed from the tracker |

Archive or keep as you prefer. The 24 funds left out on 20 Oct 2026 (HANDOVER §6) also have folders; that
was a deliberate choice, so they aren't listed here.

## 6. Manager folders to tidy

| Folder | Issue |
|---|---|
| `Catalyx Capital` | A different firm from Catalyst Fund Managers (the tracker's Catalyst SCI Global Real Estate); check it's meant to be there |
| `Curate (look under Lyrical)` | Pointer folder; with Curate Global Quality under Evenlode, the note is now only partly true |
| `Lyrical Asset Management (Curate-Momentum)\New folder` | Empty, unnamed |
| `1 - UNALLOCATED` | Empty holding area; delete if no longer used |

## 7. Waiting for a decision

- `Cartesian\MitonOptimal BCI Interest Plus Fund` looks like the AUM workbook's "MitonOptimal FR Interest Plus
  Fund", which the owner sources directly. Keep it in Cartesian, move it, or leave it out?

## 8. Buy list names out of date (`!MitonOptimal Buy Lists\MitonOptimal Buy List MASTER.xlsx`)

| Buy list says | Name now |
|---|---|
| Peregrine Capital High Growth H4 RIHF / Pure Hedge H4 RIHF | Peregrine Capital High Growth / Pure Hedge Retail Hedge Fund (left H4 on 7 Aug 2025) |
| Fairtree Flexible Income Plus Prescient | Fairtree FR Income Plus Fund |
| Old Mutual RAFI All World Index Feeder | Old Mutual RAFI Select Global Index Feeder Fund |
