"""Lightweight schema + range validation for the Cleveland dataset.

Returns a structured report instead of raising on the first failure so the
caller (Prefect flow, CI step, API startup) can decide what to do.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from .config import (
    CATEGORICAL_FEATURES,
    COLUMNS,
    NUMERIC_FEATURES,
    RAW_TARGET,
    TARGET,
)

# Allowed value ranges per UCI documentation (and clinical sanity).
NUMERIC_RANGES: dict[str, tuple[float, float]] = {
    "age": (1, 120),
    "trestbps": (50, 260),
    "chol": (50, 700),
    "thalach": (40, 260),
    "oldpeak": (-2.0, 10.0),
}

CATEGORICAL_VALUES: dict[str, set[int]] = {
    "sex": {0, 1},
    "cp": {1, 2, 3, 4},
    "fbs": {0, 1},
    "restecg": {0, 1, 2},
    "exang": {0, 1},
    "slope": {1, 2, 3},
    "ca": {0, 1, 2, 3},
    "thal": {3, 6, 7},
}


@dataclass
class ValidationReport:
    """Structured validation outcome."""

    passed: bool
    n_rows: int
    n_missing_total: int
    missing_per_column: dict[str, int] = field(default_factory=dict)
    out_of_range: dict[str, int] = field(default_factory=dict)
    invalid_categories: dict[str, list] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def validate_raw(df: pd.DataFrame) -> ValidationReport:
    """Validate the raw dataframe (after `load_raw_cleveland`)."""
    errors: list[str] = []

    expected = set(COLUMNS)
    actual = set(df.columns)
    if expected != actual:
        errors.append(f"Schema mismatch. Missing: {expected - actual}, extra: {actual - expected}")

    missing_per_column = df.isna().sum().astype(int).to_dict()
    n_missing_total = int(sum(missing_per_column.values()))

    return ValidationReport(
        passed=len(errors) == 0,
        n_rows=len(df),
        n_missing_total=n_missing_total,
        missing_per_column={k: v for k, v in missing_per_column.items() if v},
        errors=errors,
    )


def validate_clean(df: pd.DataFrame) -> ValidationReport:
    """Validate the cleaned dataframe (after `clean_cleveland`)."""
    errors: list[str] = []

    if df.isna().any().any():
        errors.append("Cleaned dataframe still contains NaNs")
    if TARGET not in df.columns:
        errors.append(f"Missing target column '{TARGET}'")
    if RAW_TARGET in df.columns:
        errors.append(f"Raw target column '{RAW_TARGET}' should be dropped")

    target_vals = set(df[TARGET].unique()) if TARGET in df.columns else set()
    if not target_vals.issubset({0, 1}):
        errors.append(f"Target must be binary {{0,1}}, got {sorted(target_vals)}")

    out_of_range: dict[str, int] = {}
    for col, (lo, hi) in NUMERIC_RANGES.items():
        if col in df.columns:
            mask = (df[col] < lo) | (df[col] > hi)
            n = int(mask.sum())
            if n:
                out_of_range[col] = n

    invalid_categories: dict[str, list] = {}
    for col, allowed in CATEGORICAL_VALUES.items():
        if col in df.columns:
            bad = sorted(set(df[col].unique()) - allowed)
            if bad:
                invalid_categories[col] = bad

    if out_of_range:
        errors.append(f"Out-of-range numeric values: {out_of_range}")
    if invalid_categories:
        errors.append(f"Invalid categorical codes: {invalid_categories}")

    missing_per_column = df.isna().sum().astype(int).to_dict()

    return ValidationReport(
        passed=len(errors) == 0,
        n_rows=len(df),
        n_missing_total=int(sum(missing_per_column.values())),
        missing_per_column={k: v for k, v in missing_per_column.items() if v},
        out_of_range=out_of_range,
        invalid_categories=invalid_categories,
        errors=errors,
    )


__all__ = [
    "CATEGORICAL_FEATURES",
    "CATEGORICAL_VALUES",
    "NUMERIC_FEATURES",
    "NUMERIC_RANGES",
    "ValidationReport",
    "validate_clean",
    "validate_raw",
]
