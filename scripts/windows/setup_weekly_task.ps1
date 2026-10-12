# One-time setup (safe to rerun): installs the scraper's Python packages and a headless browser, then
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

# 2. Python environment. Needs Python 3.11-3.14: brand-new versions (e.g. 3.15) don't have
#    ready-built packages yet and would need a C++ compiler.
function Test-Step($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE) - see the messages above." } }

$base = $null
$ErrorActionPreference = "Continue"   # probing missing versions writes to stderr; don't treat as fatal
foreach ($v in "3.13", "3.12", "3.14", "3.11") {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try { & py "-$v" -c "import sys" 2>&1 | Out-Null } catch { }
        if ($LASTEXITCODE -eq 0) { $base = @("py", "-$v"); break }
    }
}
if (-not $base -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $ver = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
    if ([version]$ver -ge [version]"3.11" -and [version]$ver -lt [version]"3.15") { $base = @("python") }
}
$ErrorActionPreference = "Stop"
if (-not $base) {
    throw "Python 3.11-3.14 is needed (3.13 recommended). Install Python 3.13 from https://www.python.org/downloads/ and rerun this script."
}
Write-Host "Using Python: $($base -join ' ')"

$python = Join-Path $repo ".venv\Scripts\python.exe"
if (Test-Path $python) {
    $venvVer = & $python -c "import sys; print('%d.%d' % sys.version_info[:2])"
    if ([version]$venvVer -ge [version]"3.15") { Write-Host "Removing old environment built with Python $venvVer"; Remove-Item -Recurse -Force ".venv" }
}
if (-not (Test-Path $python)) {
    if ($base.Count -gt 1) { & $base[0] $base[1] -m venv .venv } else { & $base[0] -m venv .venv }
    Test-Step "Creating the Python environment"
}
& $python -m pip install --upgrade pip
Test-Step "Upgrading pip"
& $python -m pip install -r requirements.txt
Test-Step "Installing the Python packages"
& $python -m playwright install chromium
Test-Step "Installing the headless browser"

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
