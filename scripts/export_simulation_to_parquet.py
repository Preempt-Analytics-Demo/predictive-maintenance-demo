"""
ETL Export — Simulation Database → CSV
========================================
Reads accumulated sensor readings from simulation.db and converts them
into the exact column format of data/ai4i2020.parquet so the retraining loop
can treat simulated data as new labelled observations.

Why this step is necessary
--------------------------
The DVC pipeline retrains from data/ai4i2020.parquet — a flat CSV in the
original AI4I 2020 format. The simulator writes to an SQLite database
with extra columns (machine_id, predicted_failure, mode, etc.) that the
training pipeline does not understand. This script bridges the two worlds.

Column mapping
--------------
SQLite                        → CSV
─────────────────────────────────────────────
id (autoincrement)            → UDI (sequential, appended after existing)
machine_type + row counter    → Product ID (e.g. "M00001")
machine_type                  → Type
air_temperature_kelvin        → Air temperature [K]
process_temperature_kelvin    → Process temperature [K]
rotational_speed_rpm          → Rotational speed [rpm]
torque_nm                     → Torque [Nm]
tool_wear_minutes             → Tool wear [min]
injected_failure              → Machine failure
(derived from sensor physics) → TWF, HDF, PWF, OSF, RNF

Failure type flags
------------------
The simulator injects failures by shifting ALL sensor values simultaneously
(lower rpm + higher torque + narrower temp gap) rather than targeting a
specific type. For retraining we derive which individual failure modes the
sensor physics indicate, using the same rules applied when the original
AI4I dataset was generated (from the paper by Matzka, 2020):

  HDF: rotational_speed_rpm < 1380  AND  temp_diff < 8.6 K
  PWF: power (W) < 3500  OR  power (W) > 9000
  OSF: torque_nm × tool_wear_minutes > 11000 (L) / 12000 (M) / 13000 (H)
  TWF: tool_wear_minutes >= per-type limit (200/220/240) — only if failure
  RNF: not injected (random, no sensor signature) → set to 0

These derived flags are ground truth for the retraining run. They may not
perfectly match the injector's intent (e.g. an injected HDF reading that
the physics rules do not flag as HDF), but they are far more honest than
copying the model's own predictions as labels, which would create a
self-reinforcing feedback loop.

Design decisions
----------------
Four choices that shaped this script — and why they were made this way:

  1. Failure flags from physics, not model predictions.
     Using predicted_failure_type as a label would make the model train on
     its own output — a self-reinforcing feedback loop. The model's bias
     compounds with every retraining cycle. Physics rules (Matzka 2020)
     produce labels that are independent of which model is currently in
     production, so retraining cannot worsen the model's existing blind spots.

  2. --append is the default; UDIs are always monotonically increasing.
     DVC takes whole-file snapshots — it does not append rows to a tracked
     file incrementally. Every `dvc add` replaces the pointer with a new hash
     of the entire CSV. If UDIs reset or overlap between runs, DVC sees a
     valid file but the dataset has silent duplicates. Continuing from the
     last UDI in the existing CSV prevents that and keeps the combined file
     behaving like the original dataset.

  3. --since lets you target a specific simulation run.
     simulation.db is append-only across multiple simulator runs. Without a
     timestamp filter you would re-export older rows every time, inflating
     the dataset with rows already included in a previous export. --since
     lets you export only the new batch.

  4. --dry-run is there to protect a DVC-tracked file.
     Once you run `dvc add data/ai4i2020.parquet`, the CSV is tracked by its
     hash. Overwriting it without reviewing what will change is risky —
     DVC will faithfully record a bad dataset just as willingly as a good
     one. --dry-run shows the failure rate, per-type flag counts, and a row
     preview so you can sanity-check the export before it touches the file.

  5. --purge deletes exported rows from simulation.db after a successful write.
     Without it, simulation.db grows unboundedly and every export re-reads the
     same old rows unless you remember to use --since. With it, the DB stays
     small and the CSV becomes the single durable record. Purge happens by
     exact row ID (not timestamp) so a simulator run that writes new rows
     during export is never accidentally deleted.

Retraining loop
---------------
The fastest path — one command does everything:

  # Export, push to DagsHub, and fire the GitHub Actions retrain workflow:
  python scripts/export_simulation_to_parquet.py --push --retrain

  # Export and push only (data accumulation, no retrain triggered):
  python scripts/export_simulation_to_parquet.py --push

The manual equivalent of --push --retrain (for reference):

  1. python scripts/export_simulation_to_parquet.py   ← this script
  2. dvc add data/ai4i2020.parquet          # update the .dvc pointer (local only)
  3. dvc push data/ai4i2020.parquet         # upload the CSV to DagsHub remote
  4. # write a UTC timestamp into retrain.trigger
  5. git add data/ai4i2020.parquet.dvc retrain.trigger
  6. git commit -m "retrain: add N simulated observations [drift]"
  7. git push                           # GitHub Actions fires because retrain.trigger changed

  GitHub Actions watches retrain.trigger, not ai4i2020.parquet.dvc. Omitting step 4-5
  (i.e. using --push without --retrain) pushes the data silently with no workflow fired.
  dvc repro is NOT run locally — GitHub Actions handles it in CI.

Usage
-----
  # Append new simulation rows to the existing dataset (default):
  python scripts/export_simulation_to_parquet.py

  # Export and trigger retraining in one step (runs dvc add/push + git commit/push):
  python scripts/export_simulation_to_parquet.py --push

  # Write to a separate file first (safe for inspection):
  python scripts/export_simulation_to_parquet.py --output data/simulated_batch.parquet --no-append

  # Only export rows from after a specific timestamp:
  python scripts/export_simulation_to_parquet.py --since "2025-01-01T00:00:00"

  # Dry run — show counts and column preview, write nothing:
  python scripts/export_simulation_to_parquet.py --dry-run

  # Export and delete the exported rows from simulation.db (keeps DB small):
  python scripts/export_simulation_to_parquet.py --purge

  # Export, purge DB, and trigger retraining:
  python scripts/export_simulation_to_parquet.py --purge --push
"""

