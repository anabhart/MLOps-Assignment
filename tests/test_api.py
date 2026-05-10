"""Tests for the FastAPI service. Uses TestClient (sync, no event loop)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def trained_client(tmp_path_factory):
    """Train a tiny model once, then build a TestClient pointing at it."""
    os.environ["HEART_DISEASE_FAST_TRAIN"] = "1"

    # Train (writes artifacts/models/best_model.joblib + summary).
    from heart_disease_mlops.train import train_and_log_all

    summary = train_and_log_all(experiment_name="api-tests")
    os.environ["HEART_DISEASE_MODEL_PATH"] = summary["model_path"]

    # Import after the model exists so lifespan loads it.
    from api.app import app

    with TestClient(app) as client:
        yield client


def test_health_endpoint(trained_client: TestClient):
    r = trained_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] == "True"


def test_model_info_endpoint(trained_client: TestClient):
    r = trained_client.get("/model-info")
    assert r.status_code == 200
    body = r.json()
    assert body["model_loaded"] is True
    assert body["best_model"] in {"logistic_regression", "random_forest"}
    assert body["test_metrics"] is not None


def test_predict_endpoint_with_sample_payload(trained_client: TestClient):
    examples = json.loads(Path("api/example_requests.json").read_text())
    for payload in examples:
        r = trained_client.post("/predict", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["prediction"] in (0, 1)
        assert body["label"] in {"disease", "no_disease"}
        assert 0.0 <= body["probability"] <= 1.0


def test_predict_validation_error(trained_client: TestClient):
    bad_payload = {"age": 999}  # missing fields + out-of-range
    r = trained_client.post("/predict", json=bad_payload)
    assert r.status_code == 422


def test_metrics_endpoint(trained_client: TestClient):
    # Trigger one prediction so counters are non-zero.
    payload = json.loads(Path("api/example_requests.json").read_text())[0]
    trained_client.post("/predict", json=payload)
    r = trained_client.get("/metrics")
    assert r.status_code == 200
    text = r.text
    assert "predict_requests_total" in text
    assert "predict_latency_seconds" in text
