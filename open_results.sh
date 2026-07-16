#!/usr/bin/env bash
# open_results.sh — opens the drift report and GitHub Actions page in your browser.
#
# Run this after the simulator finishes:
#   docker compose run --rm simulator --mode sudden-spike --n-readings 1000
#   ./open_results.sh

REPORT="reports/drift_report.html"
ACTIONS="https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo/actions"

# open command differs by OS — macOS uses `open`, Linux uses `xdg-open`
_open() { case "$(uname -s)" in Darwin) open "$1" ;; Linux) xdg-open "$1" 2>/dev/null || true ;; esac; }

# ── Open the drift report after a short delay ────────────────────────────────
# The HTML report is already written to the mounted reports/ volume — it is
# ready the moment the simulator container exits. An 8-second pause gives you
# time to read the per-feature drift table in this terminal before the browser
# jumps to the foreground and steals focus from this window.
echo ""
echo "  The HTML report shows per-feature drift histograms and the overall verdict."
echo "  Opening in your browser in 8 seconds..."
sleep 2 && echo "  Opening in 6 seconds..."
sleep 2 && echo "  Opening in 4 seconds..."
sleep 2 && echo "  Opening in 2 seconds..."
sleep 2
if [ -f "$REPORT" ]; then
    echo "  Opening drift report: $REPORT"
    _open "$REPORT"                         # macOS: open, Linux: xdg-open
else
    echo "  No drift report found at $REPORT — run the simulator first."
fi

# ── Open GitHub Actions after a delay ────────────────────────────────────────
# Measured in practice, not estimated: the monitor's own check interval, the
# export + DagsHub upload, and GitHub Actions picking up the push each add
# real time — the workflow is reliably visible and running by ~4 minutes, not
# the 90 s this used to wait. Opening earlier just shows an empty Actions page
# with no run yet, which reads as "did this actually work?" to a first-time user.
echo ""
echo "  GitHub Actions will open automatically once the retraining workflow"
echo "  has had time to appear (this reliably takes a few minutes end to end)."
echo "  Opening in 240 seconds..."
sleep 60 && echo "  Opening in 180 seconds..."
sleep 60 && echo "  Opening in 120 seconds..."
sleep 60 && echo "  Opening in 60 seconds..."
sleep 30 && echo "  Opening in 30 seconds..."
sleep 30
echo "  Opening GitHub Actions: $ACTIONS"
_open "$ACTIONS"
echo ""
