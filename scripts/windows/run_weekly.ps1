# Weekly MDD collection - run by the "Fund MDD weekly download" scheduled task.
# Downloads the latest MDDs into <OutFolder>\YYYY - MM\ and refreshes each month's MDD Tracker.
# With -FundShare, each MDD is also copied to its fund's folder there (<Fund> - YYYY-MM.pdf).
param(
    [Parameter(Mandatory = $true)][string]$OutFolder,
    [string]$FundsWorkbook = "",
    [string]$FundsSheet = "Holding Fund Totals",
    [string]$Exclude = "^MitonOptimal FR",
    [int]$RecentMonths = 2,
    # Fund folders (<manager>\<fund folder>\MDDs\YYYY) to copy each MDD into; skipped if not found.
    [string]$FundShare = 'E:\OneDrive - MitonOptimal Portfolio Management (Pty) Ltd\Linka Henning''s files - Asset Management (FRA-DD Documents)'
)

$ErrorActionPreference = "Continue"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repo

$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("weekly-{0:yyyy-MM-dd}.log" -f (Get-Date))

$python = Join-Path $repo ".venv\Scripts\python.exe"

# Pick up code and fund-source updates pushed to the repository (needs git and a git clone; skipped otherwise).
# If the update changed the required packages, install them before collecting.
if ((Get-Command git -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $repo ".git"))) {
    $before = (Get-FileHash requirements.txt).Hash
    "=== $(Get-Date -Format s) updating from GitHub" | Out-File -Append $log
    git pull --ff-only *>> $log
    if ((Get-FileHash requirements.txt).Hash -ne $before) {
        & $python -m pip install -r requirements.txt *>> $log
        & $python -m playwright install chromium *>> $log
    }
}
$cmd = @("-m", "fund_allocator", "collect",
         "--sources", "config\mdd_sources.yaml",
         "--out", $OutFolder,
         "--download-dir", (Join-Path $repo "data\downloads"),
         "--recent", $RecentMonths,
         "--aum-label", "MitonOptimal AUM")
if ($Exclude) { $cmd += @("--exclude", $Exclude) }
if ($FundShare -and (Test-Path -LiteralPath $FundShare)) { $cmd += @("--fund-share", $FundShare) }
if ($FundsWorkbook -and (Test-Path $FundsWorkbook)) { $cmd += @("--funds", $FundsWorkbook, "--sheet", $FundsSheet) }

"=== $(Get-Date -Format s) collecting into $OutFolder" | Out-File -Append $log
& $python @cmd *>> $log
"=== finished with exit code $LASTEXITCODE" | Out-File -Append $log

# Keep the last 12 weekly logs.
Get-ChildItem $logDir -Filter "weekly-*.log" | Sort-Object Name -Descending | Select-Object -Skip 12 | Remove-Item
