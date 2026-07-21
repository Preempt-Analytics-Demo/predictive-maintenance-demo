# open_results.ps1 - opens the drift report and GitHub Actions page in your browser.
#
# Run this after the simulator finishes:
#   docker compose run --rm simulator --mode sudden-spike --n-readings 1000
#   .\open_results.ps1

$Report  = "reports\drift_report.html"
$Repo    = "Preempt-Analytics-Demo/predictive-maintenance-demo"
$WorkflowRuns = "https://github.com/$Repo/actions/workflows/retrain.yml"   # this one workflow's runs, not every workflow in the repo

# -- ANSI colour helpers ---------------------------------------------------------
# Same convention as preempt.ps1 - color marks what matters at a glance: green
# for a successful open, yellow for "didn't find what we expected."
$ESC = [char]27
$R   = "$ESC[0m"
$GRN = "$ESC[92m"
$YLW = "$ESC[93m"

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

# -- Spinner helper -------------------------------------------------------------
# Two frame sets: "dots" (small, single-glyph) for short/incidental waits,
# "circle" (the bigger dotsCircle animation) for the two waits that matter
# most here - opening the drift report and watching for the GitHub Actions
# run. Only call this after checking that output isn't redirected - a script
# piped to a log file has no way to overwrite a line, so this would
# otherwise write raw escape characters into that log instead of animating.
function Show-Spinner {
    param([int]$Seconds, [string]$Label, [string]$Style = "dots")
    # Built from [char] codepoints, not literal glyphs: this file has no BOM, and
    # Windows PowerShell 5.1 reads un-BOM'd script files using the system codepage
    # (Western European / 1252 here), not UTF-8 - literal Braille characters in
    # the source get silently corrupted into mojibake and fail to parse. Plain
    # ASCII codepoint math sidesteps the file-encoding question entirely.
    if ($Style -eq "circle") {
        $Frames = @(
            ([char]0x288E + ' '),
            ([char]0x280E + [char]0x2801),
            ([char]0x280A + [char]0x2811),
            ([char]0x2808 + [char]0x2831),
            (' ' + [char]0x2871),
            ([char]0x2880 + [char]0x2870),
            ([char]0x2884 + [char]0x2860),
            ([char]0x2886 + [char]0x2840)
        )
    } else {
        $Frames = @([char]0x280B, [char]0x2819, [char]0x2839, [char]0x2838, [char]0x283C, [char]0x2834, [char]0x2826, [char]0x2827, [char]0x2807, [char]0x280F)
    }
    $Ticks = [int]($Seconds * 1000 / 80)   # 80ms per frame - same cadence Ollama's CLI uses
    for ($i = 0; $i -lt $Ticks; $i++) {
        Write-Host -NoNewline ("`r  {0} {1}" -f $Frames[$i % $Frames.Length], $Label)
        Start-Sleep -Milliseconds 80
    }
    Write-Host -NoNewline ("`r" + (' ' * 70) + "`r")   # wipe the line before returning
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
if (-not [Console]::IsOutputRedirected) {
    Write-Host ""
    Show-Spinner -Seconds 8 -Label "Opening drift report" -Style circle
} else {
    Start-Sleep 2; Write-Host "  Opening in 6 seconds..."
    Start-Sleep 2; Write-Host "  Opening in 4 seconds..."
    Start-Sleep 2; Write-Host "  Opening in 2 seconds..."
    Start-Sleep 2
}
if (Test-Path $Report) {
    Write-Host "  ${GRN}$([char]0x2713)${R}  Opening drift report: $Report"
    Start-Process (Resolve-Path $Report)   # opens in default browser on Windows
} else {
    Write-Host "  ${YLW}$([char]0x26A0)  No drift report found${R} at $Report - run the simulator first."
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
Write-Host ""

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
    if (-not [Console]::IsOutputRedirected) {
        Show-Spinner -Seconds $PollInterval -Label "Watching for a new run" -Style circle
    } else {
        Start-Sleep $PollInterval
    }

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
        Write-Host "  ${GRN}$([char]0x2713)${R}  Opening the retraining job live: $JobUrl"
        Start-Process $JobUrl
    } else {
        $RunUrl = "https://github.com/$Repo/actions/runs/$NewRunId"
        Write-Host "  ${GRN}$([char]0x2713)${R}  Opening the retraining run: $RunUrl"
        Start-Process $RunUrl
    }
} else {
    # No new run within MaxWait - fall back to the workflow's own run list.
    # Still far more targeted than the repo's general Actions tab, which mixes
    # in the unrelated docker-publish workflow.
    Write-Host "  ${YLW}$([char]0x26A0)  No new run appeared${R} within ${MaxWait}s - opening the retraining workflow's run list instead."
    Write-Host "  Click the top row (the most recent run) to watch it live."
    Start-Process $WorkflowRuns
}
Write-Host ""
