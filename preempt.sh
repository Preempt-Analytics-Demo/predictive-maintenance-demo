#!/usr/bin/env bash
# preempt.sh — single entry point for the Preempt Analytics demo on macOS/Linux.
#
# WHY THIS FILE EXISTS
# Running the demo previously required remembering two separate commands:
# `docker compose run --rm simulator ...` and `./open_results.sh`.  This script
# replaces both with a numbered menu — one keystroke per action, no typing.
#
# HOW TO RUN
#   chmod +x preempt.sh && ./preempt.sh
#
# REQUIREMENTS
#   Docker must be running.  Uses POSIX read + stty for single-keypress input
#   so it works without any extra tools on macOS and Linux.

set -euo pipefail

# ── ANSI colour helpers ───────────────────────────────────────────────────────
# Most modern terminals support these escape sequences.  If you see literal
# "[1m" characters, your TERM variable may not be set to xterm-256color.
ESC=$'\033'
B="${ESC}[1m"          # bold
DIM="${ESC}[2m"        # dim
R="${ESC}[0m"          # reset
CYAN="${ESC}[96m"      # bright cyan  — section headers
GRN="${ESC}[92m"       # bright green — numbers
YLW="${ESC}[93m"       # yellow       — system actions

ACTIONS="https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo/actions"
REPORT="reports/drift_report.html"

# ── ASCII art banner (optional) ───────────────────────────────────────────────
# Drop your own ASCII-art rendering of "PREEMPT" here — a figlet font,
# https://www.asciiart.eu, hand-drawn, whatever fits. Printed once during the
# boot sequence below, right after the BOOT flicker.
ASCII_ART=' ______ ______  ______  ______  __    __  ______ ______               
/\  == /\  == \/\  ___\/\  ___\/\ "-./  \/\  == /\__  _\              
\ \  _-\ \  __<\ \  __\\ \  __\\ \ \-./\ \ \  _-\/_/\ \/              
 \ \_\  \ \_\ \_\ \_____\ \_____\ \_\ \ \_\ \_\    \ \_\              
  \/_/   \/_/ /_/\/_____/\/_____/\/_/  \/_/\/_/     \/_/              
                                                                      
 ______  __   __  ______  __      __  __  ______ __  ______  ______   
/\  __ \/\ "-.\ \/\  __ \/\ \    /\ \_\ \/\__  _/\ \/\  ___\/\  ___\  
\ \  __ \ \ \-.  \ \  __ \ \ \___\ \____ \/_/\ \\ \ \ \ \___\ \___  \ 
 \ \_\ \_\ \_\\"\_\ \_\ \_\ \_____\/\_____\ \ \_\\ \_\ \_____\/\_____\
  \/_/\/_/\/_/ \/_/\/_/\/_/\/_____/\/_____/  \/_/ \/_/\/_____/\/_____/'

# ── Cross-platform browser opener ─────────────────────────────────────────────
# macOS uses `open`, Linux uses `xdg-open`.  Both are no-ops on systems where
# neither is available (e.g. a headless server).
_open() {
    case "$(uname -s)" in
        Darwin) open "$1" ;;
        Linux)  xdg-open "$1" 2>/dev/null || true ;;
    esac
}

# ── Docker running? ───────────────────────────────────────────────────────────
# A missing Docker daemon means every compose command would fail with a confusing
# "Cannot connect to the Docker daemon" message.  Catch it here with a plain hint.
_docker_ok() {
    docker info &>/dev/null
}

