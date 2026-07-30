# tests/test_data_contract.py
#
# ── Why this test exists ────────────────────────────────────────────────────
# UDI 1-10000 in data/ai4i2020.parquet is supposed to be the untouched original
# AI4I baseline (3.39% failure rate) forever -- export_simulation_to_parquet.py
# never trims or rewrites it, only appends simulated rows above it. On
# 2026-07-30 that partition was found silently overwritten with synthetic rows
# (failure rate had drifted to ~15-19%) after a dvc-pull-skipping bug let a
# retrain run start a fresh file at UDI=1. Nothing caught it until a human
# noticed a suspiciously perfect production metric. This test is the automated
# check that incident didn't have: it fails loudly the moment the baseline
# partition drifts, instead of silently retraining every model on corrupted
# ground truth.
#
# Skipped when data/ai4i2020.parquet isn't present locally (e.g. the CI step
# that runs this suite executes before `dvc pull`, per retrain.yml) -- it has
# nothing to check without the file, and skipping beats failing for a reason
# unrelated to the thing being tested.

from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARQUET_PATH = PROJECT_ROOT / "data" / "ai4i2020.parquet"
BASELINE_ROW_COUNT = 10_000          # matches export_simulation_to_parquet.py
REAL_FAILURE_RATE = 0.0339           # 339 / 10,000 -- the published AI4I 2020 rate
TOLERANCE = 0.01                     # +-1 percentage point; rounding/precision only, not drift


@pytest.mark.skipif(not PARQUET_PATH.exists(), reason="data/ai4i2020.parquet not pulled locally")
def test_baseline_partition_failure_rate_matches_original_ai4i_dataset():
    df = pd.read_parquet(PARQUET_PATH)
    baseline = df[df["UDI"] <= BASELINE_ROW_COUNT]

    assert len(baseline) == BASELINE_ROW_COUNT, (
        f"Expected exactly {BASELINE_ROW_COUNT} baseline rows (UDI<=10000), "
        f"found {len(baseline)}. The baseline partition's row count itself has changed."
    )

    observed_rate = baseline["Machine failure"].mean()
    assert abs(observed_rate - REAL_FAILURE_RATE) <= TOLERANCE, (
        f"Baseline partition (UDI<=10000) failure rate is {observed_rate:.4f}, "
        f"expected ~{REAL_FAILURE_RATE:.4f}. This is the exact signature of the "
        "2026-07-30 incident: synthetic rows overwriting the reserved baseline "
        "UDI range. Do not train on this file until data/ai4i2020_baseline.csv "
        "is re-merged into UDI<=10000 (see scripts/export_simulation_to_parquet.py)."
    )
