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
# Runs drift detection on a schedule. If drift is detected it exports the
# simulation data to the training CSV and pushes the retrain trigger to GitHub
# so the CI retraining pipeline fires automatically — without human intervention.
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
#        +-- no drift --> sleep until next scheduled run
#        |
#        +-- drift detected
#              |
#              v
#         export_simulation_to_csv.py --purge   (append to training CSV, clear DB rows)
#              |
#              v
#         dvc add + git push                    (update .dvc pointer, push to GitHub)
#              |
#              v
#         GitHub Actions picks up the push      (retrain.yml triggers)
#              |
#              v
#         dvc repro + promote_model.py          (retrain + auto-promote if gates pass)

import subprocess
import sys
from pathlib import Path

import schedule    # schedule library — already in requirements.txt
import time

# ── Paths ─────────────────────────────────────────────────────────────────────
# ROOT resolves to the project directory regardless of where the script is called from.
# All subprocess calls use cwd=ROOT so relative paths inside those scripts work.
ROOT = Path(__file__).resolve().parent.parent


# ── Drift check ───────────────────────────────────────────────────────────────
# This function runs on every scheduled tick. It calls detect_drift.py as a
# subprocess rather than importing it — keeping the two scripts independent and
# making it easy to test detect_drift.py on its own without the scheduler.

def check_drift() -> None:
    print("\n" + "=" * 60)
    print("  Drift check starting...")
    print("=" * 60)

    # ── Step 1: Run drift detection ───────────────────────────────────────────
    # detect_drift.py exits with code 0 (no drift) or 1 (drift detected).
    # We read the exit code to decide whether to trigger the export.
    result = subprocess.run(
        ["python", "scripts/detect_drift.py"],
        cwd=ROOT,
    )

    if result.returncode == 0:
        print("  No drift detected. Model distribution is stable.")
        print("  Next check scheduled per configured interval.")
        return

    # ── Step 2: Export simulation data ────────────────────────────────────────
    # Drift was detected — append simulation rows to the training CSV.
    # --purge removes the exported rows from simulation.db so they are not
    # exported again in the next cycle.
    print("  Drift detected. Exporting simulation data...")
    export_result = subprocess.run(
        ["python", "scripts/export_simulation_to_csv.py", "--purge"],
        cwd=ROOT,
    )

    if export_result.returncode != 0:
        print("  ERROR: Export failed. Skipping git push — will retry next cycle.")
        return

    # ── Step 3: Update DVC and push to GitHub ─────────────────────────────────
    # The training CSV has new rows. We need to:
    #   1. dvc add — recomputes the content hash and updates ai4i2020.csv.dvc
    #   2. git add  — stages the updated .dvc pointer file
    #   3. Update retrain.trigger — this is what the GitHub Actions workflow watches
    #   4. git commit + git push — sends the pointer change to GitHub
    #
    # GitHub Actions sees the push, pulls the new CSV from DagsHub, and retrains.
    #
    # TODO A — Complete the push sequence
    # The commands below are scaffolded with placeholders. Replace each TODO
    # line with the correct shell command. Use subprocess.run() like the examples
    # above. The first command is done for you as a model.
    #
    # Hint: look at what you run manually after export_simulation_to_csv.py.
    # The sequence is: dvc add → dvc push → git add → git commit → git push

    print("  Updating DVC pointer...")
    subprocess.run(
        ["dvc", "add", "data/ai4i2020.csv"],   # recompute hash, update .dvc file
        cwd=ROOT,
        check=True,
    )

    print("  Pushing data to DagsHub...")
    subprocess.run(
        ["dvc", "push", "data/ai4i2020.csv"],   # upload new rows to DagsHub remote
        cwd=ROOT,
        check=True,
    )

    # TODO A-1 — Touch retrain.trigger so GitHub Actions fires
    # retrain.yml watches for changes to retrain.trigger (not ai4i2020.csv.dvc).
    # Write the current timestamp into it so git sees a real change.
    # Hint:
    #   from datetime import datetime, timezone
    #   (ROOT / "retrain.trigger").write_text(datetime.now(timezone.utc).isoformat())
    print("  TODO A-1: update retrain.trigger here")

    # TODO A-2 — Stage the changed files for commit
    # You need to stage: data/ai4i2020.csv.dvc and retrain.trigger
    # Hint: subprocess.run(["git", "add", ...], cwd=ROOT, check=True)
    print("  TODO A-2: git add the changed files here")

    # TODO A-3 — Commit with a descriptive message
    # Hint: subprocess.run(["git", "commit", "-m", "..."], cwd=ROOT, check=True)
    print("  TODO A-3: git commit here")

    # TODO A-4 — Push to GitHub so GitHub Actions triggers
    # Hint: subprocess.run(["git", "push"], cwd=ROOT, check=True)
    print("  TODO A-4: git push here")

    print("  Retrain trigger pushed. GitHub Actions will pick this up shortly.")


# ── Schedule ──────────────────────────────────────────────────────────────────
# The schedule library uses a simple chained API:
#   schedule.every().day.at("02:00").do(check_drift)
#   schedule.every(6).hours.do(check_drift)
#   schedule.every(30).minutes.do(check_drift)   ← useful for demos
#
# TODO B — Set the production schedule
# Replace the placeholder below with the 2am daily schedule.
# Keep the 5-minute version commented out below it for demo use.
#
# Production (uncomment when deploying):
# schedule.every().day.at("02:00").do(check_drift)
#
# Demo (runs frequently so you can show it working live):
schedule.every(5).minutes.do(check_drift)   # TODO B: replace with daily at 02:00


# ── Main loop ─────────────────────────────────────────────────────────────────
# schedule.run_pending() checks whether any scheduled jobs are due and runs them.
# It must be called in a loop — it does not block between runs.
# time.sleep(60) means we check the schedule once per minute, which is
# precise enough for a daily job and cheap in terms of CPU.
if __name__ == "__main__":
    print("Preempt Analytics — Drift Monitor")
    print("Scheduled checks configured. Waiting for next run...")

    # Run once immediately at startup so you can verify the pipeline works
    # without waiting for the first scheduled tick.
    # TODO C — Should we run check_drift() immediately on startup?
    # Uncomment the line below if you want the first check to run right away:
    # check_drift()

    while True:
        schedule.run_pending()   # fire any jobs whose time has come
        time.sleep(60)           # wait 60 seconds before checking again
