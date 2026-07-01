# scripts/monitor.py
#
# USAGE
#   # Run directly (local dev)
#   python scripts/monitor.py
#
#   # Run inside Docker (started automatically by docker compose up)
#   docker compose up monitor
#
# WHAT THIS SCRIPT DOES
# Runs drift detection on a schedule. If drift is detected it delegates the
# entire export-and-push sequence to export_simulation_to_parquet.py, which
# already contains the dvc add → dvc push → git commit → git push pipeline.
# This script is purely the scheduler and audit logger — it adds no new logic.
#
# WHY A PYTHON SCHEDULER AND NOT LINUX CRON
# Both work. The Python schedule library (already in requirements.txt) keeps
# the timing logic visible in code rather than a separate crontab file.
# It also runs in the foreground, so Docker can see the process and restart
# it if it crashes. A cron job runs silently in the background — Docker
# cannot monitor or restart individual cron jobs.
#
# THE SELF-MONITORING LOOP
#
#   monitor.py runs               (every night at 02:00)
#        |
#        v
#   detect_drift.py runs          (compares simulation.db vs baseline CSV)
#        |
#        +-- no drift --> log PASS to monitor_log.jsonl, sleep until next run
#        |
#        +-- drift detected
#              |
#              v
#         export_simulation_to_parquet.py --purge --push --retrain
#              |   appends rows to CSV, clears DB, dvc add/push,
#              |   writes retrain.trigger, git commit + git push
#              v
#         GitHub Actions picks up the push      (retrain.yml triggers)
#              |
#              v
#         dvc repro + promote_model.py          (retrain + auto-promote if gates pass)
#              |
#              v
#         log result to monitor_log.jsonl


import json                                    # serialise log entries as single-line JSON
import sqlite3                                # check whether simulation.db has data before drift run
import subprocess
from datetime import datetime, timezone        # UTC timestamps for monitor_log.jsonl entries
from pathlib import Path

import schedule    # schedule library — already in requirements.txt
import time

# ── Paths ─────────────────────────────────────────────────────────────────────
# ROOT resolves to the project directory regardless of where the script is called from.
# All subprocess calls use cwd=ROOT so relative paths inside those scripts work.
ROOT = Path(__file__).resolve().parent.parent
LOG_PATH      = ROOT / "reports" / "monitor_log.jsonl"  # one JSON line appended per run; never overwritten
SIMULATION_DB = ROOT / "data" / "simulation.db"         # checked before each drift run

# ── Timing ────────────────────────────────────────────────────────────────────
# How long to wait before the very first drift check at startup, and how often
# to print the countdown line between checks. Both values are in seconds.
# The startup grace period gives a new user time to read the banner (and start
# the simulator) before the first check fires.
STARTUP_DELAY_S     = 10   # seconds before the first drift check on a fresh start
COUNTDOWN_INTERVAL_S = 15  # print "next check in Xs" every N seconds during idle


# ── Pre-flight check ──────────────────────────────────────────────────────────
# Before running Evidently's statistical tests, confirm there is at least one
# row in simulation.db. detect_drift.py handles the empty case itself, but
# calling it only to hear "no data" gives Frederick a confusing "STABLE" verdict
# from the monitor's perspective. Checking here lets us print a clear, actionable
# message and skip the full drift computation when the db is empty.

def _db_has_data() -> bool:
    """Return True if simulation.db has at least one sensor reading."""
    if not SIMULATION_DB.exists():
        return False
    conn = sqlite3.connect(SIMULATION_DB)
    count = conn.execute("SELECT COUNT(*) FROM sensor_readings").fetchone()[0]  # single-row aggregate
    conn.close()
    return count > 0


# ── Countdown helper ──────────────────────────────────────────────────────────
# Replaces the silent time.sleep() in the main loop. Prints one status line
# per COUNTDOWN_INTERVAL_S so the terminal never looks frozen between checks.
# Docker logs don't support carriage-return overwriting, so each tick is a new
# line — matches the countdown style the simulator already uses when waiting to
# open GitHub Actions.

