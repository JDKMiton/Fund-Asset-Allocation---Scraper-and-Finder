# One-time setup: installs the scraper's Python packages and a headless browser, then
# registers a weekly Windows scheduled task that downloads the latest MDDs into OneDrive.
#
# Run from PowerShell inside the repository folder:
#   powershell -ExecutionPolicy Bypass -File scripts\windows\setup_weekly_task.ps1
# Options:
#   -OutFolder "C:\Users\me\OneDrive - MitonOptimal\#Webscraper MDDs"   (default: found automatically)
#   -FundsWorkbook "C:\...\AUM_By_Holding_Fund_Model_Portfolio.xlsx"     (adds AUM to the trackers)
#   -Day Monday -Time 07:00
param(
    [string]$OutFolder = "",
    [string]$FundsWorkbook = "",
    [string]$Day = "Monday",
    [string]$Time = "07:00",
    [string]$TaskName = "Fund MDD weekly download"
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repo

# 1. Where the MDDs go: the OneDrive-synced "#Webscraper MDDs" folder.
if (-not $OutFolder) {
    $oneDrive = @($env:OneDriveCommercial, $env:OneDrive) | Where-Object { $_ } | Select-Object -First 1
    if (-not $oneDrive) { throw "OneDrive folder not found - pass -OutFolder ""<path to #Webscraper MDDs>""" }
    $OutFolder = Join-Path $oneDrive "#Webscraper MDDs"
}
New-Item -ItemType Directory -Force -Path $OutFolder | Out-Null
Write-Host "MDDs will be saved to: $OutFolder"

# 2. Python environment.
$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python 3.11+ is needed - install it from https://www.python.org/downloads/ (tick 'Add to PATH') and rerun." }
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $py.Source -m venv .venv }
$python = Join-Path $repo ".venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python -m playwright install chromium

# 3. Weekly scheduled task (runs as you, when you're logged on, so OneDrive syncs the files).
$runArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\windows\run_weekly.ps1`" -OutFolder `"$OutFolder`""
if ($FundsWorkbook) { $runArgs += " -FundsWorkbook `"$FundsWorkbook`"" }
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $runArgs -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $Time
# StartWhenAvailable: if the PC was off at the scheduled time, run as soon as it's back on.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Downloads the latest fund MDDs into $OutFolder and updates the MDD Trackers" -Force | Out-Null

Write-Host "Scheduled '$TaskName' every $Day at $Time."
Write-Host "Run it now with:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Logs are written to $repo\logs"
