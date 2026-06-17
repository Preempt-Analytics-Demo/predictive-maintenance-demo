# tests/test_modeling_pipeline_smoke.py
#
# ── Why this test exists ────────────────────────────────────────────────────
# This is the test that would have caught the RNF class-gap bug (see
# feature_transformation.py) months before it reached CI: training every one
# of the 12 model families on a small synthetic dataset, in seconds, with no
# real data or MLflow connection. It does not check accuracy — only that
# train_model() runs to completion without raising for every experiment.

import pandas as pd
import pytest

from modeling_pipeline import EXPERIMENTS, train_model

# 15 rows per group comfortably clears train_test_split's stratify requirement
# at test_size=0.2 (params.yaml) — each class needs at least a couple of rows
# in both the train and test split.
ROWS_PER_GROUP = 15

# Each group sets exactly one multiclass failure flag, matching how
# resolve_label() in modeling_pipeline.py derives failure_type: whichever of
# twf/hdf/pwf/osf is 1 wins; none of them set => "none". RNF is omitted on
# purpose — sensor_simulator.py never injects it (see feature_transformation.py).
FAILURE_FLAG_GROUPS = [
    {"TWF": 0, "HDF": 0, "PWF": 0, "OSF": 0, "Machine failure": 0},  # -> "none"
    {"TWF": 1, "HDF": 0, "PWF": 0, "OSF": 0, "Machine failure": 1},  # -> "twf"
    {"TWF": 0, "HDF": 1, "PWF": 0, "OSF": 0, "Machine failure": 1},  # -> "hdf"
    {"TWF": 0, "HDF": 0, "PWF": 1, "OSF": 0, "Machine failure": 1},  # -> "pwf"
    {"TWF": 0, "HDF": 0, "PWF": 0, "OSF": 1, "Machine failure": 1},  # -> "osf"
]


def _synthetic_ai4i_dataframe() -> pd.DataFrame:
    """Build a small DataFrame in the original AI4I column format.

    Covers every failure type (for multiclass) and both machine_failure
    classes (for binary) with enough rows per class to survive a stratified
    train/test split. Sensor values are jittered per row so classifiers that
    care about feature variance (logreg, SVM, MLP) don't choke on constant
    columns.
    """
    rows = []
    types = ["L", "M", "H"]
    for group in FAILURE_FLAG_GROUPS:
        for i in range(ROWS_PER_GROUP):
            rows.append({
                "Type":                      types[i % 3],
                "Air temperature [K]":       295.0 + i * 0.3,
                "Process temperature [K]":   305.0 + i * 0.3,
                "Rotational speed [rpm]":    1300 + i * 5,
                "Torque [Nm]":               25.0 + i * 0.5,
                "Tool wear [min]":           10 + i * 2,
                "Machine failure":           group["Machine failure"],
                "TWF":                       group["TWF"],
                "HDF":                       group["HDF"],
                "PWF":                       group["PWF"],
                "OSF":                       group["OSF"],
                "RNF":                       0,   # never injected — see feature_transformation.py
            })
    return pd.DataFrame(rows)


@pytest.mark.parametrize("experiment_name", list(EXPERIMENTS.keys()))
def test_train_model_runs_without_raising(experiment_name):
    config = EXPERIMENTS[experiment_name]
    df     = _synthetic_ai4i_dataframe()

    pipeline, metrics, params = train_model(df, config)

    assert pipeline is not None
    assert "f1_test" in metrics