def _countdown_to_next_check(idle_seconds: float) -> None:
    """Sleep idle_seconds while printing a periodic countdown line."""
    remaining = max(int(idle_seconds), 1)
    while remaining > 0:
        print(f"  ┄  Next drift check in {remaining:3d}s …", flush=True)  # visible in docker logs -f
        tick = min(COUNTDOWN_INTERVAL_S, remaining)   # don't sleep past the deadline
        time.sleep(tick)
        remaining -= tick


# ── Run log ───────────────────────────────────────────────────────────────────
# Every scheduled run appends one JSON line to reports/monitor_log.jsonl.
# This gives a persistent, human-readable audit trail without any extra
# dependencies. Docker logs scroll away on restart; this file does not.
# Fields: timestamp (UTC ISO-8601), drift_detected, retrain_triggered.

def _append_log(drift_detected: bool, retrain_triggered: bool) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)   # create reports/ if absent
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),  # UTC so log is timezone-safe
        "drift_detected": drift_detected,
        "retrain_triggered": retrain_triggered,
    }
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")   # one line per run; never truncates existing entries


# ── Drift check ───────────────────────────────────────────────────────────────
# This function runs on every scheduled tick. It calls detect_drift.py as a
# subprocess rather than importing it — keeping the two scripts independent and
# making it easy to test detect_drift.py on its own without the scheduler.

ACTIONS_URL = "https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo/actions"


def check_drift() -> None:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    print(f"\n{'─' * 60}")
    print(f"  [{now}]  Drift check running...")
    print(f"{'─' * 60}")

    # ── Step 0: Guard — require at least one simulation row ───────────────────
    # Running Evidently with an empty database produces a misleading "STABLE"
    # verdict (exit 0 from detect_drift.py).  Checking here gives Frederick a
    # plain "nothing to compare yet" message and skips the full computation.
    if not _db_has_data():
        print("\n  ○  No simulation data yet — the database is empty.")
        print("     Run the simulator to generate readings, then this monitor")
        print("     will compare them to the training baseline automatically:")
        print()
        print("     docker compose run --rm simulator \\")
        print("       --mode normal --n-readings 500")
        _append_log(drift_detected=False, retrain_triggered=False)
        return

    # ── Step 1: Run drift detection ───────────────────────────────────────────
    # detect_drift.py exits with code 0 (no drift) or 1 (drift detected).
    # We read the exit code to decide whether to trigger the export.
    result = subprocess.run(
        ["python", "scripts/detect_drift.py"],
        cwd=ROOT,
    )

    if result.returncode == 0:
        print("\n  ✓  STABLE — sensor distributions look normal.")
        print("     No retraining needed.")
        _append_log(drift_detected=False, retrain_triggered=False)   # record the PASS
        return

    # ── Step 2: Export, push, and trigger retraining ─────────────────────────
    # Drift confirmed. export_simulation_to_parquet.py owns the full pipeline:
    #   --purge   : removes exported rows from simulation.db after writing
    #   --push    : runs dvc add → dvc push to upload the updated CSV to DagsHub
    #   --retrain : writes a UTC timestamp to retrain.trigger and commits + pushes
    #
    # GitHub Actions watches retrain.trigger — a change there fires retrain.yml.
    print("\n  ✗  DRIFT DETECTED — uploading new data and triggering retraining...")
    print("     This may take a minute. Please wait.\n")
    export_result = subprocess.run(
        ["python", "scripts/export_simulation_to_parquet.py", "--purge", "--push", "--retrain"],
        cwd=ROOT,
    )

    if export_result.returncode != 0:
        print("\n  ERROR: Upload/push failed. Will retry on the next check (in ~1 minute).")
        print("  If this keeps failing, check README → 'Trigger the full retraining loop'.")
        _append_log(drift_detected=True, retrain_triggered=False)
        return

    print("\n" + "═" * 60)
    print("  RETRAINING TRIGGERED SUCCESSFULLY")
    print("═" * 60)
    print()
    print("  The model is now retraining in the cloud.")
    print("  Watch it run live — open this link in your browser:")
    print()
    print(f"  {ACTIONS_URL}")
    print()
    print("  See README → 'Trigger the full retraining loop' for what to expect.")
    print("═" * 60)
    _append_log(drift_detected=True, retrain_triggered=True)


