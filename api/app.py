"""FastAPI service exposing the heart-disease classifier."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from itertools import count
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

from heart_disease_mlops.config import (
    CATEGORICAL_FEATURES,
    FEEDBACK_PATH,
    MODELS_DIR,
    NUMERIC_FEATURES,
    REPORTS_DIR,
)
from heart_disease_mlops.data import append_feedback, load_feedback

from .logging_config import configure_logging

logger = logging.getLogger("heart_disease_api")

MODEL_PATH = Path(os.getenv("HEART_DISEASE_MODEL_PATH", MODELS_DIR / "best_model.joblib"))
SUMMARY_PATH = REPORTS_DIR / "training_summary.json"

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
REQUESTS = Counter(
    "predict_requests_total",
    "Total number of /predict requests.",
    labelnames=("status",),
)
LATENCY = Histogram(
    "predict_latency_seconds",
    "Latency of /predict requests in seconds.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
PREDICTIONS = Counter(
    "predict_predictions_total",
    "Number of predictions broken down by predicted class.",
    labelnames=("label",),
)
FEEDBACK = Counter(
    "feedback_submissions_total",
    "Number of feedback submissions, labelled by correctness.",
    labelnames=("correct",),
)
RETRAIN_RUNS = Counter(
    "retrain_runs_total",
    "Number of retraining runs by status.",
    labelnames=("status",),
)
FEEDBACK_ROWS = Gauge(
    "feedback_rows",
    "Total number of feedback rows currently saved.",
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
class PatientFeatures(BaseModel):
    """Single patient record. Field ranges follow the UCI documentation."""

    age: float = Field(..., ge=1, le=120)
    sex: int = Field(..., ge=0, le=1, description="1 = male, 0 = female")
    cp: int = Field(..., ge=1, le=4, description="Chest pain type 1-4")
    trestbps: float = Field(..., ge=50, le=260, description="Resting blood pressure (mm Hg)")
    chol: float = Field(..., ge=50, le=700, description="Serum cholesterol (mg/dl)")
    fbs: int = Field(..., ge=0, le=1, description="Fasting blood sugar > 120 mg/dl")
    restecg: int = Field(..., ge=0, le=2)
    thalach: float = Field(..., ge=40, le=260, description="Max heart rate achieved")
    exang: int = Field(..., ge=0, le=1, description="Exercise induced angina")
    oldpeak: float = Field(..., ge=-2.0, le=10.0)
    slope: int = Field(..., ge=1, le=3)
    ca: int = Field(..., ge=0, le=3)
    thal: int = Field(..., description="3 = normal, 6 = fixed defect, 7 = reversible defect")

    model_config = {
        "json_schema_extra": {
            "example": {
                "age": 63, "sex": 1, "cp": 1, "trestbps": 145, "chol": 233,
                "fbs": 1, "restecg": 2, "thalach": 150, "exang": 0,
                "oldpeak": 2.3, "slope": 3, "ca": 0, "thal": 6,
            }
        }
    }


class PredictionResponse(BaseModel):
    prediction: int = Field(..., description="0 = no disease, 1 = disease")
    label: str = Field(..., description="Human-readable label")
    probability: float = Field(..., ge=0.0, le=1.0, description="P(disease)")


class ModelInfo(BaseModel):
    best_model: str | None = None
    trained_at: str | None = None
    test_metrics: dict[str, float] | None = None
    model_path: str
    model_loaded: bool


class FeedbackPayload(BaseModel):
    """User feedback for a single prediction."""

    features: PatientFeatures
    true_label: int = Field(..., ge=0, le=1, description="Actual diagnosis (0/1)")
    predicted_label: int | None = Field(default=None, ge=0, le=1)
    probability: float | None = Field(default=None, ge=0.0, le=1.0)


class FeedbackResponse(BaseModel):
    saved: bool
    feedback_path: str
    total_feedback_rows: int
    correct: bool | None = None


class RetrainResponse(BaseModel):
    job_id: int
    status: str
    message: str


# ---------------------------------------------------------------------------
# App + model lifecycle
# ---------------------------------------------------------------------------
class _State:
    model: Any | None = None
    summary: dict | None = None
    retrain_lock: threading.Lock = threading.Lock()
    retrain_busy: bool = False
    job_counter = count(1)


def _load_model() -> Any | None:
    if not MODEL_PATH.exists():
        logger.warning("Model file %s does not exist; /predict will 503 until trained.", MODEL_PATH)
        return None
    logger.info("Loading model from %s", MODEL_PATH)
    return joblib.load(MODEL_PATH)


def _load_summary() -> dict | None:
    if not SUMMARY_PATH.exists():
        return None
    try:
        return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.exception("Failed to parse training summary at %s", SUMMARY_PATH)
        return None


def _refresh_feedback_gauge() -> None:
    try:
        FEEDBACK_ROWS.set(len(load_feedback(FEEDBACK_PATH)))
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to update feedback gauge")


def _run_retrain(job_id: int) -> None:
    """Background task: retrain (incl. feedback), reload model on success."""
    from heart_disease_mlops.train import train_and_log_all

    if _State.retrain_busy:
        logger.warning("Retrain job %d skipped: another job is in progress", job_id)
        RETRAIN_RUNS.labels(status="skipped").inc()
        return

    with _State.retrain_lock:
        _State.retrain_busy = True

    try:
        logger.info("Retrain job %d starting", job_id)
        summary = train_and_log_all(
            experiment_name="heart-disease-feedback-retrain",
            include_feedback=True,
        )
        # Hot-reload the model + summary so subsequent /predict uses it.
        _State.model = _load_model()
        _State.summary = _load_summary()
        RETRAIN_RUNS.labels(status="success").inc()
        logger.info(
            "Retrain job %d finished: best=%s score=%.4f n_feedback=%s",
            job_id,
            summary.get("best_model"),
            summary.get("best_score", 0.0),
            summary.get("n_feedback_rows", 0),
        )
    except Exception:  # pragma: no cover - logged for ops
        RETRAIN_RUNS.labels(status="failure").inc()
        logger.exception("Retrain job %d failed", job_id)
    finally:
        _State.retrain_busy = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    _State.model = _load_model()
    _State.summary = _load_summary()
    _refresh_feedback_gauge()
    yield
    _State.model = None


app = FastAPI(
    title="Heart Disease Classifier API",
    description=(
        "Predicts the risk of heart disease from the UCI Cleveland 13-feature "
        "patient record. Trained model is loaded on startup."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware: structured request logging
# ---------------------------------------------------------------------------
@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round(elapsed * 1000, 2),
            "client": request.client.host if request.client else None,
        },
    )
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "model_loaded": str(_State.model is not None)}


@app.get("/model-info", response_model=ModelInfo, tags=["meta"])
def model_info() -> ModelInfo:
    summary = _State.summary or {}
    best = summary.get("best_model")
    test_metrics: dict[str, float] | None = None
    if best and "results" in summary and best in summary["results"]:
        test_metrics = summary["results"][best].get("test_metrics")
    return ModelInfo(
        best_model=best,
        trained_at=summary.get("trained_at"),
        test_metrics=test_metrics,
        model_path=str(MODEL_PATH),
        model_loaded=_State.model is not None,
    )


@app.post("/predict", response_model=PredictionResponse, tags=["inference"])
def predict(features: PatientFeatures) -> PredictionResponse:
    if _State.model is None:
        REQUESTS.labels(status="unavailable").inc()
        raise HTTPException(
            status_code=503,
            detail=(
                "Model is not loaded. Train via `python -m heart_disease_mlops` "
                "or set HEART_DISEASE_MODEL_PATH to a valid joblib file."
            ),
        )

    start = time.perf_counter()
    try:
        row = pd.DataFrame(
            [features.model_dump()],
            columns=NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        )
        proba = float(_State.model.predict_proba(row)[0, 1])
        prediction = int(proba >= 0.5)
        label = "disease" if prediction == 1 else "no_disease"
    except Exception as exc:  # pragma: no cover - defensive
        REQUESTS.labels(status="error").inc()
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}") from exc

    LATENCY.observe(time.perf_counter() - start)
    REQUESTS.labels(status="ok").inc()
    PREDICTIONS.labels(label=label).inc()

    return PredictionResponse(prediction=prediction, label=label, probability=round(proba, 4))


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/feedback", response_model=FeedbackResponse, tags=["feedback"])
def feedback(payload: FeedbackPayload) -> FeedbackResponse:
    """Record a labelled feedback example so it is included in the next retrain."""
    try:
        path = append_feedback(
            features=payload.features.model_dump(),
            true_label=int(payload.true_label),
            path=FEEDBACK_PATH,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to persist feedback")
        raise HTTPException(status_code=500, detail="Could not save feedback") from exc

    total = len(load_feedback(path))
    FEEDBACK_ROWS.set(total)

    correct: bool | None = None
    if payload.predicted_label is not None:
        correct = int(payload.predicted_label) == int(payload.true_label)
        FEEDBACK.labels(correct=str(correct).lower()).inc()
    else:
        FEEDBACK.labels(correct="unknown").inc()

    return FeedbackResponse(
        saved=True,
        feedback_path=str(path),
        total_feedback_rows=total,
        correct=correct,
    )


@app.post("/retrain", response_model=RetrainResponse, tags=["feedback"])
def retrain(background: BackgroundTasks) -> RetrainResponse:
    """Kick off a background retraining run that includes feedback rows."""
    if _State.retrain_busy:
        raise HTTPException(
            status_code=409,
            detail="A retraining job is already in progress; try again later.",
        )

    job_id = next(_State.job_counter)
    background.add_task(_run_retrain, job_id)
    return RetrainResponse(
        job_id=job_id,
        status="scheduled",
        message="Retraining started in the background; the model will reload on completion.",
    )


# ---------------------------------------------------------------------------
# Static frontend (served at /ui)
# ---------------------------------------------------------------------------
_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.exists():
    app.mount(
        "/ui/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="ui-static",
    )

    @app.get("/ui", include_in_schema=False)
    def ui_index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/", include_in_schema=False)
    def root() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")
else:  # pragma: no cover - fallback when static assets missing
    logger.warning("Static UI directory %s not found; /ui will be unavailable.", _STATIC_DIR)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "internal_server_error"})
