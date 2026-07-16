# open_results.ps1 - opens the drift report and GitHub Actions page in your browser.
#
# Run this after the simulator finishes:
#   docker compose run --rm simulator --mode sudden-spike --n-readings 1000
#   .\open_results.ps1

$Report  = "reports\drift_report.html"
$Repo    = "Preempt-Analytics-Demo/predictive-maintenance-demo"
$WorkflowRuns = "https://github.com/$Repo/actions/workflows/retrain.yml"   # this one workflow's runs, not every workflow in the repo

# -TimeoutSec caps how long the request itself can sit waiting: without it, a
# request that gets silently dropped by a firewall, proxy, or VPN (rather than
# actively refused) can hang far longer than any timeout this script tries to
# enforce around it - Windows' own TCP retry behavior alone can stretch that
# to several minutes on a locked-down network, with nothing in PowerShell to
# cut it off on its own.
function Get-LatestRunId {
    try {
        $Response = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/actions/workflows/retrain.yml/runs?per_page=1" -TimeoutSec 10 -ErrorAction Stop
        if ($Response.workflow_runs.Count -gt 0) { return $Response.workflow_runs[0].id }
    } catch { }
    return $null
}

# -- Baseline: remember the run that exists before this trigger fires ---------
# Captured as the very first thing the script does, before the drift-report
# section below can spend any time - so a fast retraining pipeline can never
# race past this check. Comparing against this baseline later is how we tell a
# genuinely NEW run apart from re-opening whatever ran last time, which is
# what happened without it: the script grabbed "the most recent run" before
# the new one existed yet, and opened an old, already-finished run instead.
$BaselineRunId = Get-LatestRunId

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

# -- Watch for the new retraining run -------------------------------------------
# A fixed wait can't work here: the slow part is uploading the training data to
# DagsHub, and that upload grows with every simulated reading ever generated in
# this environment - a few minutes early in a demo's life, longer the more the
# demo has been used since. Rather than guess a duration, poll the (public,
# unauthenticated) GitHub API every 20s for a run newer than the baseline
# above, and open it the instant it exists - accurate no matter how long the
# real wait turns out to be.
Write-Host ""
Write-Host "  Watching GitHub for the new retraining run - this can take anywhere from"
Write-Host "  about a minute to several minutes. It depends on how much training data"
Write-Host "  has to upload, not on anything going wrong. You'll be taken there the"
Write-Host "  moment it's ready; no need to do anything."

$PollInterval = 20
$MaxWait = 600   # 10-minute ceiling - generous, but bounded so this can't hang forever
$StartTime = Get-Date
$NextHeartbeat = 60
$NewRunId = $null

# Measures real wall-clock time (now minus StartTime), not sleep time added up
# - a counter that only counted PollInterval sleeps would understate the true
# wait whenever Get-LatestRunId itself takes a while (slow network, a retry,
# anything short of the -TimeoutSec cutoff above), so MaxWait would stop being
# a real ceiling exactly when it matters most.
$Elapsed = 0
while ($Elapsed -lt $MaxWait) {
    Start-Sleep $PollInterval

    $CurrentRunId = Get-LatestRunId
    if ($CurrentRunId -and $CurrentRunId -ne $BaselineRunId) {
        $NewRunId = $CurrentRunId
        break
    }

    $Elapsed = [int]((Get-Date) - $StartTime).TotalSeconds

    # Heartbeat every ~60s so a long wait doesn't look like the terminal froze.
    if ($Elapsed -ge $NextHeartbeat) {
        Write-Host "  Still watching... (${Elapsed}s so far - still normal)"
        $NextHeartbeat += 60
    }
}

if ($NewRunId) {
    # A run's summary page still requires clicking into a job to see anything
    # live - html_url on the job itself is that exact click already followed,
    # landing on the same run+job URL a person would land on by hand.
    try {
        $Jobs = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/actions/runs/$NewRunId/jobs" -TimeoutSec 10 -ErrorAction Stop
        $JobUrl = $Jobs.jobs[0].html_url
    } catch { $JobUrl = $null }

    if ($JobUrl) {
        Write-Host "  Opening the retraining job live: $JobUrl"
        Start-Process $JobUrl
    } else {
        $RunUrl = "https://github.com/$Repo/actions/runs/$NewRunId"
        Write-Host "  Opening the retraining run: $RunUrl"
        Start-Process $RunUrl
    }
} else {
    # No new run within MaxWait - fall back to the workflow's own run list.
    # Still far more targeted than the repo's general Actions tab, which mixes
    # in the unrelated docker-publish workflow.
    Write-Host "  No new run appeared within ${MaxWait}s - opening the retraining workflow's run list instead."
    Write-Host "  Click the top row (the most recent run) to watch it live."
    Start-Process $WorkflowRuns
}
Write-Host ""
