# open_results.ps1 — opens the drift report and GitHub Actions page in your browser.
#
# Run this after the simulator finishes:
#   docker compose run --rm simulator --mode sudden-spike --n-readings 1000
#   .\open_results.ps1

$Report  = "reports\drift_report.html"
$Actions = "https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo/actions"

if (Test-Path $Report) { Start-Process (Resolve-Path $Report) } else { Write-Host "No drift report yet at $Report" }
Start-Process $Actions
