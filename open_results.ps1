# open_results.ps1 - opens the drift report and GitHub Actions page in your browser.
#
# Run this after the simulator finishes:
#   docker compose run --rm simulator --mode sudden-spike --n-readings 1000
#   .\open_results.ps1

$Report  = "reports\drift_report.html"
$Repo    = "Preempt-Analytics-Demo/predictive-maintenance-demo"
$WorkflowRuns = "https://github.com/$Repo/actions/workflows/retrain.yml"   # this one workflow's runs, not every workflow in the repo

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
# with no run yet, which reads as "did this actually work?" to a first-time
# user - so the wait itself is explained up front, in plain terms, before the
# countdown starts (Redish: say what's happening and why before the numbers).
Write-Host ""
Write-Host "  Please be patient - retraining takes a little while to fire."
Write-Host "  How long depends on your machine's speed, not on anything going wrong."
Write-Host "  GitHub Actions will open as soon as the run is ready to watch."
Write-Host ""
Write-Host "  Opening in 240 seconds..."
Start-Sleep 60; Write-Host "  Opening in 180 seconds..."
Start-Sleep 60; Write-Host "  Opening in 120 seconds..."
Start-Sleep 60; Write-Host "  Opening in 60 seconds..."
Start-Sleep 30; Write-Host "  Opening in 30 seconds..."
Start-Sleep 30

# -- Find the specific run, not just the workflow list -------------------------
# A run only gets a numeric ID once GitHub actually starts it - there is no way
# to know that ID ahead of time, but by now the run has had ~4 minutes to start,
# so asking the (public, unauthenticated) GitHub API for the most recent run of
# this one workflow reliably finds it.
try {
    $Response = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/actions/workflows/retrain.yml/runs?per_page=1" -ErrorAction Stop
    if ($Response.workflow_runs.Count -gt 0) {
        $RunUrl = "https://github.com/$Repo/actions/runs/$($Response.workflow_runs[0].id)"
        Write-Host "  Opening the retraining run directly: $RunUrl"
        Start-Process $RunUrl
    } else {
        Write-Host "  No run found yet - opening the retraining workflow's run list instead."
        Write-Host "  Click the top row (the most recent run) to watch it live."
        Start-Process $WorkflowRuns
    }
} catch {
    # API call failed - fall back to the workflow's own run list. Still far more
    # targeted than the repo's general Actions tab, which mixes in the unrelated
    # docker-publish workflow.
    Write-Host "  Couldn't fetch the specific run - opening the retraining workflow's run list instead."
    Write-Host "  Click the top row (the most recent run) to watch it live."
    Start-Process $WorkflowRuns
}
Write-Host ""
