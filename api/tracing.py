"""MLflow tracing setup for the FastAPI service.

Traces produced via ``@mlflow.trace`` (and any sklearn autologged spans)
are sent to the configured MLflow tracking server under a dedicated
serving experiment so they are easy to filter from training runs.

Tracking URI resolution (in priority order):
  1. ``MLFLOW_SERVER_URI`` (project-specific; what the Makefile uses)
  2. ``MLFLOW_TRACKING_URI`` (standard MLflow env var)
  3. local ``mlruns/`` file-backend (default for `python -m heart_disease_mlops`)

Disable with the env var ``HEART_DISEASE_DISABLE_TRACING=1``.
"""

from __future__ import annotations

import logging
import os

import mlflow

from heart_disease_mlops.config import MLRUNS_DIR, ensure_dirs

logger = logging.getLogger(__name__)

SERVING_EXPERIMENT = os.environ.get(
    "HEART_DISEASE_SERVING_EXPERIMENT", "heart-disease-serving"
)

_initialised = False


def _resolve_tracking_uri() -> str:
    """Pick the MLflow tracking URI based on env vars, with file-store fallback."""
    for var in ("MLFLOW_SERVER_URI", "MLFLOW_TRACKING_URI"):
        val = os.environ.get(var)
        if val:
            return val
    ensure_dirs()
    MLRUNS_DIR.mkdir(parents=True, exist_ok=True)
    return MLRUNS_DIR.resolve().as_uri()


def setup_tracing() -> bool:
    """Configure MLflow tracking + a serving experiment for traces.

    Returns ``True`` when tracing is active, ``False`` when disabled or
    when the backend could not be reached.
    """
    global _initialised
    if _initialised:
        return True
    if os.environ.get("HEART_DISEASE_DISABLE_TRACING") == "1":
        logger.info("MLflow tracing disabled via env var")
        return False

    try:
        uri = _resolve_tracking_uri()
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(SERVING_EXPERIMENT)
        _initialised = True
        logger.info(
            "MLflow tracing initialised (uri=%s experiment=%s)",
            uri,
            SERVING_EXPERIMENT,
        )
        return True
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to initialise MLflow tracing")
        return False
