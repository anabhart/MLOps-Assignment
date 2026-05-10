"""Prefect orchestration for the heart-disease pipeline.

Run locally:
    python pipelines/prefect_flow.py            # one-off run
    prefect server start                        # in another terminal for the UI

Schedule (registered as a deployment):
    python -c "from pipelines.prefect_flow import deploy; deploy()"
"""

from __future__ import annotations

import json
from typing import Any

from prefect import flow, get_run_logger, task
from prefect.tasks import exponential_backoff

from heart_disease_mlops.config import REPORTS_DIR, ensure_dirs
from heart_disease_mlops.data import clean_cleveland, load_raw_cleveland
from heart_disease_mlops.train import train_and_log_all
from heart_disease_mlops.validation import validate_clean, validate_raw


@task(retries=2, retry_delay_seconds=exponential_backoff(backoff_factor=2))
def ingest_task():
    logger = get_run_logger()
    df = load_raw_cleveland()
    logger.info("Ingested raw rows: %d", len(df))
    return df


@task
def validate_raw_task(df):
    report = validate_raw(df)
    logger = get_run_logger()
    logger.info("Raw validation: %s", report.to_dict())
    if not report.passed:
        raise ValueError(f"Raw validation failed: {report.errors}")
    return df


@task
def clean_task(df):
    cleaned = clean_cleveland(df)
    return cleaned


@task
def validate_clean_task(df):
    report = validate_clean(df)
    logger = get_run_logger()
    logger.info("Clean validation: %s", report.to_dict())
    if not report.passed:
        raise ValueError(f"Clean validation failed: {report.errors}")
    return df


@task(retries=1, retry_delay_seconds=10)
def train_task() -> dict[str, Any]:
    summary = train_and_log_all(experiment_name="heart-disease-prefect")
    logger = get_run_logger()
    logger.info("Training summary: %s", json.dumps(summary, indent=2, default=str))
    return summary


@task
def persist_summary_task(summary: dict[str, Any]) -> str:
    ensure_dirs()
    path = REPORTS_DIR / "prefect_run_summary.json"
    path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return str(path)


@flow(name="heart-disease-pipeline", log_prints=True)
def heart_disease_pipeline() -> dict[str, Any]:
    """Ingest → validate → clean → validate → train → register."""
    raw = ingest_task()
    raw_validated = validate_raw_task(raw)
    cleaned = clean_task(raw_validated)
    validate_clean_task(cleaned)
    summary = train_task()
    persist_summary_task(summary)
    return summary


def deploy() -> None:
    """Register a weekly deployment with the local Prefect server.

    Requires Prefect 2.x and a running `prefect server start`.
    """
    from prefect.client.schemas.schedules import CronSchedule

    heart_disease_pipeline.serve(  # type: ignore[attr-defined]
        name="weekly-retrain",
        schedule=CronSchedule(cron="0 3 * * 0", timezone="UTC"),
        tags=["heart-disease", "scheduled"],
    )


if __name__ == "__main__":
    heart_disease_pipeline()
