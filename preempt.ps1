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

# -- ASCII art banner (optional) -------------------------------------------------
# Mirrors preempt.sh's ASCII_ART -- printed once during the boot sequence below,
# right after the BOOT flicker. Single-quoted here-string so the embedded quotes
# and backslashes in the art are read literally, not as PowerShell syntax.
$AsciiArt = @'
 ______ ______  ______  ______  __    __  ______ ______
/\  == /\  == \/\  ___\/\  ___\/\ "-./  \/\  == /\__  _\
\ \  _-\ \  __<\ \  __\\ \  __\\ \ \-./\ \ \  _-\/_/\ \/
 \ \_\  \ \_\ \_\ \_____\ \_____\ \_\ \ \_\ \_\    \ \_\
  \/_/   \/_/ /_/\/_____/\/_____/\/_/  \/_/\/_/     \/_/

 ______  __   __  ______  __      __  __  ______ __  ______  ______
/\  __ \/\ "-.\ \/\  __ \/\ \    /\ \_\ \/\__  _/\ \/\  ___\/\  ___\
\ \  __ \ \ \-.  \ \  __ \ \ \___\ \____ \/_/\ \\ \ \ \ \___\ \___  \
 \ \_\ \_\ \_\\"\_\ \_\ \_\ \_____\/\_____\ \ \_\\ \_\ \_____\/\_____\
  \/_/\/_/\/_/ \/_/\/_/\/_/\/_____/\/_____/  \/_/ \/_/\/_____/\/_____/
'@

# ── Docker running? ───────────────────────────────────────────────────────────
# A missing Docker daemon means every compose command would fail with a confusing
# "Cannot connect to the Docker daemon" message. Catch it here with a plain hint.
function Test-Docker {
    $null = docker info 2>&1
    return $LASTEXITCODE -eq 0
}

# -- Spinner helper -------------------------------------------------------------
# Same rotating-glyph animation open_results.ps1 uses. A couple of seconds of
# motion right after the keypress signals "got it, doing something" instead of
# a blank pause before the command's own output starts. choice.exe already
# requires a real console, so there's no non-interactive fallback to guard for.
# Built from [char] codepoints, not literal glyphs -- this file has no BOM, and
# Windows PowerShell 5.1 reads un-BOM'd script files using the system codepage,
# not UTF-8, so literal Braille characters in the source would get corrupted.
function Show-Spinner {
    param([int]$Seconds, [string]$Label)
    $Frames = @([char]0x280B, [char]0x2819, [char]0x2839, [char]0x2838, [char]0x283C, [char]0x2834, [char]0x2826, [char]0x2827, [char]0x2807, [char]0x280F)
    $Ticks = [int]($Seconds * 1000 / 80)   # 80ms per frame
    for ($i = 0; $i -lt $Ticks; $i++) {
        Write-Host -NoNewline ("`r  {0} {1}" -f $Frames[$i % $Frames.Length], $Label)
        Start-Sleep -Milliseconds 80
    }
    Write-Host -NoNewline ("`r" + (' ' * 70) + "`r")   # wipe the line before returning
}

# -- Boot sequence ----------------------------------------------------------------
# Runs once when the script starts, before the menu loop below (which clears and
# redraws on every return trip) -- a short "system coming online" beat that sets
# the control-panel tone before the plain numbered menu takes over. Purely
# atmospheric; skipping it changes nothing about how the menu itself works.
function Start-BootSequence {
    param([string]$AsciiArt)

    # Flicker "BOOT" twice -- a fast clear/print/clear cycle reads as a terminal
    # still warming up, before the real banner replaces it.
    for ($i = 0; $i -lt 2; $i++) {
        Clear-Host
        Write-Host "  BOOT" -NoNewline
        Start-Sleep -Milliseconds 100
        Clear-Host
        Start-Sleep -Milliseconds 100
    }

    # Custom logo, if one has been dropped into $AsciiArt above.
    if ($AsciiArt) {
        Write-Host ""
        Write-Host $AsciiArt
        Write-Host ""
    }

    # Typewriter the uplink line one character at a time -- same builds-
    # anticipation trick as the spinners, just for this one-time moment.
    $Msg = "Initializing uplink to Preempt Analytics prediction engine . ."
    Write-Host "  " -NoNewline
    foreach ($ch in $Msg.ToCharArray()) {
        Write-Host $ch -NoNewline -ForegroundColor Cyan
        Start-Sleep -Milliseconds 15
    }
    Write-Host ""

    # Loading bar -- 24 blocks, fills left to right. [char]0x2588 (not a literal
    # glyph), same BOM/codepage reason as Show-Spinner above.
    Write-Host "`n  [" -NoNewline
    for ($k = 0; $k -lt 24; $k++) {
        Write-Host ([char]0x2588) -NoNewline -ForegroundColor Green
        Start-Sleep -Milliseconds 30
    }
    Write-Host "]"
    Start-Sleep -Milliseconds 300
}

