# scripts/promote_model.py
#
# WHY THIS SCRIPT EXISTS
# After dvc repro finishes, a new model version sits in the MLflow registry but
# carries no @production alias. The API and simulator both load models:/{name}@production,
# so nothing changes in production until someone (or this script) moves the alias.
#
# TWO MODES — CHOOSE BEFORE EVERY RETRAIN
#
#   Manual mode  (default, no --auto flag)
#     Reports what WOULD happen: shows new vs current f1_test, whether the new
#     version meets the threshold, and whether it would be promoted.
#     The alias is NOT moved. A developer reviews the report and promotes manually.
#     Safest option for regulated environments or when you don't trust the data yet.
#
#   Auto mode  (pass --auto)
#     Same comparison logic, but actually calls set_registered_model_alias() when
#     the new version passes both gates (beats current AND clears min-f1).
#     Use this only when you trust the simulation data quality and retraining pipeline.
#
# PROMOTION GATES (both must pass for auto-promote)
#   Gate 1 — improvement: new f1_test > current @production f1_test
#   Gate 2 — floor:       new f1_test >= --min-f1 (default 0.85 binary, 0.80 multiclass)
#
# USAGE
#   # Review only (safe — never changes the alias)
#   python scripts/promote_model.py --model-name predictive-maintenance-binary
#
#   # Auto-promote if new model passes both gates
#   python scripts/promote_model.py --model-name predictive-maintenance-binary --auto
#
#   # Override minimum F1 floor
#   python scripts/promote_model.py --model-name predictive-maintenance-binary --min-f1 0.90 --auto
#
# ENVIRONMENT VARIABLES REQUIRED
#   MLFLOW_TRACKING_URI       — DagsHub MLflow endpoint
#   MLFLOW_TRACKING_USERNAME  — your DagsHub username
#   MLFLOW_TRACKING_PASSWORD  — your DagsHub token (never commit this)
#   These are set automatically in CI from GitHub Secrets.
#   Locally, source them from your .env file before running.

import os
import sys
import click
import mlflow
from mlflow import MlflowClient


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_f1_for_version(client: MlflowClient, model_name: str, version: str) -> float | None:
    """Return f1_test from the MLflow run that produced this model version.

    Why this approach: model versions don't store metrics directly — metrics
    live on the run that created them. model_version.run_id is the bridge.
    Returns None if the run is missing or f1_test was never logged.
    """
    mv = client.get_model_version(model_name, version)
    if not mv.run_id:
        return None
    try:
        run = client.get_run(mv.run_id)
        return run.data.metrics.get("f1_test")
    except Exception:
        return None


def get_production_version(client: MlflowClient, model_name: str) -> str | None:
    """Return the version number currently carrying the @production alias, or None."""
    try:
        mv = client.get_model_version_by_alias(model_name, "production")
        return mv.version
    except mlflow.exceptions.MlflowException:
        # No @production alias set yet — first promotion ever.
        return None


def get_latest_version(client: MlflowClient, model_name: str) -> str | None:
    """Return the highest version number in the registry for this model name.

    MLflow assigns version numbers sequentially (1, 2, 3...). The latest retrain
    always produces the highest number. We sort as integers because string sort
    would place "10" before "2".
    """
    versions = client.search_model_versions(f"name='{model_name}'")
    if not versions:
        return None
    return str(max(int(mv.version) for mv in versions))


# ── Main ─────────────────────────────────────────────────────────────────────

