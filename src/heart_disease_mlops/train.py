"""Training pipeline: model definitions, cross-validation, MLflow tracking."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from .config import (
    CV_FOLDS,
    MLRUNS_DIR,
    MODELS_DIR,
    RANDOM_STATE,
    REPORTS_DIR,
    ensure_dirs,
)
from .data import load_training_dataset, train_test_split_df
from .evaluate import evaluation_report
from .preprocessing import build_preprocessor


@dataclass
class ModelSpec:
    """Specification for a candidate model with optional grid search."""

    name: str
    estimator: Any
    param_grid: dict[str, list[Any]] = field(default_factory=dict)


def default_model_specs(fast: bool | None = None) -> list[ModelSpec]:
    """Return the default candidate models.

    When ``fast=True`` (or ``HEART_DISEASE_FAST_TRAIN=1`` is set in the
    environment), the grids are shrunk so CI smoke runs finish in seconds.
    """
    if fast is None:
        fast = os.getenv("HEART_DISEASE_FAST_TRAIN", "0") == "1"

    if fast:
        return [
            ModelSpec(
                name="logistic_regression",
                estimator=LogisticRegression(
                    max_iter=500, solver="liblinear", random_state=RANDOM_STATE
                ),
                param_grid={"classifier__C": [1.0]},
            ),
            ModelSpec(
                name="random_forest",
                estimator=RandomForestClassifier(
                    n_estimators=50, random_state=RANDOM_STATE, n_jobs=-1
                ),
                param_grid={"classifier__max_depth": [5]},
            ),
        ]

    return [
        ModelSpec(
            name="logistic_regression",
            estimator=LogisticRegression(
                max_iter=2000, solver="liblinear", random_state=RANDOM_STATE
            ),
            param_grid={
                "classifier__C": [0.1, 1.0, 10.0],
                "classifier__penalty": ["l1", "l2"],
            },
        ),
        ModelSpec(
            name="random_forest",
            estimator=RandomForestClassifier(
                n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1
            ),
            param_grid={
                "classifier__n_estimators": [200, 400],
                "classifier__max_depth": [None, 5, 10],
                "classifier__min_samples_split": [2, 5],
            },
        ),
    ]


def build_pipeline(estimator: Any) -> Pipeline:
    """Wrap an estimator with the standard preprocessing transformer."""
    return Pipeline(
        steps=[
            ("preprocess", build_preprocessor()),
            ("classifier", estimator),
        ]
    )


def cross_validate_pipeline(
    pipeline: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    scoring: str = "roc_auc",
    cv: int = CV_FOLDS,
) -> dict[str, float]:
    """Stratified K-fold cross-validation summary."""
    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_val_score(pipeline, X, y, scoring=scoring, cv=skf, n_jobs=-1)
    return {
        "scoring": scoring,
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "scores": [float(s) for s in scores],
    }


def tune_model(
    spec: ModelSpec,
    X: pd.DataFrame,
    y: pd.Series,
    cv: int = CV_FOLDS,
    scoring: str = "roc_auc",
) -> GridSearchCV:
    """Run grid search over the spec's hyperparameter grid."""
    pipeline = build_pipeline(spec.estimator)
    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=RANDOM_STATE)
    grid = GridSearchCV(
        pipeline,
        param_grid=spec.param_grid or {},
        scoring=scoring,
        cv=skf,
        n_jobs=-1,
        refit=True,
    )
    grid.fit(X, y)
    return grid


def _setup_mlflow(experiment_name: str = "heart-disease-cleveland") -> None:
    ensure_dirs()
    MLRUNS_DIR.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(MLRUNS_DIR.resolve().as_uri())
    mlflow.set_experiment(experiment_name)