# ── Spinner helper ─────────────────────────────────────────────────────────
# Same rotating-glyph animation open_results.sh uses. A couple of seconds of
# motion right after the keypress signals "got it, doing something" instead
# of a blank pause before the command's own output starts. This script
# already requires a real interactive terminal (stty raw below), so unlike
# open_results.sh there's no non-TTY fallback to guard for.
_spin() {
    local seconds="$1" label="$2" style="${3:-dots}"
    local frames
    if [ "$style" = "circle" ]; then
        frames=("⢎ " "⠎⠁" "⠊⠑" "⠈⠱" " ⡱" "⢀⡰" "⢄⡠" "⢆⡀")
    else
        frames=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
    fi
    local ticks=$(( seconds * 1000 / 80 ))   # 80ms per frame
    local i=0
    while [ "$i" -lt "$ticks" ]; do
        printf "\r  %s %s" "${frames[$(( i % ${#frames[@]} ))]}" "$label"
        sleep 0.08
        i=$(( i + 1 ))
    done
    printf "\r%*s\r" 70 ""   # wipe the line before returning
}

# ── Single-keypress read ──────────────────────────────────────────────────────
# stty raw/-echo reads one byte without waiting for Enter.  We restore the
# terminal on exit (or SIGINT) via the trap below.
_read_key() {
    stty raw -echo 2>/dev/null
    local key
    key=$(dd bs=1 count=1 2>/dev/null)   # read exactly one byte
    stty -raw echo 2>/dev/null
    printf '%s' "$key"
}

# Restore terminal if the user hits Ctrl+C mid-menu
trap 'stty -raw echo 2>/dev/null; echo; exit 0' INT

