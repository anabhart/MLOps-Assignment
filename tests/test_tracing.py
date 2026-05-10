"""Sanity tests for MLflow tracing wiring (no MLflow server required)."""

from __future__ import annotations

import mlflow

from api.tracing import setup_tracing


def test_setup_tracing_returns_true():
    assert setup_tracing() is True
    # Active experiment should be the serving one.
    exp = mlflow.get_experiment_by_name("heart-disease-serving")
    assert exp is not None


def test_setup_tracing_disabled_via_env(monkeypatch):
    # Reset module flag so the env var is honoured.
    import api.tracing as tracing_mod

    monkeypatch.setattr(tracing_mod, "_initialised", False)
    monkeypatch.setenv("HEART_DISEASE_DISABLE_TRACING", "1")
    assert tracing_mod.setup_tracing() is False


def test_trace_decorator_runs_without_error():
    @mlflow.trace(name="dummy_trace_test")
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5
