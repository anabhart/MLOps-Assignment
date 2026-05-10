"""MLflow tracing setup for the FastAPI service.

Traces produced via ``@mlflow.trace`` (and any sklearn autologged spans)
are sent to the same file-backend ``mlruns/`` store under a dedicated
serving experiment so they are easy to filter from training runs.

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
        ensure_dirs()
        MLRUNS_DIR.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(MLRUNS_DIR.resolve().as_uri())
        mlflow.set_experiment(SERVING_EXPERIMENT)
        _initialised = True
        logger.info(
            "MLflow tracing initialised (uri=%s experiment=%s)",
            MLRUNS_DIR.resolve().as_uri(),
            SERVING_EXPERIMENT,
        )
        return True
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to initialise MLflow tracing")
        return False
