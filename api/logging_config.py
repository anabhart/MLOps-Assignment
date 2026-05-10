"""JSON-formatted logging for the API."""

from __future__ import annotations

import logging
import sys

try:
    from pythonjsonlogger import jsonlogger
except ImportError:  # pragma: no cover - fallback if extras not installed
    jsonlogger = None  # type: ignore[assignment]


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging to emit JSON lines on stdout (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any pre-existing handlers (uvicorn installs its own).
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if jsonlogger is not None:
        fmt = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "ts", "levelname": "level"},
        )
    else:  # plain text fallback
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    handler.setFormatter(fmt)
    root.addHandler(handler)

    # Quiet down noisy uvicorn access duplicates (we have our own middleware).
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
