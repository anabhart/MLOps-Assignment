"""Tests for the feedback loop: append_feedback, /feedback, /retrain, UI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def isolated_feedback(tmp_path, monkeypatch):
    """Redirect FEEDBACK_PATH to a temp file for the duration of the test."""
    feedback_file = tmp_path / "feedback.csv"
    from api import app as api_app
    from heart_disease_mlops import config, data

    monkeypatch.setattr(config, "FEEDBACK_PATH", feedback_file)
    monkeypatch.setattr(data, "FEEDBACK_PATH", feedback_file)
    monkeypatch.setattr(api_app, "FEEDBACK_PATH", feedback_file)
    return feedback_file


def test_append_feedback_creates_csv(isolated_feedback, tmp_path):
    from heart_disease_mlops.data import append_feedback, load_feedback

    features = {
        "age": 55, "sex": 1, "cp": 4, "trestbps": 130, "chol": 250,
        "fbs": 0, "restecg": 1, "thalach": 140, "exang": 1,
        "oldpeak": 1.5, "slope": 2, "ca": 1, "thal": 7,
    }
    path = append_feedback(features, true_label=1, path=isolated_feedback)
    assert path.exists()

    df = load_feedback(isolated_feedback)
    assert len(df) == 1
    assert df.iloc[0]["target"] == 1
    assert df.iloc[0]["age"] == 55
    assert "submitted_at" in df.columns


def test_append_feedback_rejects_invalid_label(isolated_feedback):
    from heart_disease_mlops.data import append_feedback

    with pytest.raises(ValueError):
        append_feedback({"age": 50}, true_label=2, path=isolated_feedback)


def test_load_training_dataset_includes_feedback(isolated_feedback):
    from heart_disease_mlops.data import (
        append_feedback,
        load_clean_cleveland,
        load_training_dataset,
    )

    base_n = len(load_clean_cleveland())
    features = {
        "age": 55, "sex": 1, "cp": 4, "trestbps": 130, "chol": 250,
        "fbs": 0, "restecg": 1, "thalach": 140, "exang": 1,
        "oldpeak": 1.5, "slope": 2, "ca": 1, "thal": 7,
    }
    append_feedback(features, true_label=1, path=isolated_feedback)
    augmented = load_training_dataset(
        include_feedback=True, feedback_path=isolated_feedback
    )
    assert len(augmented) == base_n + 1


# ---------------------------------------------------------------------------
# API integration: reuse the module-scoped trained_client from test_api.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def trained_client(tmp_path_factory):
    os.environ["HEART_DISEASE_FAST_TRAIN"] = "1"
    from heart_disease_mlops.train import train_and_log_all

    summary = train_and_log_all(experiment_name="feedback-tests")
    os.environ["HEART_DISEASE_MODEL_PATH"] = summary["model_path"]

    from api.app import app

    with TestClient(app) as client:
        yield client


def _example_payload() -> dict:
    return json.loads(Path("api/example_requests.json").read_text())[0]


def test_feedback_endpoint_persists_row(trained_client: TestClient, tmp_path, monkeypatch):
    feedback_file = tmp_path / "feedback_api.csv"
    from api import app as api_app
    from heart_disease_mlops import config, data

    monkeypatch.setattr(config, "FEEDBACK_PATH", feedback_file)
    monkeypatch.setattr(data, "FEEDBACK_PATH", feedback_file)
    monkeypatch.setattr(api_app, "FEEDBACK_PATH", feedback_file)

    payload = {
        "features": _example_payload(),
        "true_label": 1,
        "predicted_label": 0,
        "probability": 0.42,
    }
    r = trained_client.post("/feedback", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] is True
    assert body["total_feedback_rows"] == 1
    assert body["correct"] is False
    assert feedback_file.exists()


def test_feedback_endpoint_rejects_bad_label(trained_client: TestClient):
    payload = {"features": _example_payload(), "true_label": 7}
    r = trained_client.post("/feedback", json=payload)
    assert r.status_code == 422  # Pydantic ge/le validation


def test_retrain_endpoint_schedules_job(trained_client: TestClient, monkeypatch):
    """/retrain should accept the request and schedule a background job.

    We monkeypatch the heavy training function so the test stays fast.
    """
    calls: list[int] = []

    def fake_run_retrain(job_id: int) -> None:
        calls.append(job_id)

    from api import app as api_app

    monkeypatch.setattr(api_app, "_run_retrain", fake_run_retrain)
    # Also reset the busy flag in case earlier tests left it set.
    api_app._State.retrain_busy = False

    r = trained_client.post("/retrain")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "scheduled"
    assert isinstance(body["job_id"], int)
    # Background task runs synchronously after response in TestClient.
    assert calls == [body["job_id"]]


def test_ui_index_served(trained_client: TestClient):
    r = trained_client.get("/ui")
    assert r.status_code == 200
    assert "Heart Disease" in r.text
    # Static asset reachable as well.
    css = trained_client.get("/ui/static/styles.css")
    assert css.status_code == 200