def train_and_log_all(
    experiment_name: str = "heart-disease-cleveland",
    specs: list[ModelSpec] | None = None,
    include_feedback: bool = True,
) -> dict[str, Any]:
    """Train all candidate models, log to MLflow, persist the best one.

    When ``include_feedback=True`` (default), any rows accumulated in
    ``data/feedback/feedback.csv`` are appended to the training set so the
    model improves from user-corrected predictions.

    Returns a dict with per-model results and the selected best model info.
    """
    ensure_dirs()
    _setup_mlflow(experiment_name)

    df = load_training_dataset(include_feedback=include_feedback)
    from .data import load_feedback

    n_feedback = len(load_feedback()) if include_feedback else 0
    X_train, X_test, y_train, y_test = train_test_split_df(df)
    specs = specs or default_model_specs()

    results: dict[str, dict[str, Any]] = {}
    best_name: str | None = None
    best_score: float = -np.inf
    best_estimator: Pipeline | None = None

    for spec in specs:
        with mlflow.start_run(run_name=spec.name) as run:
            grid = tune_model(spec, X_train, y_train)
            best_pipe: Pipeline = grid.best_estimator_

            cv_summary = {
                "cv_best_score": float(grid.best_score_),
                "cv_scoring": "roc_auc",
                "cv_folds": CV_FOLDS,
            }
            test_eval = evaluation_report(best_pipe, X_test, y_test)

            mlflow.log_params({f"best_{k}": v for k, v in grid.best_params_.items()})
            mlflow.log_param("model_family", spec.name)
            mlflow.log_param("cv_scoring", cv_summary["cv_scoring"])
            mlflow.log_param("cv_folds", cv_summary["cv_folds"])
            mlflow.log_param("n_train_rows", int(len(X_train)))
            mlflow.log_param("n_feedback_rows", int(n_feedback))
            mlflow.log_metric("cv_best_score", cv_summary["cv_best_score"])
            mlflow.log_metrics({f"test_{k}": v for k, v in test_eval["metrics"].items()})

            report_path = REPORTS_DIR / f"{spec.name}_classification_report.txt"
            report_path.write_text(test_eval["classification_report"], encoding="utf-8")
            mlflow.log_artifact(str(report_path))

            mlflow.sklearn.log_model(best_pipe, artifact_path="model")

            results[spec.name] = {
                "run_id": run.info.run_id,
                "best_params": grid.best_params_,
                **cv_summary,
                "test_metrics": test_eval["metrics"],
            }

            score = test_eval["metrics"].get("roc_auc", test_eval["metrics"]["f1"])
            if score > best_score:
                best_score = score
                best_name = spec.name
                best_estimator = best_pipe

    assert best_estimator is not None and best_name is not None

    model_path = MODELS_DIR / "best_model.joblib"
    joblib.dump(best_estimator, model_path)

    # Register the best model in the MLflow Model Registry (file-based store).
    try:
        with mlflow.start_run(run_name=f"register_{best_name}") as reg_run:
            mlflow.log_param("promoted_model", best_name)
            mlflow.log_metric("promoted_score", float(best_score))
            mlflow.sklearn.log_model(
                best_estimator,
                artifact_path="model",
                registered_model_name="heart-disease-classifier",
            )
            register_run_id: str | None = reg_run.info.run_id
    except Exception as exc:  # pragma: no cover - registry can fail on file backend
        register_run_id = None
        print(f"[warn] model registry step skipped: {exc}")

    summary = {
        "best_model": best_name,
        "best_score": best_score,
        "model_path": str(model_path),
        "trained_at": datetime.now(UTC).isoformat(),
        "register_run_id": register_run_id,
        "n_train_rows": int(len(X_train)),
        "n_test_rows": int(len(X_test)),
        "n_feedback_rows": int(n_feedback),
        "results": results,
    }
    (REPORTS_DIR / "training_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    return summary


def load_model(path: Path | str = MODELS_DIR / "best_model.joblib") -> Pipeline:
    """Load a previously trained pipeline from disk."""
    return joblib.load(path)


def _cli() -> None:
    """Console-script entry point: ``heart-disease-train``."""
    print(json.dumps(train_and_log_all(), indent=2, default=str))

if __name__ == "__main__":
    summary = train_and_log_all()
    print(json.dumps(summary, indent=2))
