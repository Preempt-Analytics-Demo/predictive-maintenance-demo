"""
Predictive Maintenance — Modeling Pipeline
==========================================
Trains a failure classifier on the AI4I 2020 dataset and logs results to MLflow.

Supported experiments (pass via --experiment):
    xgb_binary,   xgb_multiclass
    rf_binary,    rf_multiclass
    logreg_binary, logreg_multiclass
    lgbm_binary,  lgbm_multiclass

Usage:
    python modeling_pipeline.py --experiment xgb_binary
    python modeling_pipeline.py --experiment xgb_binary --cml-run
    python modeling_pipeline.py --experiment rf_binary
    ...
    Additional experiments can be added to the EXPERIMENTS registry with a new config
    and run via the script .
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import click
import mlflow
import pandas as pd
import xgboost as xgb
import lightgbm as lgb
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline

load_dotenv()

DATA_PATH = Path("data/ai4i2020.csv")

COLUMN_RENAME = {
    "Type": "type",
    "Air temperature [K]": "air_temperature_kelvin",
    "Process temperature [K]": "process_temperature_kelvin",
    "Rotational speed [rpm]": "rotational_speed_rpm",
    "Torque [Nm]": "torque_nm",
    "Tool wear [min]": "tool_wear_minutes",
    "Machine failure": "machine_failure",
    "TWF": "twf",
    "HDF": "hdf",
    "PWF": "pwf",
    "OSF": "osf",
    "RNF": "rnf",
}

FEATURES = [
    "type",
    "air_temperature_kelvin",
    "process_temperature_kelvin",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_minutes",
    "power_kw",
    "temp_diff_kelvin",
    "mechanical_stress",
]


# ── Experiment registry ────────────────────────────────────────────────────────

@dataclass
class ExperimentConfig:
    """Single source of truth for one experiment.

    classifier_factory receives the imbalance_ratio (float) and returns an
    unfitted classifier. Multiclass factories ignore it (lambda _).
    metric_average is passed directly to sklearn scoring functions — "binary"
    for binary targets, "macro" for multiclass.
    """
    experiment_name: str
    registered_model_name: str
    model_family: str
    target: str
    target_type: str       # "binary" or "multiclass"
    metric_average: str    # "binary" or "macro"
    classifier_factory: Callable
    test_size: float = 0.2
    description: str = ""
    notes: Optional[str] = None
    tags: dict = field(default_factory=dict)


EXPERIMENTS: dict[str, ExperimentConfig] = {
    "xgb_binary": ExperimentConfig(
        experiment_name="predictive-maintenance/xgboost/binary",
        registered_model_name="xgboost-binary",
        model_family="xgboost",
        target="machine_failure",
        target_type="binary",
        metric_average="binary",
        # scale_pos_weight compensates for ~97:3 class imbalance without resampling
        classifier_factory=lambda r: xgb.XGBClassifier(
            n_estimators=200, scale_pos_weight=r,
            random_state=42, n_jobs=-1, eval_metric="logloss",
        ),
    ),

    "xgb_multiclass": ExperimentConfig(
        experiment_name="predictive-maintenance/xgboost/multiclass",
        registered_model_name="xgboost-multiclass",
        model_family="xgboost",
        target="failure_type",
        target_type="multiclass",
        metric_average="macro",
        classifier_factory=lambda _: xgb.XGBClassifier(
            n_estimators=200, objective="multi:softprob",
            random_state=42, n_jobs=-1, eval_metric="mlogloss",
        ),
    ),

    "lgbm_binary": ExperimentConfig(
        experiment_name="predictive-maintenance/lightgbm/binary",
        registered_model_name="lightgbm-binary",
        model_family="lightgbm",
        target="machine_failure",
        target_type="binary",
        metric_average="binary",
        classifier_factory=lambda r: lgb.LGBMClassifier(
            n_estimators=200,
            scale_pos_weight=r,
            random_state=42,
            n_jobs=-1,
        ),
    ),

    "lgbm_multiclass": ExperimentConfig(
        experiment_name="predictive-maintenance/lightgbm/multiclass",
        registered_model_name="lightgbm-multiclass",
        model_family="lightgbm",
        target="failure_type",
        target_type="multiclass",
        metric_average="macro",
        classifier_factory=lambda _: lgb.LGBMClassifier(
            n_estimators=200,
            objective="multiclass",
            random_state=42,
            n_jobs=-1,
        ),
    ),
    "rf_binary": ExperimentConfig(
        experiment_name="predictive-maintenance/random-forest/binary",
        registered_model_name="random-forest-binary",
        model_family="random_forest",
        target="machine_failure",
        target_type="binary",
        metric_average="binary",
        classifier_factory=lambda _: RandomForestClassifier(
            class_weight="balanced", n_estimators=100, random_state=42, n_jobs=-1,
        ),
    ),
    "rf_multiclass": ExperimentConfig(
        experiment_name="predictive-maintenance/random-forest/multiclass",
        registered_model_name="random-forest-multiclass",
        model_family="random_forest",
        target="failure_type",
        target_type="multiclass",
        metric_average="macro",
        classifier_factory=lambda _: RandomForestClassifier(
            class_weight="balanced", n_estimators=100, random_state=42, n_jobs=-1,
        ),
    ),
    "logreg_binary": ExperimentConfig(
        experiment_name="predictive-maintenance/logreg/binary",
        registered_model_name="logreg-binary",
        model_family="logreg",
        target="machine_failure",
        target_type="binary",
        metric_average="binary",
        classifier_factory=lambda _: LogisticRegression(
            class_weight="balanced", max_iter=1000, random_state=42,
        ),
    ),
    "logreg_multiclass": ExperimentConfig(
        experiment_name="predictive-maintenance/logistic-regression/multiclass",
        registered_model_name="logreg-multiclass",
        model_family="logreg",
        target="failure_type",
        target_type="multiclass",
        metric_average="macro",
        classifier_factory=lambda _: LogisticRegression(
            class_weight="balanced", max_iter=1000, random_state=42,
        ),
    ),
}


# ── Preprocessing ──────────────────────────────────────────────────────────────

def preprocess(df: pd.DataFrame, config: ExperimentConfig) -> pd.DataFrame:
    """Return a DataFrame containing FEATURES + target column only.

    Derived features are grounded in EDA findings:
    - power_kw: torque × rpm converted to kW — failures cluster at power extremes
    - temp_diff_kelvin: process − air temperature — HDF boundary correlates with low diff + low rpm
    - mechanical_stress: torque × tool wear — captures compounded wear hazard
    DictVectorizer in the downstream pipeline handles one-hot encoding of 'type'.
    """
    df = df.copy().rename(columns=COLUMN_RENAME)

    df["power_kw"] = (df["torque_nm"] * df["rotational_speed_rpm"] * 2 * 3.14159 / 60) / 1000
    df["temp_diff_kelvin"] = df["process_temperature_kelvin"] - df["air_temperature_kelvin"]
    df["mechanical_stress"] = df["torque_nm"] * df["tool_wear_minutes"]

    if config.target_type == "multiclass":
        failure_cols = ["twf", "hdf", "pwf", "osf", "rnf"]
        def resolve_label(row):
            active = [c for c in failure_cols if row[c] == 1]
            return active[0] if active else "none"
        df["failure_type"] = df.apply(resolve_label, axis=1)

    return df[FEATURES + [config.target]]


# ── Classifier builder ─────────────────────────────────────────────────────────

def _build_classifier(config: ExperimentConfig, imbalance_ratio: float):
    """Delegate classifier construction to the factory stored in config."""
    return config.classifier_factory(imbalance_ratio)


# ── Training ───────────────────────────────────────────────────────────────────

def train_model(df: pd.DataFrame, config: ExperimentConfig):
    """Preprocess, split, train, and evaluate. Return (pipeline, metrics, params).

    Stratified split preserves the minority-class ratio in both folds.
    ROC-AUC is only meaningful for binary targets and is skipped for multiclass.
    """
    df_processed = preprocess(df, config)
    y = df_processed[config.target]
    X = df_processed.drop(columns=[config.target])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, random_state=42, test_size=config.test_size, stratify=y
    )

    # Guard against ZeroDivisionError: multiclass y_train holds string labels,
    # so integer comparisons would produce 0/0.
    if config.target_type == "binary":
        imbalance_ratio = (y_train == 0).sum() / (y_train == 1).sum()
    else:
        imbalance_ratio = 1.0  # ignored by multiclass factories (lambda _)

    classifier = _build_classifier(config, imbalance_ratio)

    X_train_records = X_train.to_dict(orient="records")
    X_test_records = X_test.to_dict(orient="records")

    pipeline = make_pipeline(DictVectorizer(), classifier)
    pipeline.fit(X_train_records, y_train)

    y_pred_train = pipeline.predict(X_train_records)
    y_pred_test = pipeline.predict(X_test_records)

    y_prob_test = (
        pipeline.predict_proba(X_test_records)[:, 1]
        if config.target_type == "binary"
        else None
    )

    average = config.metric_average
    metrics: dict[str, float] = {
        "f1_train":       f1_score(y_train, y_pred_train, average=average),
        "f1_test":        f1_score(y_test, y_pred_test, average=average),
        "precision_test": precision_score(y_test, y_pred_test, average=average),
        "recall_test":    recall_score(y_test, y_pred_test, average=average),
    }
    if y_prob_test is not None:
        metrics["roc_auc_test"] = roc_auc_score(y_test, y_prob_test)

    params: dict[str, object] = {
        **classifier.get_params(),
        "model_family": config.model_family,
        "target_type": config.target_type,
        "test_size": config.test_size,
    }

    return pipeline, metrics, params


# ── MLflow ─────────────────────────────────────────────────────────────────────

def configure_mlflow(config: ExperimentConfig) -> None:
    """Point MLflow at the remote tracking server and select the experiment."""
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        raise EnvironmentError("MLFLOW_TRACKING_URI is not set in the environment.")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(config.experiment_name)


def log_model(
    pipeline, metrics: dict, params: dict, config: ExperimentConfig
) -> None:
    """Log a single MLflow run and register the model artifact."""
    with mlflow.start_run():
        mlflow.set_tags({
            "model_family": config.model_family,
            "target_type": config.target_type,
            "target": config.target,
            "experiment_name": config.experiment_name,
            "developer": os.getenv("MLFLOW_TRACKING_USERNAME", "unknown"),
        })
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(
            pipeline,
            artifact_path="model",
            registered_model_name=config.registered_model_name,
        )


# ── CML report ─────────────────────────────────────────────────────────────────

def write_cml_metrics(metrics: dict) -> None:
    """Write test metrics to metrics.txt for a CML pull-request report."""
    lines = [
        "# Training Metrics",
        "",
        f"f1_test:        {metrics['f1_test']:.4f}",
        f"precision_test: {metrics['precision_test']:.4f}",
        f"recall_test:    {metrics['recall_test']:.4f}",
    ]
    if "roc_auc_test" in metrics:
        lines.append(f"roc_auc_test:   {metrics['roc_auc_test']:.4f}")
    Path("metrics.txt").write_text("\n".join(lines), encoding="utf-8")


# ── Entry point ────────────────────────────────────────────────────────────────

@click.command()
@click.option(
    "--experiment",
    default="xgb_binary",
    type=click.Choice(list(EXPERIMENTS)),
    show_default=True,
    help="Which experiment config to use.",
)
@click.option(
    "--cml-run/--no-cml-run",
    default=False,
    help="Write metrics.txt for a CML pull request report.",
)
def main(experiment: str, cml_run: bool) -> None:
    """Train a predictive maintenance failure classifier."""
    config = EXPERIMENTS[experiment]

    df = pd.read_csv(DATA_PATH)
    configure_mlflow(config)

    pipeline, metrics, params = train_model(df, config)
    log_model(pipeline, metrics, params, config)

    if cml_run:
        write_cml_metrics(metrics)


if __name__ == "__main__":
    main()
