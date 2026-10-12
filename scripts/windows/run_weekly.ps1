# Weekly MDD collection - run by the "Fund MDD weekly download" scheduled task.
# Downloads the latest MDDs into <OutFolder>\YYYY - MM\ and refreshes each month's MDD Tracker.
param(
    [Parameter(Mandatory = $true)][string]$OutFolder,
    [string]$FundsWorkbook = "",
    [string]$FundsSheet = "Holding Fund Totals",
    [string]$Exclude = "^MitonOptimal FR",
    [int]$RecentMonths = 2
)

$ErrorActionPreference = "Continue"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repo

$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("weekly-{0:yyyy-MM-dd}.log" -f (Get-Date))

# Pick up any updated fund sources pushed to the repository (ignored if git isn't available).
if (Get-Command git -ErrorAction SilentlyContinue) { git pull --ff-only *>> $log }

$python = Join-Path $repo ".venv\Scripts\python.exe"
$cmd = @("-m", "fund_allocator", "collect",
         "--sources", "config\mdd_sources.yaml",
         "--out", $OutFolder,
         "--download-dir", (Join-Path $repo "data\downloads"),
         "--recent", $RecentMonths)
if ($Exclude) { $cmd += @("--exclude", $Exclude) }
if ($FundsWorkbook -and (Test-Path $FundsWorkbook)) { $cmd += @("--funds", $FundsWorkbook, "--sheet", $FundsSheet) }

"=== $(Get-Date -Format s) collecting into $OutFolder" | Out-File -Append $log
& $python @cmd *>> $log
"=== finished with exit code $LASTEXITCODE" | Out-File -Append $log

# Keep the last 12 weekly logs.
Get-ChildItem $logDir -Filter "weekly-*.log" | Sort-Object Name -Descending | Select-Object -Skip 12 | Remove-Item
