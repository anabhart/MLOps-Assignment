"""Data drift detection using Evidently.

Compares a *reference* dataset (the cleaned Cleveland CSV used at training
time) against a *current* sample (e.g. a recent batch of API requests).

Usage:
    python monitoring/drift_detection.py                # uses synthetic drift sample
    python monitoring/drift_detection.py --current path/to/recent.csv

Outputs:
    artifacts/reports/drift_report.html
    artifacts/reports/drift_report.json
    Exit code 1 if any feature exceeds the drift threshold.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from heart_disease_mlops.config import REPORTS_DIR, ensure_dirs
from heart_disease_mlops.data import load_clean_cleveland


def _load_reference() -> pd.DataFrame:
    return load_clean_cleveland()


def _synthesize_drifted_sample(reference: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Return a perturbed copy of the reference to demonstrate drift."""
    rng = np.random.default_rng(seed)
    sample = reference.sample(frac=0.5, random_state=seed).copy()
    sample["chol"] = sample["chol"] * rng.normal(1.15, 0.05, size=len(sample))
    sample["thalach"] = sample["thalach"] * rng.normal(0.92, 0.05, size=len(sample))
    sample["age"] = (sample["age"] + rng.integers(0, 8, size=len(sample))).clip(upper=110)
    return sample


def _run_evidently(reference: pd.DataFrame, current: pd.DataFrame, html_path: Path, json_path: Path):
    """Run Evidently drift report and persist HTML + JSON. Returns drift summary."""
    try:
        from evidently.metric_preset import DataDriftPreset
        from evidently.report import Report
    except ImportError as exc:  # pragma: no cover - extras not installed
        raise SystemExit(
            "Evidently is not installed. Run `pip install -e .[monitoring]`."
        ) from exc

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference, current_data=current)
    report.save_html(str(html_path))
    payload = report.as_dict()
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    summary = payload["metrics"][0]["result"]
    return {
        "n_features": int(summary.get("number_of_columns", 0)),
        "n_drifted": int(summary.get("number_of_drifted_columns", 0)),
        "share_drifted": float(summary.get("share_of_drifted_columns", 0.0)),
        "dataset_drift": bool(summary.get("dataset_drift", False)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--current",
        type=Path,
        default=None,
        help="Path to a CSV with the same schema as the cleaned reference dataset.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.30,
        help="Fail if share of drifted features exceeds this threshold.",
    )
    args = parser.parse_args(argv)

    ensure_dirs()
    reference = _load_reference()
    if args.current:
        current = pd.read_csv(args.current)
    else:
        current = _synthesize_drifted_sample(reference)

    html_path = REPORTS_DIR / "drift_report.html"
    json_path = REPORTS_DIR / "drift_report.json"
    summary = _run_evidently(reference, current, html_path, json_path)

    print(json.dumps(summary, indent=2))
    print(f"HTML report: {html_path}")
    print(f"JSON report: {json_path}")

    if summary["share_drifted"] > args.threshold:
        print(f"Drift threshold ({args.threshold}) exceeded.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
