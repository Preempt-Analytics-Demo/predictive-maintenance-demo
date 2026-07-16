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

# "id" is deliberately matched with its quotes and colon, both here and further
# down — the same API responses also contain workflow_id, check_suite_id, etc.,
# which a looser match would grab by mistake.
_latest_run_id() {
    curl -s "https://api.github.com/repos/$REPO/actions/workflows/retrain.yml/runs?per_page=1" 2>/dev/null \
        | grep -o '"id": [0-9]*' | head -1 | grep -o '[0-9]*'
}

# ── Baseline: remember the run that exists before this trigger fires ─────────
# Captured as the very first thing the script does, before the drift-report
# section below can spend any time — so a fast retraining pipeline can never
# race past this check. Comparing against this baseline later is how we tell a
# genuinely NEW run apart from re-opening whatever ran last time, which is
# what happened without it: the script grabbed "the most recent run" before
# the new one existed yet, and opened an old, already-finished run instead.
BASELINE_RUN_ID=$(_latest_run_id)

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

# ── Watch for the new retraining run ──────────────────────────────────────────
# A fixed wait can't work here: the slow part is uploading the training data to
# DagsHub, and that upload grows with every simulated reading ever generated in
# this environment — a few minutes early in a demo's life, longer the more the
# demo has been used since. Rather than guess a duration, poll the (public,
# unauthenticated) GitHub API every 20s for a run newer than the baseline
# above, and open it the instant it exists — accurate no matter how long the
# real wait turns out to be.
echo ""
echo "  Watching GitHub for the new retraining run — this can take anywhere from"
echo "  about a minute to several minutes. It depends on how much training data"
echo "  has to upload, not on anything going wrong. You'll be taken there the"
echo "  moment it's ready; no need to do anything."

POLL_INTERVAL=20
MAX_WAIT=600   # 10-minute ceiling — generous, but bounded so this can't hang forever
ELAPSED=0
NEW_RUN_ID=""

while [ "$ELAPSED" -lt "$MAX_WAIT" ]; do
    sleep "$POLL_INTERVAL"
    ELAPSED=$((ELAPSED + POLL_INTERVAL))

    CURRENT_RUN_ID=$(_latest_run_id)
    if [ -n "$CURRENT_RUN_ID" ] && [ "$CURRENT_RUN_ID" != "$BASELINE_RUN_ID" ]; then
        NEW_RUN_ID="$CURRENT_RUN_ID"
        break
    fi

    # Heartbeat every ~60s so a long wait doesn't look like the terminal froze.
    if [ $((ELAPSED % 60)) -eq 0 ]; then
        echo "  Still watching... (${ELAPSED}s so far — still normal)"
    fi
done

if [ -n "$NEW_RUN_ID" ]; then
    # A run's summary page still requires clicking into a job to see anything
    # live — html_url on the job itself is that exact click already followed,
    # landing on the same run+job URL a person would land on by hand.
    JOB_URL=$(curl -s "https://api.github.com/repos/$REPO/actions/runs/$NEW_RUN_ID/jobs" 2>/dev/null \
        | grep -o '"html_url": "[^"]*"' | head -1 | cut -d'"' -f4)

    if [ -n "$JOB_URL" ]; then
        echo "  Opening the retraining job live: $JOB_URL"
        _open "$JOB_URL"
    else
        RUN_URL="https://github.com/$REPO/actions/runs/$NEW_RUN_ID"
        echo "  Opening the retraining run: $RUN_URL"
        _open "$RUN_URL"
    fi
else
    # No new run within MAX_WAIT — fall back to the workflow's own run list.
    # Still far more targeted than the repo's general Actions tab, which mixes
    # in the unrelated docker-publish workflow.
    echo "  No new run appeared within ${MAX_WAIT}s — opening the retraining workflow's run list instead."
    echo "  Click the top row (the most recent run) to watch it live."
    _open "$WORKFLOW_RUNS"
fi
echo ""
