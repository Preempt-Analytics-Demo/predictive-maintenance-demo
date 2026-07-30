# scripts/generate_leaderboard.py
#
# WHY THIS SCRIPT EXISTS
# MLflow's own UI on DagsHub is contributor-gated — per DagsHub's own docs,
# "only a repository contributor can log experiments and access the DagsHub
# MLflow UI," regardless of whether the git repo itself is public. A demo
# visitor without DagsHub access can't open it. This script reads the exact
# same data promote_model.py already reads (every registered model version's
# f1_test, which one is @production) and writes it out as a plain file this
# public GitHub repo can show to anyone, no DagsHub account required.
#
# WHAT IT PRODUCES
#   reports/model_leaderboard.md  — a markdown table per registered model,
#                                    plus promotion history, plus an embedded chart
#   reports/leaderboard_chart.png — f1_test per version, one line per model
#
# USAGE
#   python scripts/generate_leaderboard.py
#
# ENVIRONMENT VARIABLES REQUIRED
#   MLFLOW_TRACKING_URI / USERNAME / PASSWORD — same as promote_model.py

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend — no display available in CI or Docker
import matplotlib.pyplot as plt
import mlflow
from mlflow import MlflowClient

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT           = Path(__file__).resolve().parent.parent
REPORTS_DIR          = REPO_ROOT / "reports"
PROMOTION_LOG_PATH   = REPORTS_DIR / "promotion_log.jsonl"   # written by promote_model.py
LEADERBOARD_MD_PATH  = REPORTS_DIR / "model_leaderboard.md"
CHART_PATH           = REPORTS_DIR / "leaderboard_chart.png"

MODEL_NAMES = ["predictive-maintenance-binary", "predictive-maintenance-multiclass"]

# The registry only ever grows — every retrain adds one more version, forever.
# Showing all of them would make this file bigger and less scannable every
# single run. The chart below still plots the full history; the table caps at
# the most recent versions, which is what anyone checking "is this healthy
# right now" actually wants.
MAX_ROWS_SHOWN = 15


# ── Data collection ──────────────────────────────────────────────────────────

def get_versions_with_metrics(client: MlflowClient, model_name: str) -> list[dict]:
    """Return one dict per registered version: version, model_family, f1_test,
    f1_train, is_production — newest version first.

    Metrics and tags live on the run that produced the version, not on the
    version itself — model_version.run_id is the bridge (same lookup
    promote_model.py's get_metric_for_version() does).
    """
    versions = client.search_model_versions(f"name='{model_name}'")
    try:
        prod_version = client.get_model_version_by_alias(model_name, "production").version
    except mlflow.exceptions.MlflowException:
        prod_version = None   # no @production alias set yet

    rows = []
    for mv in versions:
        run = None
        if mv.run_id:
            try:
                run = client.get_run(mv.run_id)
            except Exception:
                run = None   # run deleted or unreachable — still show the version
        metrics = run.data.metrics if run else {}
        tags    = run.data.tags if run else {}
        rows.append({
            "version":       int(mv.version),
            "model_family":  tags.get("model_family", "?"),
            "f1_test":       metrics.get("f1_test"),
            "f1_train":      metrics.get("f1_train"),
            "is_production": mv.version == prod_version,
        })
    rows.sort(key=lambda r: r["version"], reverse=True)
    return rows


def load_promotion_history(limit: int = 10) -> list[dict]:
    """Return the most recent promotion events, newest first. Empty if no
    promotion has ever run against this repo's copy of the log."""
    if not PROMOTION_LOG_PATH.exists():
        return []
    lines   = PROMOTION_LOG_PATH.read_text().strip().splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return list(reversed(entries[-limit:]))


# ── Rendering ─────────────────────────────────────────────────────────────────

