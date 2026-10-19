# Running it weekly on the owner's computer

Downloads have to run where the owner's network can reach the managers' sites. Some, like M&G's port 8082,
are blocked from cloud sandboxes. The MDD folder is **whatever the owner chose**: a local folder, a
OneDrive or SharePoint-synced folder, or a network drive.

## Windows (Task Scheduler)

Give the owner these steps, filling in their paths.

1. **Install Python 3.11–3.14** from python.org (3.13 recommended), ticking "Add python.exe to PATH". Very
   new versions such as 3.15 may lack ready-made packages for PyYAML, which then fails to build.
2. **Put the project somewhere stable**, e.g. `C:\Tools\MDD-Collector`. Without git, download the ZIP and
   extract it there. Later updates are the same: copy over it, choose **Replace**, and keep `.venv`.
3. Open **PowerShell normally** (not "Run as administrator", which starts in `C:\Windows\System32`), then:
   ```powershell
   cd C:\Tools\MDD-Collector
   powershell -ExecutionPolicy Bypass -File scripts\windows\setup_weekly_task.ps1 `
       -OutFolder "D:\Fund MDDs" `
       -FundsWorkbook "C:\path\to\holdings.xlsx" -FundsSheet "Sheet1" `
       -Exclude "^MyFirm " -Day Monday -Time 07:00
   ```
   - Only `-OutFolder` matters; the script asks for it if it's left out.
   - The others are optional: the holdings workbook fills the AUM column, and `-Exclude` skips funds the
     owner sources themselves.
   - The script creates `.venv`, installs the packages and Chromium, and registers the task "Fund MDD
     weekly download". The task runs when the user is logged on; if the PC was off, it runs at the next
     logon.
4. **Run it once now:** `Start-ScheduledTask -TaskName "Fund MDD weekly download"`. Check
   `logs\weekly-YYYY-MM-DD.log`; the end says `N funds: MDDs for X …` and lists the exceptions.
   PowerShell doesn't need to stay open.
5. To change the AUM column heading, edit `"--aum-label"` in `scripts\windows\run_weekly.ps1`.

**Common problems:**
- "Python 3.11–3.14 is needed": install 3.13 and rerun.
- "path not found": the command was run from `System32`; `cd` into the project first.
- The task runs but nothing appears in OneDrive: OneDrive must be signed in and running.

## macOS / Linux (cron)

```bash
cd ~/mdd-collector && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt \
  && .venv/bin/python -m playwright install chromium
crontab -e   # then add (Mondays 07:00):
0 7 * * 1 cd ~/mdd-collector && .venv/bin/python -m fund_allocator collect --out "$HOME/Fund MDDs" >> logs/weekly.log 2>&1
```