# ── Boot sequence ──────────────────────────────────────────────────────────
# Runs once, before the menu loop below (which clears and redraws on every
# return trip) — a short "system coming online" beat that sets the control-
# panel tone before the plain numbered menu takes over. Purely atmospheric;
# skipping it changes nothing about how the menu itself works.
_boot_sequence() {
    # Flicker "BOOT" twice — a fast clear/print/clear cycle reads as a
    # terminal still warming up, before the real banner replaces it.
    local i
    for i in 1 2; do
        clear
        printf "  %sBOOT%s" "$B" "$R"
        sleep 0.1
        clear
        sleep 0.1
    done

    # Custom logo, if one has been dropped into ASCII_ART above.
    if [ -n "$ASCII_ART" ]; then
        printf "\n%s" "$DIM"
        echo "$ASCII_ART"
        printf "%s\n" "$R"
    fi

    # Typewriter the uplink line one character at a time — same builds-
    # anticipation trick as the spinners, just for this one-time moment.
    local msg="Initializing uplink to Preempt Analytics prediction engine . ."
    local j
    printf "  %s" "$CYAN"
    for (( j=0; j<${#msg}; j++ )); do
        printf "%s" "${msg:$j:1}"
        sleep 0.015
    done
    printf "%s\n" "$R"

    # Loading bar — 24 blocks, fills left to right.
    local k
    printf "\n  %s[%s" "$DIM" "$R"
    for (( k=0; k<24; k++ )); do
        printf "%s█%s" "$GRN" "$R"
        sleep 0.03
    done
    printf "%s]%s\n" "$DIM" "$R"
    sleep 0.3
}

_boot_sequence

# ── Menu loop ─────────────────────────────────────────────────────────────────
while true; do

    clear
    echo ""
    echo "  ${B}${CYAN}PREEMPT ANALYTICS${R}  —  control panel"
    echo "  ${DIM}Predictive maintenance demo${R}"
    echo ""
    echo "  ${DIM}Run${R}"
    echo "  ${GRN}  1${R}  Smoke Test               ${DIM}(verify the API is connected)${R}"
    echo "  ${GRN}  2${R}  Full Retraining Loop     ${DIM}(simulate drift, watch it retrain)${R}"
    echo ""
    echo "  ${DIM}Inspect results${R}"
    echo "  ${GRN}  3${R}  Open drift report        ${DIM}(HTML — last run's feature histograms)${R}"
    echo "  ${GRN}  4${R}  Watch GitHub Actions     ${DIM}(live retraining pipeline)${R}"
    echo "  ${GRN}  5${R}  Follow monitor output    ${DIM}(docker compose logs -f monitor)${R}"
    echo ""
    echo "  ${DIM}System${R}"
    echo "  ${YLW}  6${R}  Restart all services     ${DIM}(pull latest image + docker compose up -d)${R}"
    echo "  ${YLW}  Q${R}  Quit"
    echo ""
    printf "  Press a number or Q:  "

    sel=$(_read_key)
    echo   # newline after the captured keystroke

    case "$sel" in

        1)
            # Smoke test: confirms the simulator can reach the API end-to-end.
            # Matches the README's own "Setup — three commands" step 3 exactly.
            _spin 2 "Spinning up simulation engine"
            if ! _docker_ok; then echo ""; echo "  ${YLW}⚠  Docker is not running.${R}  Start Docker Desktop first."; echo ""; read -rp "  Press Enter to continue..." ; continue; fi
            echo ""
            echo "  Running smoke test — verifying the simulator can reach the API..."
            echo ""
            docker compose run --rm simulator --mode normal --n-readings 500 --pause
            echo ""
            echo "  Smoke test complete — the API is connected. Choose option 3 to view the drift report."
            echo ""
            read -rp "  Press Enter to continue..."
            ;;

        2)
            # Full retraining loop: generates abnormal readings, then open_results.sh
            # opens the drift report and polls for + opens the specific GitHub Actions run.
            # Matches the README's "Trigger the full retraining loop" section exactly.
            _spin 2 "Engaging full retraining sequence"
            if ! _docker_ok; then echo ""; echo "  ${YLW}⚠  Docker is not running.${R}  Start Docker Desktop first."; echo ""; read -rp "  Press Enter to continue..." ; continue; fi
            echo ""
            echo "  Running the full retraining loop — this will take 1-5 minutes. Don't close this window."
            echo ""
            docker compose run --rm simulator --mode sudden-spike --n-readings 1000 --demo && ./open_results.sh
            echo ""
            read -rp "  Press Enter to continue..."
            ;;

        3)
            # Open the HTML drift report from the last simulator run.
            _spin 2 "Initializing drift report"
            if [ -f "$REPORT" ]; then
                echo ""
                echo "  Opening $REPORT in your browser..."
                echo ""
                _open "$REPORT"
            else
                echo ""
                echo "  No report found at $REPORT — run option 1 or 2 first."
                echo ""
                read -rp "  Press Enter to continue..."
            fi
            ;;

        4)
            # Open the GitHub Actions page to watch the retraining workflow run live.
            _spin 2 "Establishing uplink to GitHub Actions"
            echo ""
            echo "  Opening GitHub Actions in your browser..."
            echo ""
            _open "$ACTIONS"
            ;;

        5)
            # Stream the monitor container's live output.
            # Ctrl+C exits the log stream; the monitor itself keeps running.
            _spin 2 "Engaging live monitoring feed"
            if ! _docker_ok; then echo ""; echo "  ${YLW}⚠  Docker is not running.${R}  Start Docker Desktop first."; echo ""; read -rp "  Press Enter to continue..." ; continue; fi
            echo ""
            echo "  Streaming monitor output (Ctrl+C to stop):"
            echo ""
            # Temporarily restore terminal so log output looks normal, then re-trap on return.
            stty -raw echo 2>/dev/null
            docker compose logs -f monitor || true
            trap 'stty -raw echo 2>/dev/null; echo; exit 0' INT
            ;;

        6)
            # Pull the latest image from GHCR and restart all services.
            _spin 2 "Powering up services"
            if ! _docker_ok; then echo ""; echo "  ${YLW}⚠  Docker is not running.${R}  Start Docker Desktop first."; echo ""; read -rp "  Press Enter to continue..." ; continue; fi
            echo ""
            echo "  Pulling latest image and restarting services..."
            echo ""
            docker compose pull
            docker compose up -d
            echo ""
            echo "  Services restarted."
            echo ""
            read -rp "  Press Enter to continue..."
            ;;

        q|Q)
            echo ""
            exit 0
            ;;

        *)
            # Any other key: redraw the menu silently.
            ;;
    esac

done
