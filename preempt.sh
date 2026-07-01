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

# ── Menu loop ─────────────────────────────────────────────────────────────────
while true; do

    clear
    echo ""
    echo "  ${B}${CYAN}PREEMPT ANALYTICS${R}  —  control panel"
    echo "  ${DIM}Predictive maintenance demo${R}"
    echo ""
    echo "  ${DIM}Simulate sensors${R}"
    echo "  ${GRN}  1${R}  Sudden-spike readings    ${DIM}(abnormal — triggers drift detection)${R}"
    echo "  ${GRN}  2${R}  Normal readings          ${DIM}(baseline — builds comparison dataset)${R}"
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
            # Sudden-spike mode: pushes sensor values outside the training distribution.
            # 1,000 readings gives Evidently enough current data for reliable KS tests.
            if ! _docker_ok; then echo ""; echo "  Docker is not running.  Start Docker Desktop first."; echo ""; read -rp "  Press Enter to continue..." ; continue; fi
            echo ""
            echo "  Generating 1,000 sudden-spike readings..."
            echo ""
            docker compose run --rm simulator --mode sudden-spike --n-readings 1000
            echo ""
            echo "  Done.  Choose option 3 to open the drift report."
            echo ""
            read -rp "  Press Enter to continue..."
            ;;

        2)
            # Normal mode: readings that match the training distribution.
            # Use this to build up the comparison dataset without triggering a retrain.
            if ! _docker_ok; then echo ""; echo "  Docker is not running.  Start Docker Desktop first."; echo ""; read -rp "  Press Enter to continue..." ; continue; fi
            echo ""
            echo "  Generating 500 normal readings..."
            echo ""
            docker compose run --rm simulator --mode normal --n-readings 500
            echo ""
            echo "  Done."
            echo ""
            read -rp "  Press Enter to continue..."
            ;;

        3)
            # Open the HTML drift report from the last simulator run.
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
            echo ""
            echo "  Opening GitHub Actions in your browser..."
            echo ""
            _open "$ACTIONS"
            ;;

        5)
            # Stream the monitor container's live output.
            # Ctrl+C exits the log stream; the monitor itself keeps running.
            if ! _docker_ok; then echo ""; echo "  Docker is not running.  Start Docker Desktop first."; echo ""; read -rp "  Press Enter to continue..." ; continue; fi
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
            if ! _docker_ok; then echo ""; echo "  Docker is not running.  Start Docker Desktop first."; echo ""; read -rp "  Press Enter to continue..." ; continue; fi
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