Start-BootSequence -AsciiArt $AsciiArt

# ── Menu loop ─────────────────────────────────────────────────────────────────
# choice.exe captures a single keypress without Enter — cleaner than Read-Host.
# Exit codes map 1:1 to the character list order (1→1, 2→2, …, Q→7).

:menu while ($true) {

    Clear-Host
    Write-Host ""
    Write-Host "  ${B}${CYAN} PREEMPT ANALYTICS${R}  --  control panel"
    Write-Host "  ${DIM}Predictive maintenance demo${R}"
    Write-Host ""
    Write-Host "  ${DIM}Run${R}"
    Write-Host "  ${GRN}  1${R}  Smoke Test               ${DIM}(verify the API is connected)${R}"
    Write-Host "  ${GRN}  2${R}  Full Retraining Loop     ${DIM}(simulate drift, watch it retrain)${R}"
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
            # Smoke test: confirms the simulator can reach the API end-to-end.
            # Matches the README's own "Setup -- three commands" step 3 exactly.
            Show-Spinner -Seconds 2 -Label "Spinning up simulation engine"
            if (-not (Test-Docker)) { Write-Host "`n  Docker is not running. Start Docker Desktop first.`n"; pause; continue menu }
            Write-Host "`n  Running smoke test -- verifying the simulator can reach the API...`n"
            docker compose run --rm simulator --mode normal --n-readings 500 --pause
            Write-Host "`n  Smoke test complete -- the API is connected. Choose option 3 to view the drift report.`n"
            pause
        }

        2 {
            # Full retraining loop: generates abnormal readings, then open_results.ps1
            # opens the drift report and polls for + opens the specific GitHub Actions run.
            # Matches the README's "Trigger the full retraining loop" section exactly.
            Show-Spinner -Seconds 2 -Label "Engaging full retraining sequence"
            if (-not (Test-Docker)) { Write-Host "`n  Docker is not running. Start Docker Desktop first.`n"; pause; continue menu }
            Write-Host "`n  Running the full retraining loop -- this will take 1-5 minutes. Don't close this window.`n"
            docker compose run --rm simulator --mode sudden-spike --n-readings 1000 --demo
            if ($?) { .\open_results.ps1 }
            pause
        }

        3 {
            # Open the HTML drift report from the last simulator run.
            # The file lives at reports\drift_report.html (host path).
            Show-Spinner -Seconds 2 -Label "Initializing drift report"
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
            Show-Spinner -Seconds 2 -Label "Establishing uplink to GitHub Actions"
            Write-Host "`n  Opening GitHub Actions in your browser...`n"
            Start-Process $ACTIONS
        }

        5 {
            # Stream the monitor container's live output.
            # Ctrl+C exits the log stream; the monitor itself keeps running.
            Show-Spinner -Seconds 2 -Label "Engaging live monitoring feed"
            if (-not (Test-Docker)) { Write-Host "`n  Docker is not running. Start Docker Desktop first.`n"; pause; continue menu }
            Write-Host "`n  Streaming monitor output (Ctrl+C to stop):`n"
            docker compose logs -f monitor
        }

        6 {
            # Pull the latest image from GHCR and restart all services.
            # Use this after a new version is published (e.g. after a model retrain).
            Show-Spinner -Seconds 2 -Label "Powering up services"
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
