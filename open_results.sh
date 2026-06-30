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

# ── Open the drift report immediately ────────────────────────────────────────
# The HTML report is already written to the mounted reports/ volume — it is
# ready the moment the simulator container exits.
if [ -f "$REPORT" ]; then
    echo ""
    echo "  Opening drift report in your browser: $REPORT"
    _open "$REPORT"
else
    echo "  No drift report yet at $REPORT — run the simulator first."
fi

# ── Open GitHub Actions after a delay ────────────────────────────────────────
# The background monitor needs up to ~60 s to detect drift and push the retrain
# trigger, then GitHub Actions takes a few more seconds to start the workflow.
# Waiting 90 s here means the new run will be visible (or just starting) when
# the page opens, rather than appearing empty and confusing the user.
echo ""
echo "  GitHub Actions will open automatically once the retraining workflow"
echo "  has had time to appear (the monitor needs up to ~90 s to fire)."
echo "  Opening in 90 seconds..."
sleep 30 && echo "  Opening in 60 seconds..."
sleep 30 && echo "  Opening in 30 seconds..."
sleep 30
echo "  Opening GitHub Actions: $ACTIONS"
_open "$ACTIONS"
echo ""