@click.command()
@click.option(
    "--model-name",
    required=True,
    type=click.Choice(
        ["predictive-maintenance-binary", "predictive-maintenance-multiclass"],
        case_sensitive=True,
    ),
    help="Registered model name in MLflow.",
)
@click.option(
    "--min-f1",
    default=None,
    type=float,
    help=(
        "Minimum f1_test the new version must reach for promotion to be allowed. "
        "Defaults to 0.85 for binary, 0.80 for multiclass."
    ),
)
@click.option(
    "--auto",
    is_flag=True,
    default=False,
    help=(
        "Actually move the @production alias if the new version passes both gates. "
        "Without this flag the script reports what WOULD happen but changes nothing."
    ),
)
def main(model_name: str, min_f1: float | None, auto: bool) -> None:
    # ── Default F1 floor per model family ────────────────────────────────────
    # These defaults represent the minimum acceptable real-world performance.
    # Adjust with --min-f1 if your data distribution or business requirements differ.
    if min_f1 is None:
        min_f1 = 0.85 if "binary" in model_name else 0.80

    # ── Connect to MLflow ─────────────────────────────────────────────────────
    # Credentials come from environment variables — never hardcoded.
    # In CI they are injected from GitHub Secrets; locally, source your .env.
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        print("ERROR: MLFLOW_TRACKING_URI is not set.", file=sys.stderr)
        sys.exit(1)

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()

    mode_label = "AUTO PROMOTE" if auto else "MANUAL REVIEW (dry run)"
    print(f"\n{'='*60}")
    print(f"  promote_model.py — {mode_label}")
    print(f"  Model : {model_name}")
    print(f"  Min F1: {min_f1}")
    print(f"{'='*60}\n")

    # ── Discover versions ─────────────────────────────────────────────────────
    latest_version = get_latest_version(client, model_name)
    if not latest_version:
        print(f"ERROR: No versions found for '{model_name}'. Has dvc repro run yet?")
        sys.exit(1)

    prod_version = get_production_version(client, model_name)

    # ── Fetch F1 scores ───────────────────────────────────────────────────────
    new_f1 = get_f1_for_version(client, model_name, latest_version)
    if new_f1 is None:
        print(
            f"ERROR: Could not read f1_test for version {latest_version}. "
            "Check that the training run logged this metric."
        )
        sys.exit(1)

    if prod_version:
        prod_f1 = get_f1_for_version(client, model_name, prod_version)
        print(f"  Current @production : version {prod_version}  f1_test={prod_f1:.4f if prod_f1 is not None else 'N/A'}")
    else:
        prod_f1 = None
        print("  Current @production : (none — this will be the first promotion)")

    print(f"  Candidate           : version {latest_version}  f1_test={new_f1:.4f}")
    print()

    # ── Evaluate gates ────────────────────────────────────────────────────────
    # Gate 1: new model must be strictly better than the current production model.
    # Gate 2: new model must clear the minimum F1 floor regardless of comparison.
    gate_improvement = (prod_f1 is None) or (new_f1 > prod_f1)
    gate_floor       = new_f1 >= min_f1

    improvement_str = (
        "PASS (no current production version)"
        if prod_f1 is None
        else f"{'PASS' if gate_improvement else 'FAIL'}  ({new_f1:.4f} vs {prod_f1:.4f})"
    )
    print(f"  Gate 1 — improvement  : {improvement_str}")
    print(f"  Gate 2 — floor >= {min_f1} : {'PASS' if gate_floor else 'FAIL'}  ({new_f1:.4f})")
    print()

    # ── TODO A — Add a third gate (optional stretch task) ────────────────────
    #
    # Right now we only check f1_test. A production-grade system might also gate on:
    #   - precision_test (false-positive rate matters for maintenance cost)
    #   - recall_test    (false-negative rate matters for undetected failures)
    #   - overfit_delta  (reject models that memorised the training set)
    #
    # To add a gate, follow the same pattern as gate_improvement and gate_floor above:
    #   1. Fetch the metric from the MLflow run (using get_f1_for_version as a template)
    #   2. Define a boolean gate variable
    #   3. Add it to the `all_gates_pass` check below
    #   4. Print its result in the gate summary
    #
    # Example for recall_test >= 0.70:
    #   new_recall = get_metric_for_version(client, model_name, latest_version, "recall_test")
    #   gate_recall = (new_recall is not None) and (new_recall >= 0.70)
    #   print(f"  Gate 3 — recall >= 0.70   : {'PASS' if gate_recall else 'FAIL'}  ({new_recall:.4f})")
    #
    # Then update: all_gates_pass = gate_improvement and gate_floor and gate_recall

    all_gates_pass = gate_improvement and gate_floor

    # ── Decide ────────────────────────────────────────────────────────────────
    if not all_gates_pass:
        print("  Decision: HOLD — one or more gates failed.")
        print("  The @production alias has NOT been moved.")
        if not auto:
            print("  (dry run — same result in --auto mode)")
        sys.exit(0)

    # All gates passed — what happens next depends on the mode flag.
    if auto:
        # ── TODO B — Wire this to retrain.yml (guided task) ──────────────────
        #
        # This is the line that actually moves the @production alias.
        # When called from CI, `latest_version` is the version just created by dvc repro.
        #
        # After this runs, api.py and sensor_simulator.py will load the new model
        # on their next restart (they read @production at startup, not on each request).
        #
        # You don't need to change the code below — it's already complete.
        # Your task is in retrain.yml: replace the TODO C step with:
        #
        #   - name: Promote model to production
        #     env:
        #       MLFLOW_TRACKING_URI: ${{ secrets.MLFLOW_TRACKING_URI }}
        #       MLFLOW_TRACKING_USERNAME: ${{ secrets.DAGSHUB_USERNAME }}
        #       MLFLOW_TRACKING_PASSWORD: ${{ secrets.DAGSHUB_TOKEN }}
        #     run: |
        #       python scripts/promote_model.py \
        #         --model-name predictive-maintenance-binary \
        #         --min-f1 0.85 \
        #         --auto
        #       python scripts/promote_model.py \
        #         --model-name predictive-maintenance-multiclass \
        #         --min-f1 0.80 \
        #         --auto
        #
        # To stay in manual mode instead: remove this step from retrain.yml entirely.
        # The API will keep serving the old model until someone promotes manually.

        client.set_registered_model_alias(model_name, "production", latest_version)
        print(f"  Decision: PROMOTED — version {latest_version} is now @production.")
        if prod_version:
            delta = new_f1 - prod_f1
            print(f"  F1 improvement: +{delta:.4f} ({prod_f1:.4f} -> {new_f1:.4f})")
    else:
        print(f"  Decision: WOULD PROMOTE — version {latest_version} passes all gates.")
        print("  Run with --auto to actually move the @production alias.")
        if prod_version:
            delta = new_f1 - prod_f1
            print(f"  F1 improvement: +{delta:.4f} ({prod_f1:.4f} -> {new_f1:.4f})")

    print()


if __name__ == "__main__":
    main()