import base64
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import click
import pandas as pd

# ── Repository roots ──────────────────────────────────────────────────────────
# This script lives in scripts/. Data and DB live at the project root.
# The output is Parquet rather than CSV: same column names and values, but
# columnar and compressed — DVC tracks it the same way, just a different hash.
REPO_ROOT      = Path(__file__).resolve().parent.parent
DB_PATH        = REPO_ROOT / "data" / "simulation.db"  # inside data/ so the existing Docker volume covers it
DEFAULT_OUTPUT = REPO_ROOT / "data" / "ai4i2020.parquet"  # Parquet replaces the growing CSV

# ── Failure type derivation thresholds ───────────────────────────────────────
# From Matzka (2020) — the same rules used to generate the original labels.

# HDF: both conditions must be true simultaneously
HDF_RPM_THRESHOLD  = 1380.0   # rpm below this + narrow temp gap → heat dissipation failure
HDF_TEMP_THRESHOLD = 8.6      # process − air temp below this K

# PWF: power (watts) outside the normal operating window
PWF_POWER_LOW_W    = 3500.0
PWF_POWER_HIGH_W   = 9000.0

# OSF: torque × tool_wear exceeds per-type strain limit
OSF_LIMITS = {"L": 11_000, "M": 12_000, "H": 13_000}

# TWF: wear reaches the per-type replacement limit
WEAR_LIMITS = {"L": 200, "M": 220, "H": 240}


# ── Physics-based failure flag derivation ────────────────────────────────────

