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

[ -f "$REPORT" ] && _open "$REPORT" || echo "No drift report yet at $REPORT"
_open "$ACTIONS"
