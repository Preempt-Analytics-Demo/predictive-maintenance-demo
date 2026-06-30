# run_demo.ps1
#
# WHY THIS SCRIPT EXISTS
# Docker containers have no access to the host desktop, so the simulator
# cannot open a browser directly. This wrapper runs the simulator via
# docker compose and then opens the drift report and GitHub Actions page
# on your machine automatically — no copy-paste required.
#
# HOW TO USE (PowerShell)
#   .\run_demo.ps1                       # default: 1,000 sudden-spike readings
#
# Pass extra arguments to override simulator defaults:
#   .\run_demo.ps1 --mode normal --n-readings 500

param([Parameter(ValueFromRemainingArguments)][string[]]$SimArgs)

$ActionsUrl = "https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo/actions"
$ReportFile = "reports\drift_report.html"

Write-Host ""
Write-Host "══════════════════════════════════════════════════════════════"
Write-Host "  PREEMPT ANALYTICS — DEMO RUN"
Write-Host "══════════════════════════════════════════════════════════════"
Write-Host ""

# ── Run the simulator ─────────────────────────────────────────────────────────
# Extra args passed to this script are forwarded to the simulator.
docker compose run --rm simulator --mode sudden-spike --n-readings 1000 @SimArgs

Write-Host ""
Write-Host "══════════════════════════════════════════════════════════════"
Write-Host "  Simulation complete. Opening results..."
Write-Host "══════════════════════════════════════════════════════════════"
Write-Host ""

# ── Open the drift report ─────────────────────────────────────────────────────
# detect_drift.py writes drift_report.html to ./reports/, which is a volume
# mount — the file already exists on your machine right now.
if (Test-Path $ReportFile) {
    Write-Host "  Drift report   -> $ReportFile"
    Start-Process (Resolve-Path $ReportFile)
} else {
    Write-Host "  No drift report at $ReportFile — was there enough data in the database?"
}

# ── Open GitHub Actions ───────────────────────────────────────────────────────
# If drift was detected, the background monitor triggers a retrain workflow
# within ~1 minute. The new run will appear in the Actions tab shortly.
Write-Host "  GitHub Actions -> $ActionsUrl"
Start-Process $ActionsUrl
Write-Host ""
