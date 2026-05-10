"""Tests for training utilities and end-to-end smoke."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from heart_disease_mlops.config import RANDOM_STATE
from heart_disease_mlops.data import train_test_split_df
from heart_disease_mlops.train import (
    build_pipeline,
    cross_validate_pipeline,
    default_model_specs,
    train_and_log_all,
)


def test_build_pipeline_fits_and_predicts(cleaned_df):
    X_train, X_test, y_train, y_test = train_test_split_df(cleaned_df)
    pipe = build_pipeline(LogisticRegression(max_iter=500, random_state=RANDOM_STATE))
    pipe.fit(X_train, y_train)
    preds = pipe.predict(X_test)
    assert preds.shape == (len(X_test),)
    assert set(np.unique(preds)).issubset({0, 1})


def test_cross_validate_pipeline_returns_valid_scores(cleaned_df):
    X_train, _, y_train, _ = train_test_split_df(cleaned_df)
    pipe = build_pipeline(LogisticRegression(max_iter=500, random_state=RANDOM_STATE))
    summary = cross_validate_pipeline(pipe, X_train, y_train, cv=3)
    assert 0.0 <= summary["mean"] <= 1.0
    assert summary["std"] >= 0.0
    assert len(summary["scores"]) == 3


def test_default_model_specs_fast_mode_smaller_grids():
    full = default_model_specs(fast=False)
    fast = default_model_specs(fast=True)
    full_combos = sum(
        max(1, sum(len(v) for v in s.param_grid.values())) for s in full
    )
    fast_combos = sum(
        max(1, sum(len(v) for v in s.param_grid.values())) for s in fast
    )
    assert fast_combos < full_combos


@pytest.mark.slow
def test_train_and_log_all_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Run the full training entry point in fast mode and validate artifacts."""
    monkeypatch.setenv("HEART_DISEASE_FAST_TRAIN", "1")

    summary = train_and_log_all(experiment_name="ci-smoke")

    assert summary["best_model"] in {"logistic_regression", "random_forest"}
    assert Path(summary["model_path"]).exists()
    # Sanity: model should beat trivial baseline by a wide margin.
    test_metrics = summary["results"][summary["best_model"]]["test_metrics"]
    assert test_metrics.get("roc_auc", test_metrics["f1"]) > 0.7