# ── Schedule ──────────────────────────────────────────────────────────────────
# The schedule library uses a simple chained API:
#   schedule.every().day.at("02:00").do(check_drift)   ← production
#   schedule.every(5).minutes.do(check_drift)           ← demo / local dev
#
# Switch to the production line before deploying. The demo line runs frequently
# so you can verify the full pipeline end-to-end without waiting until 02:00.
#
# Production (uncomment when deploying):
# schedule.every().day.at("02:00").do(check_drift)
#
# Demo (comment out when deploying):
# 30s keeps the worst-case wait under a minute; GitHub Actions startup (~60-90s)
# is the dominant delay regardless, so going shorter adds no real benefit.
schedule.every(30).seconds.do(check_drift)


# ── Main loop ─────────────────────────────────────────────────────────────────
# schedule.run_pending() checks whether any scheduled jobs are due and runs them.
# It returns immediately — it does not block. idle_seconds() tells us exactly
# how long until the next job is due, so we sleep precisely that long rather
# than waking up every 60 seconds to find nothing to do.
if __name__ == "__main__":
    # ── Startup banner ────────────────────────────────────────────────────────
    # This block prints once when the container starts. It is Frederick's first
    # view of the monitor — the goal is to answer "what is this, what should I
    # do next, and how will I know it worked?" before any drift check runs.
    print()
    print("═" * 60)
    print("  PREEMPT ANALYTICS — DRIFT MONITOR")
    print("═" * 60)
    print()
    print("  What this does")
    print("  ──────────────")
    print("  Every minute this monitor compares the live sensor readings")
    print("  in simulation.db to the distribution the model was trained")
    print("  on.  When it detects significant drift (≥ 20 % of features"),
    print("  shifted), it automatically exports the new data, pushes it")
    print("  to DagsHub, and fires the GitHub Actions retraining workflow.")
    print()
    print("  What YOU need to do")
    print("  ───────────────────")
    print("  1. Generate sensor readings (if you haven't yet):")
    print("       docker compose run --rm simulator \\")
    print("         --mode sudden-spike --n-readings 500")
    print()
    print("  2. That's it — this monitor handles everything else.")
    print("     Watch the retraining workflow run live:")
    print(f"     {ACTIONS_URL}")
    print()
    print("  To follow this monitor's output:")
    print("    docker compose logs -f monitor")
    print()
    print(f"  Audit log: {LOG_PATH}")
    print("═" * 60)

    # ── Startup grace period ──────────────────────────────────────────────────
    # Give Frederick STARTUP_DELAY_S seconds to read the banner (and optionally
    # start the simulator) before the first drift check fires.  A fresh container
    # sometimes also needs a few seconds for DNS and the API healthcheck to
    # settle — the delay acts as a natural buffer for both concerns.
    print()
    for remaining in range(STARTUP_DELAY_S, 0, -1):
        print(f"\r  First drift check starting in {remaining:2d}s …", end="", flush=True)
        time.sleep(1)
    print()   # newline after countdown

    # Run once immediately after the grace period so Frederick gets instant
    # feedback without waiting for the first scheduled minute to tick.
    check_drift()

    # ── Main scheduling loop ──────────────────────────────────────────────────
    # schedule.run_pending() returns immediately; we sleep between ticks.
    # _countdown_to_next_check() replaces the silent time.sleep() so the log
    # always shows how long until the next check — the terminal never looks dead.
    while True:
        schedule.run_pending()                        # fire any jobs whose time has come
        idle = schedule.idle_seconds()                # seconds until the next scheduled job
        _countdown_to_next_check(max(idle, 1))        # sleep with visible countdown
