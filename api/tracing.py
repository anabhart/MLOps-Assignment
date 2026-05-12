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


def _local_tracking_uri() -> str:
    ensure_dirs()
    offline_dir = MLRUNS_DIR / "offline"
    offline_dir.mkdir(parents=True, exist_ok=True)
    return offline_dir.resolve().as_uri()


def _resolve_tracking_uri() -> str:
    """Pick the MLflow tracking URI based on env vars, with file-store fallback."""
    for var in ("MLFLOW_SERVER_URI", "MLFLOW_TRACKING_URI"):
        val = os.environ.get(var)
        if val:
            return val
    return _local_tracking_uri()


def _set_tracking_uri(uri: str) -> None:
    os.environ["MLFLOW_TRACKING_URI"] = uri
    os.environ["MLFLOW_SERVER_URI"] = uri
    mlflow.set_tracking_uri(uri)


def _configure_tracking(experiment_name: str) -> str:
    """Configure MLflow, falling back to the local file store if needed."""
    preferred_uri = _resolve_tracking_uri()
    _set_tracking_uri(preferred_uri)
    try:
        mlflow.set_experiment(experiment_name)
        return preferred_uri
    except Exception:
        fallback_uri = _local_tracking_uri()
        if preferred_uri == fallback_uri:
            raise
        logger.warning(
            "MLflow backend %s unreachable for experiment %s; falling back to %s",
            preferred_uri,
            experiment_name,
            fallback_uri,
        )
        _set_tracking_uri(fallback_uri)
        mlflow.set_experiment(experiment_name)
        return fallback_uri


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
        uri = _configure_tracking(SERVING_EXPERIMENT)
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
