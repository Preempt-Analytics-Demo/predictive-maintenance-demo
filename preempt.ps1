# preempt.ps1 — single entry point for the Preempt Analytics demo on Windows.
#
# WHY THIS FILE EXISTS
# Running the demo previously required remembering two separate commands:
# `docker compose run --rm simulator ...` and `.\open_results.ps1`. This script
# replaces both with a numbered menu — one keystroke per action, no typing.
#
# HOW TO RUN
#   .\preempt.ps1
#
# REQUIREMENTS
#   Docker Desktop must be running.  `choice.exe` (built into Windows) handles
#   the single-keypress input — no extra tools needed.

param()

# ── ANSI colour helpers ───────────────────────────────────────────────────────
# Windows Terminal and recent PowerShell support ANSI escape sequences natively.
# If your terminal shows literal "[1m" characters, run:  $env:TERM = "xterm-256color"
$ESC  = [char]27
$B    = "$ESC[1m"           # bold
$DIM  = "$ESC[2m"           # dim
$R    = "$ESC[0m"           # reset
$CYAN = "$ESC[96m"          # bright cyan  — section headers
$GRN  = "$ESC[92m"          # bright green — numbers
$YLW  = "$ESC[93m"          # yellow       — system actions

$ACTIONS = "https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo/actions"
$REPORT  = "reports\drift_report.html"

# ── Docker running? ───────────────────────────────────────────────────────────
# A missing Docker daemon means every compose command would fail with a confusing
# "Cannot connect to the Docker daemon" message. Catch it here with a plain hint.
function Test-Docker {
    $null = docker info 2>&1
    return $LASTEXITCODE -eq 0
}

# ── Menu loop ─────────────────────────────────────────────────────────────────
# choice.exe captures a single keypress without Enter — cleaner than Read-Host.
# Exit codes map 1:1 to the character list order (1→1, 2→2, …, Q→7).

:menu while ($true) {

    Clear-Host
    Write-Host ""
    Write-Host "  ${B}${CYAN} PREEMPT ANALYTICS${R}  --  control panel"
    Write-Host "  ${DIM}Predictive maintenance demo${R}"
    Write-Host ""
    Write-Host "  ${DIM}Simulate sensors${R}"
    Write-Host "  ${GRN}  1${R}  Sudden-spike readings    ${DIM}(abnormal -- triggers drift detection)${R}"
    Write-Host "  ${GRN}  2${R}  Normal readings          ${DIM}(baseline -- builds comparison dataset)${R}"
    Write-Host ""
    Write-Host "  ${DIM}Inspect results${R}"
    Write-Host "  ${GRN}  3${R}  Open drift report        ${DIM}(HTML -- last run's feature histograms)${R}"
    Write-Host "  ${GRN}  4${R}  Watch GitHub Actions     ${DIM}(live retraining pipeline)${R}"
    Write-Host "  ${GRN}  5${R}  Follow monitor output    ${DIM}(docker compose logs -f monitor)${R}"
    Write-Host ""
    Write-Host "  ${DIM}System${R}"
    Write-Host "  ${YLW}  6${R}  Restart all services     ${DIM}(pull latest image + docker compose up -d)${R}"
    Write-Host "  ${YLW}  Q${R}  Quit"
    Write-Host ""

    # choice /c lists the valid keys; /n suppresses the "[1,2,Q]?" prompt so our
    # menu line above is the only prompt the user sees.
    choice /c 123456Q /n /m "  Press a number or Q:  " 2>$null
    $sel = $LASTEXITCODE

    switch ($sel) {

        1 {
            # Sudden-spike mode: pushes sensor values outside the training distribution.
            # 1,000 readings gives Evidently enough current data for reliable KS tests.
            if (-not (Test-Docker)) { Write-Host "`n  Docker is not running. Start Docker Desktop first.`n"; pause; continue menu }
            Write-Host "`n  Generating 1,000 sudden-spike readings...`n"
            docker compose run --rm simulator --mode sudden-spike --n-readings 1000
            Write-Host "`n  Done. Choose option 3 to open the drift report.`n"
            pause
        }

        2 {
            # Normal mode: readings that match the training distribution.
            # Use this to build up the comparison dataset without triggering a retrain.
            if (-not (Test-Docker)) { Write-Host "`n  Docker is not running. Start Docker Desktop first.`n"; pause; continue menu }
            Write-Host "`n  Generating 500 normal readings...`n"
            docker compose run --rm simulator --mode normal --n-readings 500
            Write-Host "`n  Done.`n"
            pause
        }

        3 {
            # Open the HTML drift report from the last simulator run.
            # The file lives at reports\drift_report.html (host path).
            if (Test-Path $REPORT) {
                Write-Host "`n  Opening $REPORT in your browser...`n"
                Start-Process (Resolve-Path $REPORT)
            } else {
                Write-Host "`n  No report found at $REPORT -- run option 1 or 2 first.`n"
                pause
            }
        }

        4 {
            # Open the GitHub Actions page to watch the retraining workflow run live.
            Write-Host "`n  Opening GitHub Actions in your browser...`n"
            Start-Process $ACTIONS
        }

        5 {
            # Stream the monitor container's live output.
            # Ctrl+C exits the log stream; the monitor itself keeps running.
            if (-not (Test-Docker)) { Write-Host "`n  Docker is not running. Start Docker Desktop first.`n"; pause; continue menu }
            Write-Host "`n  Streaming monitor output (Ctrl+C to stop):`n"
            docker compose logs -f monitor
        }

        6 {
            # Pull the latest image from GHCR and restart all services.
            # Use this after a new version is published (e.g. after a model retrain).
            if (-not (Test-Docker)) { Write-Host "`n  Docker is not running. Start Docker Desktop first.`n"; pause; continue menu }
            Write-Host "`n  Pulling latest image and restarting services...`n"
            docker compose pull
            docker compose up -d
            Write-Host "`n  Services restarted.`n"
            pause
        }

        7 {
            # Q maps to exit code 7 in the choice /c 123456Q list
            Write-Host ""
            break menu
        }
    }
}
