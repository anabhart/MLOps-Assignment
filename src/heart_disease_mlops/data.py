"""Data loading and cleaning for the UCI Cleveland Heart Disease dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import (
    CATEGORICAL_FEATURES,
    CLEAN_CLEVELAND_PATH,
    COLUMNS,
    FEEDBACK_PATH,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    RAW_CLEVELAND_PATH,
    RAW_TARGET,
    TARGET,
    TEST_SIZE,
    ensure_dirs,
)


def load_raw_cleveland(path: Path | str = RAW_CLEVELAND_PATH) -> pd.DataFrame:
    """Load the raw Cleveland file. Missing values are encoded as ``?``."""
    df = pd.read_csv(path, header=None, names=COLUMNS, na_values="?")
    return df


def clean_cleveland(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw Cleveland dataframe.

    Steps:
        * Drop rows with missing values (only ~6 rows in the Cleveland subset).
        * Cast categorical columns to integer codes.
        * Derive binary ``target`` from ``num`` (0 = no disease, >=1 = disease).
    """
    df = df.copy()
    df = df.dropna().reset_index(drop=True)

    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype(int)

    for col in NUMERIC_FEATURES:
        df[col] = df[col].astype(float)

    df[TARGET] = (df[RAW_TARGET] >= 1).astype(int)
    df = df.drop(columns=[RAW_TARGET])
    return df


def load_clean_cleveland(
    raw_path: Path | str = RAW_CLEVELAND_PATH,
    cache_path: Path | str | None = CLEAN_CLEVELAND_PATH,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Return the cleaned Cleveland dataframe, caching to CSV when requested."""
    cache_path = Path(cache_path) if cache_path else None
    if use_cache and cache_path and cache_path.exists():
        return pd.read_csv(cache_path)

    df = clean_cleveland(load_raw_cleveland(raw_path))
    if cache_path is not None:
        ensure_dirs()
        df.to_csv(cache_path, index=False)
    return df


def split_features_target(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Split a cleaned dataframe into ``X`` and ``y``."""
    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    return df[feature_cols].copy(), df[TARGET].astype(int).copy()


# ---------------------------------------------------------------------------
# Feedback loop
# ---------------------------------------------------------------------------
FEEDBACK_COLUMNS: list[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET, "submitted_at"]


def append_feedback(features: dict, true_label: int, path: Path | str = FEEDBACK_PATH) -> Path:
    """Append a single feedback row (features + true label) to the feedback CSV."""
    from datetime import UTC, datetime

    if true_label not in (0, 1):
        raise ValueError(f"true_label must be 0 or 1, got {true_label!r}")

    path = Path(path)
    ensure_dirs()

    row = {col: features[col] for col in NUMERIC_FEATURES + CATEGORICAL_FEATURES}
    row[TARGET] = int(true_label)
    row["submitted_at"] = datetime.now(UTC).isoformat()

    df_row = pd.DataFrame([row], columns=FEEDBACK_COLUMNS)
    write_header = not path.exists()
    df_row.to_csv(path, mode="a", header=write_header, index=False)
    return path


def load_feedback(path: Path | str = FEEDBACK_PATH) -> pd.DataFrame:
    """Load the feedback CSV (or an empty frame if it does not exist yet)."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=FEEDBACK_COLUMNS)
    return pd.read_csv(path)


def load_training_dataset(
    include_feedback: bool = True,
    feedback_path: Path | str = FEEDBACK_PATH,
) -> pd.DataFrame:
    """Return the training dataset, optionally augmented with feedback rows."""
    base = load_clean_cleveland()
    if not include_feedback:
        return base

    feedback = load_feedback(feedback_path)
    if feedback.empty:
        return base

    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET]
    feedback = feedback[feature_cols].copy()
    feedback[TARGET] = feedback[TARGET].astype(int)
    return pd.concat([base, feedback], ignore_index=True)


def train_test_split_df(
    df: pd.DataFrame,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Stratified train/test split returning ``(X_train, X_test, y_train, y_test)``."""
    X, y = split_features_target(df)
    return train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
