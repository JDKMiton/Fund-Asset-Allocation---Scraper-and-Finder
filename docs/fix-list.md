# Fix list: moved to the share

Since 20 Oct 2026 the list of mismatches between Linka's folders, the MDD tracker and the MDDs is a
spreadsheet the owner and Linka work from:

`E:\OneDrive - MitonOptimal Portfolio Management (Pty) Ltd\Linka Henning's files - Asset Management (FRA-DD Documents)\# TO DO LIST\Folder and tracker fixes.xlsx`

Sheet "To do", one row per item: Area, What, Where, Now, Should be / action, Status (Open / Done), Done on,
Notes. Each weekly run moves the rows marked Done to the "Done" sheet (with the date), so a Done row stays
visible until the next Monday run.

For Claude:
- Add a row at the bottom whenever a scan or change finds a new mismatch. Open the workbook with openpyxl
  and append; never rewrite it, re-sort it or touch the Status, Done on and Notes the owner and Linka fill in.
- Check the "Done" sheet for rows the config must follow; when a row is Done, make the config match (`fund_folder`, `fund_manager`, `fund_path`, `current_name`) and
  say so in HANDOVER's learning log.