def derive_failure_flags(row: pd.Series) -> dict:
    """Derive individual failure type flags from sensor physics.

    Each flag is 1 if the physics of this specific reading match the
    failure mode's known sensor signature AND the reading was labelled
    as a failure by the simulator (injected_failure == 1).

    Setting flags only when injected_failure is true keeps the label
    set realistic: false-positive sensor patterns in normal operation
    should not be labelled as failures in the retraining data.

    Args:
        row: One row from the exported SQLite query.

    Returns:
        Dict with keys twf, hdf, pwf, osf, rnf (all 0 or 1).
    """
    if not row["injected_failure"]:
        return {"twf": 0, "hdf": 0, "pwf": 0, "osf": 0, "rnf": 0}

    machine_type = row["machine_type"]
    temp_diff    = row["process_temperature_kelvin"] - row["air_temperature_kelvin"]
    power_w      = row["torque_nm"] * row["rotational_speed_rpm"] * 2 * 3.14159 / 60
    wear_limit   = WEAR_LIMITS.get(machine_type, 240)
    osf_limit    = OSF_LIMITS.get(machine_type, 11_000)

    # TWF: wear reached or exceeded the per-type replacement limit
    twf = int(row["tool_wear_minutes"] >= wear_limit)

    # HDF: low rpm AND narrow temp gap — simultaneous conditions required
    hdf = int(
        row["rotational_speed_rpm"] < HDF_RPM_THRESHOLD
        and temp_diff < HDF_TEMP_THRESHOLD
    )

    # PWF: power outside the safe operating window
    pwf = int(power_w < PWF_POWER_LOW_W or power_w > PWF_POWER_HIGH_W)

    # OSF: torque × wear exceeds per-type overstrain limit
    osf = int(row["torque_nm"] * row["tool_wear_minutes"] > osf_limit)

    # RNF: purely random, no sensor signature — never injected, always 0 here
    rnf = 0

    return {"twf": twf, "hdf": hdf, "pwf": pwf, "osf": osf, "rnf": rnf}


# ── Product ID generation ────────────────────────────────────────────────────

def make_product_id(machine_type: str, row_counter: int) -> str:
    """Generate a Product ID in the original dataset format.

    Original format: type letter + 5-digit zero-padded number (e.g. "M14860").
    Simulated rows start their counter above 20000 to avoid collisions with
    the original 10,000 rows (which top out near ~19860).

    Args:
        machine_type: "L", "M", or "H".
        row_counter:  Sequential row number within this export batch.

    Returns:
        Product ID string, e.g. "M20001".
    """
    return f"{machine_type}{20_000 + row_counter:05d}"


# ── Main ETL ──────────────────────────────────────────────────────────────────

def load_simulation_rows(db_path: Path, since: str | None) -> pd.DataFrame:
    """Read sensor readings from simulation.db.

    Args:
        db_path: Path to the SQLite file.
        since:   ISO 8601 timestamp string; if given, only rows after this
                 timestamp are returned. None = all rows.

    Returns:
        DataFrame with all sensor_readings columns.
    """
    if not db_path.exists():
        click.echo(f"ERROR: Database not found at {db_path}", err=True)
        click.echo("Run `python src/sensor_simulator.py` first to generate readings.", err=True)
        sys.exit(1)

    conn  = sqlite3.connect(db_path)
    query = "SELECT * FROM sensor_readings"
    if since:
        query += f" WHERE timestamp > '{since}'"
    query += " ORDER BY id"

    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def purge_exported_rows(db_path: Path, row_ids: list[int]) -> int:
    """Delete exported rows from simulation.db by their exact IDs.

    WHY by ID and not by timestamp?
    Deleting by ID means we remove exactly the rows that were loaded and
    written to CSV — nothing more.  If the simulator happens to write new
    rows while this script is running, those rows have higher IDs and are
    never touched.  A timestamp-based DELETE could catch those new rows if
    the clock ticks between load and delete.

    WHY batch in chunks of 500?
    SQLite's default SQLITE_MAX_VARIABLE_NUMBER limit is 999.  Passing more
    than 999 values in a single IN clause raises an OperationalError.  500
    is a safe batch size with headroom for other bound variables.
    """
    if not row_ids:
        return 0

    conn    = sqlite3.connect(db_path)
    deleted = 0

    # Delete in batches so we never exceed SQLite's IN-clause variable limit.
    for i in range(0, len(row_ids), 500):
        chunk        = row_ids[i : i + 500]               # slice one batch of IDs
        placeholders = ",".join("?" * len(chunk))          # "?,?,?..." for parameterised query
        cursor       = conn.execute(
            f"DELETE FROM sensor_readings WHERE id IN ({placeholders})", chunk
        )
        deleted += cursor.rowcount                         # accumulate rows actually deleted

    conn.commit()
    conn.close()
    return deleted