def render_table(rows: list[dict]) -> str:
    if not rows:
        return "_No versions registered yet._\n"

    # rows is already newest-first (see get_versions_with_metrics). If the
    # current @production version happens to be older than the cap, keep it
    # visible anyway — "which one is live" is the one thing this table must
    # never omit, even if it means showing one row out of chronological order.
    shown = rows[:MAX_ROWS_SHOWN]
    prod_row = next((r for r in rows if r["is_production"]), None)
    if prod_row and prod_row not in shown:
        shown.append(prod_row)

    omitted = len(rows) - len(shown)
    lines = [
        "| Version | Model family | f1_test | f1_train | Status |\n",
        "|---------|--------------|---------|----------|--------|\n",
    ]
    for r in shown:
        f1_test  = f"{r['f1_test']:.4f}"  if r["f1_test"]  is not None else "—"
        f1_train = f"{r['f1_train']:.4f}" if r["f1_train"] is not None else "—"
        status   = "🟢 @production" if r["is_production"] else ""
        lines.append(f"| {r['version']} | {r['model_family']} | {f1_test} | {f1_train} | {status} |\n")
    if omitted > 0:
        lines.append(f"\n_{omitted} older version(s) omitted — showing the {len(shown)} most recent._\n")
    return "".join(lines)


def render_history_table(entries: list[dict]) -> str:
    if not entries:
        return "_No promotions recorded yet._\n"
    lines = [
        "| Date | Model | Version change | f1_test change |\n",
        "|------|-------|-----------------|------------------|\n",
    ]
    for e in entries:
        from_version = e["from_version"] or "—"          # None on a model's first-ever promotion
        from_f1      = f"{e['from_f1']:.4f}" if e["from_f1"] is not None else "—"
        to_f1        = f"{e['to_f1']:.4f}"
        lines.append(
            f"| {e['timestamp']} | {e['model_name']} | {from_version} → {e['to_version']} "
            f"| {from_f1} → {to_f1} |\n"
        )
    return "".join(lines)


def render_chart(rows_by_model: dict[str, list[dict]]) -> None:
    """Plot f1_test against registry version, one line per registered model.

    Versions are registration order across every model family that feeds
    this registry (xgboost, lightgbm, svm, ...), not a single algorithm's
    tuning history — the chart shows whether the registry has trended
    upward over time, not which family is best.
    """
    fig, ax = plt.subplots(figsize=(8, 4.5))
    any_points = False
    for model_name, rows in rows_by_model.items():
        scored = sorted((r for r in rows if r["f1_test"] is not None), key=lambda r: r["version"])
        if not scored:
            continue
        any_points = True
        label = "binary" if "binary" in model_name else "multiclass"
        ax.plot([r["version"] for r in scored], [r["f1_test"] for r in scored], marker="o", label=label)

    ax.set_xlabel("Registry version")
    ax.set_ylabel("f1_test")
    ax.set_title("Model performance across registered versions")
    if any_points:
        ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=120)
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        print("ERROR: MLFLOW_TRACKING_URI is not set.", file=sys.stderr)
        sys.exit(1)

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()

    rows_by_model = {}
    sections = []
    for model_name in MODEL_NAMES:
        rows = get_versions_with_metrics(client, model_name)
        rows_by_model[model_name] = rows
        label = "Binary classifier" if "binary" in model_name else "Multiclass classifier"
        sections.append(f"### {label} (`{model_name}`)\n\n{render_table(rows)}\n")

    render_chart(rows_by_model)

    history = load_promotion_history()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    content = f"""# Model Leaderboard

_Auto-generated by `scripts/generate_leaderboard.py` — last updated {now} UTC._

MLflow's own experiment-tracking UI on DagsHub is only visible to repository
contributors, regardless of whether this git repo is public (see the README's
MLflow section for why). This file mirrors the same underlying data — every
registered model version's test score and which one is currently live — so
anyone browsing this repo on GitHub can see it without a DagsHub account.

![Model performance across registered versions](leaderboard_chart.png)

{"".join(sections)}
## Promotion history

Most recent {len(history)} promotion(s):

{render_history_table(history)}
"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LEADERBOARD_MD_PATH.write_text(content)
    print(f"Leaderboard written to {LEADERBOARD_MD_PATH}")
    print(f"Chart written to {CHART_PATH}")


if __name__ == "__main__":
    main()
