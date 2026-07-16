#!/usr/bin/env bash
# open_results.sh — opens the drift report and GitHub Actions page in your browser.
#
# Run this after the simulator finishes:
#   docker compose run --rm simulator --mode sudden-spike --n-readings 1000
#   ./open_results.sh

REPORT="reports/drift_report.html"
REPO="Preempt-Analytics-Demo/predictive-maintenance-demo"
WORKFLOW_RUNS="https://github.com/$REPO/actions/workflows/retrain.yml"   # this one workflow's runs, not every workflow in the repo

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
# with no run yet, which reads as "did this actually work?" to a first-time
# user — so the wait itself is explained up front, in plain terms, before the
# countdown starts (Redish: say what's happening and why before the numbers).
echo ""
echo "  Please be patient — retraining takes a little while to fire."
echo "  How long depends on your machine's speed, not on anything going wrong."
echo "  GitHub Actions will open as soon as the run is ready to watch."
echo ""
echo "  Opening in 240 seconds..."
sleep 60 && echo "  Opening in 180 seconds..."
sleep 60 && echo "  Opening in 120 seconds..."
sleep 60 && echo "  Opening in 60 seconds..."
sleep 30 && echo "  Opening in 30 seconds..."
sleep 30
echo "  Opening any moment. Please stay put — on a slower machine, or if"
echo "  the run itself started late, this can take a little longer still."

# ── Find the specific run, not just the workflow list ────────────────────────
# A run only gets a numeric ID once GitHub actually starts it — there is no way
# to know that ID ahead of time, but by now the run has had ~4 minutes to start,
# so asking the (public, unauthenticated) GitHub API for the most recent run of
# this one workflow reliably finds it. "id" is deliberately matched with its
# quotes and colon — the same response also contains workflow_id, check_suite_id,
# etc., which a looser match would grab by mistake.
RUN_ID=$(curl -s "https://api.github.com/repos/$REPO/actions/workflows/retrain.yml/runs?per_page=1" 2>/dev/null \
    | grep -o '"id": [0-9]*' | head -1 | grep -o '[0-9]*')

if [ -n "$RUN_ID" ]; then
    RUN_URL="https://github.com/$REPO/actions/runs/$RUN_ID"
    echo "  Opening the retraining run directly: $RUN_URL"
    _open "$RUN_URL"
else
    # API call failed or no run exists yet — fall back to the workflow's own run
    # list. Still far more targeted than the repo's general Actions tab, which
    # mixes in the unrelated docker-publish workflow.
    echo "  Couldn't fetch the specific run — opening the retraining workflow's run list instead."
    echo "  Click the top row (the most recent run) to watch it live."
    _open "$WORKFLOW_RUNS"
fi
echo ""