def convert_to_parquet_format(sim_df: pd.DataFrame, starting_udi: int) -> pd.DataFrame:
    """Convert simulation DataFrame to original CSV column layout.

    Args:
        sim_df:       Raw rows from sensor_readings table.
        starting_udi: UDI to assign to the first exported row. Subsequent
                      rows get consecutive integers.

    Returns:
        DataFrame with exactly the same columns as data/ai4i2020.parquet.
    """
    rows = []
    for offset, (_, row) in enumerate(sim_df.iterrows()):
        flags = derive_failure_flags(row)
        rows.append({
            "UDI":                        starting_udi + offset,
            "Product ID":                 make_product_id(row["machine_type"], offset + 1),
            "Type":                       row["machine_type"],
            "Air temperature [K]":        round(row["air_temperature_kelvin"], 1),
            "Process temperature [K]":    round(row["process_temperature_kelvin"], 1),
            "Rotational speed [rpm]":     int(row["rotational_speed_rpm"]),
            "Torque [Nm]":                round(row["torque_nm"], 1),
            "Tool wear [min]":            int(row["tool_wear_minutes"]),
            "Machine failure":            int(row["injected_failure"]),
            "TWF":                        flags["twf"],
            "HDF":                        flags["hdf"],
            "PWF":                        flags["pwf"],
            "OSF":                        flags["osf"],
            "RNF":                        flags["rnf"],
        })
    return pd.DataFrame(rows)


# ── Friendly error translation ───────────────────────────────────────────────
# dvc and git report failures as raw CLI stderr — DNS errors, auth rejections,
# merge conflicts — which means nothing to the non-technical demo user this
# script runs for inside the monitor container. This maps the handful of
# failure signatures we actually see in this demo (no internet, expired demo
# credentials, a stale local commit) to one plain-English line, printed above
# the raw text so a developer debugging the same log still gets full detail.
_FAILURE_SIGNATURES: list[tuple[tuple[str, ...], str]] = [
    (
        ("Name or service not known", "nodename nor servname",
         "Temporary failure in name resolution", "getaddrinfo failed",
         "Could not resolve host"),
        "No internet connection - this machine could not reach the network at all. "
        "Your data is safe locally; the next check will retry automatically.",
    ),
    (
        ("Connection refused", "Connection timed out", "Max retries exceeded",
         "Could not connect"),
        "Could not reach DagsHub/GitHub - the network is up but the remote server "
        "did not respond. The next check will retry automatically.",
    ),
    (
        ("401", "403", "Authentication failed", "Permission denied (publickey)",
         "could not read Username"),
        "Login to DagsHub/GitHub failed - the demo credentials may have expired "
        "or changed. Check .env.demo against the project's DagsHub settings.",
    ),
    (
        ("rejected", "non-fast-forward", "Updates were rejected"),
        "Someone (or something) else pushed changes to this repo first. "
        "Pull the latest changes, then retry.",
    ),
    (
        ("nothing to commit",),
        "Nothing new to save - this export produced no changes since the last push.",
    ),
    (
        ("No space left on device",),
        "This computer is out of disk space.",
    ),
]


def _diagnose_failure(output: str) -> str | None:
    """Match dvc/git failure text against known signatures; return a plain-English
    cause, or None when the failure doesn't match anything we've seen before
    (the raw output is still shown in that case — nothing is hidden)."""
    for signatures, message in _FAILURE_SIGNATURES:
        if any(sig in output for sig in signatures):    # first matching signature wins
            return message
    return None


# ── SSH environment setup for Docker ─────────────────────────────────────────
# When running inside Docker the git remote URL contains 'github-preempt' — an
# SSH Host alias that exists only in the host's ~/.ssh/config, not inside the
# container. Without this function git push fails with "Could not resolve
# hostname github-preempt". The fix: decode the Ed25519 deploy key from
# GIT_SSH_KEY_B64 (set in .env.demo) and write a temp SSH config that maps the
# alias to github.com. Returns None on the host where ~/.ssh/config already works.

