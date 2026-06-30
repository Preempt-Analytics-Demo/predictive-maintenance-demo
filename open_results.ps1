# open_results.ps1 — opens the drift report and GitHub Actions page in your browser.
#
# Run this after the simulator finishes:
#   docker compose run --rm simulator --mode sudden-spike --n-readings 1000
#   .\open_results.ps1

$Report  = "reports\drift_report.html"
$Actions = "https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo/actions"

# ── Open the drift report immediately ────────────────────────────────────────
if (Test-Path $Report) {
    Write-Host ""
    Write-Host "  Opening drift report in your browser: $Report"
    Start-Process (Resolve-Path $Report)
} else {
    Write-Host "  No drift report yet at $Report — run the simulator first."
}

# ── Open GitHub Actions after a delay ────────────────────────────────────────
# The background monitor needs up to ~60 s to detect drift and push the retrain
# trigger, then GitHub Actions takes a few more seconds to start the workflow.
# Waiting 90 s here means the new run will be visible (or just starting) when
# the page opens, rather than appearing empty and confusing the user.
Write-Host ""
Write-Host "  GitHub Actions will open automatically in your browser once the"
Write-Host "  retraining workflow has had time to appear. Opening in 90 seconds..."
for ($i = 90; $i -ge 1; $i--) {
    Write-Host -NoNewline "`r  Opening in $i seconds...  "
    Start-Sleep 1
}
Write-Host "`r  Opening GitHub Actions: $Actions"
Start-Process $Actions
Write-Host ""
