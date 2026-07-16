# open_results.ps1 - opens the drift report and GitHub Actions page in your browser.
#
# Run this after the simulator finishes:
#   docker compose run --rm simulator --mode sudden-spike --n-readings 1000
#   .\open_results.ps1

$Report  = "reports\drift_report.html"
$Actions = "https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo/actions"

# -- Open the drift report after a short delay --------------------------------
# The HTML report is written the moment the simulator exits - it is ready now.
# An 8-second pause gives you time to read the terminal output (which shows the
# per-feature drift table) before the browser takes focus away from this window.
Write-Host ""
Write-Host "  The HTML report shows per-feature drift histograms and the overall verdict."
Write-Host "  Opening in your browser in 8 seconds..."
Start-Sleep 2; Write-Host "  Opening in 6 seconds..."
Start-Sleep 2; Write-Host "  Opening in 4 seconds..."
Start-Sleep 2; Write-Host "  Opening in 2 seconds..."
Start-Sleep 2
if (Test-Path $Report) {
    Write-Host "  Opening drift report: $Report"
    Start-Process (Resolve-Path $Report)   # opens in default browser on Windows
} else {
    Write-Host "  No drift report found at $Report - run the simulator first."
}

# -- Open GitHub Actions after a delay -----------------------------------------
# Measured in practice, not estimated: the monitor's own check interval, the
# export + DagsHub upload, and GitHub Actions picking up the push each add
# real time - the workflow is reliably visible and running by ~4 minutes, not
# the 90 s this used to wait. Opening earlier just shows an empty Actions page
# with no run yet, which reads as "did this actually work?" to a first-time user.
Write-Host ""
Write-Host "  GitHub Actions will open automatically once the retraining workflow"
Write-Host "  has had time to appear (this reliably takes a few minutes end to end)."
Write-Host "  Opening in 240 seconds..."
Start-Sleep 60; Write-Host "  Opening in 180 seconds..."
Start-Sleep 60; Write-Host "  Opening in 120 seconds..."
Start-Sleep 60; Write-Host "  Opening in 60 seconds..."
Start-Sleep 30; Write-Host "  Opening in 30 seconds..."
Start-Sleep 30
Write-Host "  Opening GitHub Actions: $Actions"
Start-Process $Actions
Write-Host ""