def _make_ssh_env() -> dict[str, str] | None:
    """Return a GIT_SSH_COMMAND env dict that resolves the github-preempt alias.

    Reads GIT_SSH_KEY_B64 from the environment. If absent (running on the host),
    returns None so the host's own SSH config handles authentication as normal.
    """
    key_b64 = os.environ.get("GIT_SSH_KEY_B64")
    if not key_b64:
        return None  # host environment — ~/.ssh/config already has the alias

    # Decode the deploy key and write to a temp file; SSH refuses keys not 0600
    key_bytes = base64.b64decode(key_b64)
    key_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".pem", delete=False)
    key_file.write(key_bytes)
    key_file.close()
    os.chmod(key_file.name, 0o600)  # SSH client refuses keys readable by others

    # Map the host alias to the real GitHub hostname so git push resolves correctly
    ssh_config = tempfile.NamedTemporaryFile(mode="w", suffix=".ssh_config", delete=False)
    ssh_config.write(
        f"Host github-preempt\n"
        f"    HostName github.com\n"           # alias maps to GitHub's real server
        f"    User git\n"
        f"    IdentityFile {key_file.name}\n"   # deploy key decoded from GIT_SSH_KEY_B64
        f"    StrictHostKeyChecking no\n"       # no known_hosts DB inside the container
        f"    UserKnownHostsFile /dev/null\n"   # suppress "unknown host" warnings
    )
    ssh_config.close()

    return {"GIT_SSH_COMMAND": f"ssh -F {ssh_config.name}"}


# ── Retrain trigger ───────────────────────────────────────────────────────────
# Runs the dvc/git sequence that tells GitHub Actions new data is ready.
# Each command must succeed before the next one starts — subprocess.run with
# check=True raises CalledProcessError on a non-zero exit code, which stops
# the sequence and prints the failing command's stderr so the cause is clear.

