#!/usr/bin/env bash
# run_demo.sh
#
# WHY THIS SCRIPT EXISTS
# Docker containers have no access to the host desktop, so the simulator
# cannot open a browser directly. This wrapper runs the simulator via
# docker compose and then opens the drift report and GitHub Actions page
# on your machine automatically — no copy-paste required.
#
# HOW TO USE
#   chmod +x run_demo.sh        # make it executable (first time only)
#   ./run_demo.sh               # default: 1,000 sudden-spike readings
#
# Pass extra arguments to override simulator defaults:
#   ./run_demo.sh --mode normal --n-readings 500

set -euo pipefail

ACTIONS_URL="https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo/actions"
REPORT_FILE="reports/drift_report.html"

# ── Open a file or URL cross-platform ─────────────────────────────────────────
# Each OS uses a different command to open things in the default app.
_open() {
    case "$(uname -s)" in
        Darwin)               open "$1" ;;
        Linux)                xdg-open "$1" 2>/dev/null || echo "  (could not open automatically — open manually)" ;;
        CYGWIN*|MINGW*|MSYS*) start "$1" ;;
    esac
}

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  PREEMPT ANALYTICS — DEMO RUN"
echo "══════════════════════════════════════════════════════════════"
echo ""

# ── Run the simulator ─────────────────────────────────────────────────────────
# Extra args passed to this script are forwarded to the simulator.
# Default is 1,000 sudden-spike readings — enough to trigger drift detection.
docker compose run --rm simulator --mode sudden-spike --n-readings 1000 "$@"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Simulation complete. Opening results..."
echo "══════════════════════════════════════════════════════════════"
echo ""

# ── Open the drift report ─────────────────────────────────────────────────────
# detect_drift.py writes drift_report.html to ./reports/, which is a volume
# mount — so the file already exists on your machine right now.
if [ -f "$REPORT_FILE" ]; then
    echo "  Drift report   → $REPORT_FILE"
    _open "$REPORT_FILE"
else
    echo "  No drift report at $REPORT_FILE — was there enough data in the database?"
fi

# ── Open GitHub Actions ───────────────────────────────────────────────────────
# If drift was detected, the background monitor triggers a retrain workflow
# within ~1 minute. The new run will appear in the Actions tab shortly.
echo "  GitHub Actions → $ACTIONS_URL"
_open "$ACTIONS_URL"
echo ""