def _push_to_remote(data_path: Path, n_rows: int, trigger_retrain: bool = False) -> None:
    """Run dvc add/push and git commit/push to update the training dataset.

    When trigger_retrain is True, retrain.trigger is also updated and staged.
    GitHub Actions watches that file, not the .dvc pointer — so a data push
    without trigger_retrain accumulates data silently with no workflow fired.
    A push with trigger_retrain updates both files in the same commit,
    which causes the workflow to run.

    Args:
        data_path:       Path to the Parquet file that was just written.
        n_rows:          Number of newly exported rows (used in the commit message).
        trigger_retrain: True → update retrain.trigger and fire GitHub Actions.
                         False → push data only, no workflow triggered.
    """
    dvc_pointer     = Path(str(data_path) + ".dvc")             # data/ai4i2020.parquet.dvc
    retrain_trigger = REPO_ROOT / "retrain.trigger"             # project-root sentinel file

    if trigger_retrain:
        # Write a UTC timestamp so git log shows exactly when each retrain was triggered.
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        retrain_trigger.write_text(f"drift detected: {ts}\n")   # change content → workflow fires
        commit_msg = f"retrain: add {n_rows:,} simulated observations [drift]"
        git_add_targets = [str(dvc_pointer), str(retrain_trigger)]
    else:
        commit_msg = f"data: add {n_rows:,} simulated observations [no retrain]"
        git_add_targets = [str(dvc_pointer)]                     # retrain.trigger unchanged → no workflow

    # ── SSH environment (Docker only) ────────────────────────────────────────
    # On the host, git's SSH config already has the 'github-preempt' alias.
    # Inside Docker that alias is missing — _make_ssh_env() injects a temp
    # SSH config that maps it to github.com so git push resolves correctly.
    git_env = _make_ssh_env()
    run_env = {**os.environ, **git_env} if git_env else None  # None = inherit as-is

    steps = [
        (["dvc", "add",  str(data_path)],               "Updating .dvc pointer"),
        (["dvc", "push", str(data_path)],               "Uploading Parquet to DagsHub"),
        (["git", "add"] + git_add_targets,              "Staging files"),
        (["git", "commit", "-m", commit_msg],           "Committing"),
        (["git", "push"],                               "Pushing to GitHub"),
    ]

    for cmd, label in steps:
        click.echo(f"\n  → {label}...")
        result = subprocess.run(cmd, capture_output=True, text=True, env=run_env)  # env resolves SSH alias
        if result.returncode != 0:
            output    = result.stderr or result.stdout
            diagnosis = _diagnose_failure(output)         # plain-English cause, or None if unrecognised
            click.echo(f"\nERROR: `{' '.join(cmd)}` failed.", err=True)
            if diagnosis:
                click.echo(f"  {diagnosis}", err=True)     # lead with the plain-English line (Redish: front-load)
            click.echo("\n  Technical detail:", err=True)
            click.echo(f"  {output}", err=True)            # full detail always shown — nothing hidden
            sys.exit(1)
        if result.stdout.strip():
            click.echo(result.stdout.strip())

    if trigger_retrain:
        click.echo("\nGitHub Actions retrain workflow triggered.")
        click.echo("Monitor at: https://github.com/Preempt-analytics/predictive-maintenance-capstone/actions")
    else:
        click.echo("\nCSV updated on DagsHub. No retrain triggered (retrain.trigger unchanged).")


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.command()
@click.option(
    "--output", "output_path",
    default=str(DEFAULT_OUTPUT),
    show_default=True,
    help="Destination Parquet path. Defaults to data/ai4i2020.parquet.",
)
@click.option(
    "--db", "db_path",
    default=str(DB_PATH),
    show_default=True,
    help="Path to the simulation SQLite database.",
)
@click.option(
    "--since",
    default=None,
    help="ISO 8601 timestamp. Export only rows recorded after this time.",
)
@click.option(
    "--append/--no-append",
    default=True,
    show_default=True,
    help=(
        "--append: read the existing CSV, find the last UDI, and append new rows "
        "(default, safe for DVC tracking). "
        "--no-append: write only simulated rows to the output file."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview counts and first few rows; do not write any files.",
)
@click.option(
    "--purge",
    is_flag=True,
    default=False,
    help=(
        "After a successful CSV write, delete the exported rows from simulation.db. "
        "Keeps the DB small. The CSV becomes the single durable record. "
        "Ignored when --dry-run is set."
    ),
)
@click.option(
    "--push",
    is_flag=True,
    default=False,
    help=(
        "After writing the CSV, run dvc add, dvc push, git commit, and git push. "
        "Ignored when --dry-run is set."
    ),
)
@click.option(
    "--retrain",
    is_flag=True,
    default=False,
    help=(
        "Update retrain.trigger in the same git commit so GitHub Actions fires the "
        "retrain workflow. Only meaningful with --push. Without this flag, the CSV "
        "is pushed (data accumulates) but no workflow runs."
    ),
)
def main(
    output_path: str,
    db_path: str,
    since: str | None,
    append: bool,
    dry_run: bool,
    purge: bool,
    push: bool,
    retrain: bool,
) -> None:
    """Convert simulation.db readings to the AI4I Parquet format for DVC retraining.

    Typical retraining workflow after collecting enough simulation data:

    \b
    1. python scripts/export_simulation_to_parquet.py
    2. dvc add data/ai4i2020.parquet
    3. dvc push data/ai4i2020.parquet
    4. git add data/ai4i2020.parquet.dvc
    5. git commit -m "retrain: add N simulated observations"
    6. git push   ← GitHub Actions retrain workflow starts automatically

    Or run steps 2-6 automatically: add --push to the command above.
    """
    output = Path(output_path)
    db     = Path(db_path)

    # ── Load simulation rows ───────────────────────────────────────────────────
    click.echo(f"\nLoading simulation data from {db} ...")
    sim_df = load_simulation_rows(db, since)
    click.echo(f"  {len(sim_df):,} rows loaded from simulation.db")

    if sim_df.empty:
        click.echo("Nothing to export. Run sensor_simulator.py to generate readings.")
        return

    # ── Determine starting UDI ─────────────────────────────────────────────────
    if append and output.exists():
        existing = pd.read_parquet(output, columns=["UDI"])  # Parquet: load only the UDI column
        last_udi = int(existing["UDI"].max())
        click.echo(f"  Existing Parquet: {len(existing):,} rows, last UDI = {last_udi}")
        starting_udi = last_udi + 1
    else:
        starting_udi = 1
        click.echo("  No existing Parquet found (or --no-append set). Starting UDI at 1.")

    # ── Convert ────────────────────────────────────────────────────────────────
    export_df = convert_to_parquet_format(sim_df, starting_udi)

    # ── Preview ────────────────────────────────────────────────────────────────
    failure_rate = export_df["Machine failure"].mean()
    hdf_count    = export_df["HDF"].sum()
    pwf_count    = export_df["PWF"].sum()
    osf_count    = export_df["OSF"].sum()
    twf_count    = export_df["TWF"].sum()

    click.echo(f"\nExport summary:")
    click.echo(f"  Rows to export      : {len(export_df):,}")
    click.echo(f"  Failure rate        : {failure_rate:.1%}")
    click.echo(f"  HDF flags set       : {hdf_count:,}  ({hdf_count/len(export_df):.1%})")
    click.echo(f"  PWF flags set       : {pwf_count:,}  ({pwf_count/len(export_df):.1%})")
    click.echo(f"  OSF flags set       : {osf_count:,}  ({osf_count/len(export_df):.1%})")
    click.echo(f"  TWF flags set       : {twf_count:,}  ({twf_count/len(export_df):.1%})")
    click.echo(f"  UDI range           : {starting_udi} -> {starting_udi + len(export_df) - 1}")
    click.echo(f"\nFirst 3 export rows:")
    click.echo(export_df.head(3).to_string(index=False))

    if dry_run:
        click.echo("\n[DRY RUN] No files written.")
        if purge:
            click.echo(f"[DRY RUN] --purge would delete {len(sim_df):,} rows from simulation.db after a real write.")
        return

    # ── Write ──────────────────────────────────────────────────────────────────
    if append and output.exists():
        existing_full = pd.read_parquet(output)                       # load the full existing dataset
        combined      = pd.concat([existing_full, export_df], ignore_index=True)
        combined.to_parquet(output, index=False)                      # overwrite with combined rows
        click.echo(f"\nAppended {len(export_df):,} rows → {output}")
        click.echo(f"  Total rows in Parquet: {len(combined):,}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        export_df.to_parquet(output, index=False)                     # write first batch
        click.echo(f"\nWrote {len(export_df):,} rows → {output}")

    # ── Push to remote and trigger retraining ─────────────────────────────────
    # Push runs BEFORE purge. _push_to_remote calls sys.exit(1) on any failure,
    # so if the push fails the rows are never purged — the next monitor cycle
    # retries with the same data. Purging before a successful push would silently
    # discard data that was never uploaded.
    if push:
        _push_to_remote(output, len(export_df), trigger_retrain=retrain)

    # ── Purge ──────────────────────────────────────────────────────────────────
    # Only runs after a confirmed write (and after a successful push when --push
    # is set). Deletes by exact row IDs so concurrent simulator writes are safe.
    if purge:
        deleted = purge_exported_rows(db, sim_df["id"].tolist())
        click.echo(f"  Purged {deleted:,} rows from simulation.db")

    if not push:
        click.echo("\nNext steps:")
        click.echo("  dvc add data/ai4i2020.parquet")
        click.echo("  dvc push data/ai4i2020.parquet")
        click.echo("  git add data/ai4i2020.parquet.dvc  # data only — no retrain")
        click.echo("  # or also: git add retrain.trigger  # include to trigger retrain workflow")
        click.echo('  git commit -m "data: add N simulated observations"')
        click.echo("  git push")
        click.echo("\n  Or run automatically: --push (data only) or --push --retrain (data + retrain).")


if __name__ == "__main__":
    main()
