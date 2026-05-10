"""Tests for data loading, cleaning, validation, and splitting."""

from __future__ import annotations

import pandas as pd

from heart_disease_mlops.config import CATEGORICAL_FEATURES, COLUMNS, NUMERIC_FEATURES, TARGET
from heart_disease_mlops.data import (
    clean_cleveland,
    load_raw_cleveland,
    split_features_target,
    train_test_split_df,
)
from heart_disease_mlops.validation import validate_clean, validate_raw


def test_load_raw_cleveland_shape_and_schema():
    df = load_raw_cleveland()
    assert df.shape == (303, 14)
    assert list(df.columns) == COLUMNS


def test_load_raw_cleveland_has_missing_values():
    df = load_raw_cleveland()
    # Missing values are encoded as '?' which we turn into NaN; only `ca` and
    # `thal` are missing in the Cleveland subset.
    assert df.isna().any().any()
    missing_cols = df.columns[df.isna().any()].tolist()
    assert set(missing_cols).issubset({"ca", "thal"})


def test_clean_cleveland_drops_na_and_binarizes_target(cleaned_df: pd.DataFrame):
    assert not cleaned_df.isna().any().any()
    assert TARGET in cleaned_df.columns
    assert set(cleaned_df[TARGET].unique()) == {0, 1}
    assert "num" not in cleaned_df.columns


def test_clean_cleveland_row_count():
    raw = load_raw_cleveland()
    cleaned = clean_cleveland(raw)
    # 303 raw rows minus the 6 NA rows in `ca`/`thal`.
    assert len(cleaned) == 297


def test_train_test_split_is_stratified_and_reproducible(cleaned_df: pd.DataFrame):
    X1, X1_t, y1, y1_t = train_test_split_df(cleaned_df)
    X2, X2_t, y2, y2_t = train_test_split_df(cleaned_df)
    pd.testing.assert_frame_equal(X1, X2)
    pd.testing.assert_series_equal(y1, y2)

    # Stratification: train and test class ratios should be close.
    train_ratio = y1.mean()
    test_ratio = y1_t.mean()
    assert abs(train_ratio - test_ratio) < 0.05


def test_split_features_target_columns(cleaned_df: pd.DataFrame):
    X, y = split_features_target(cleaned_df)
    assert list(X.columns) == NUMERIC_FEATURES + CATEGORICAL_FEATURES
    assert y.name == TARGET


def test_validate_raw_reports_missing(cleaned_df: pd.DataFrame):
    raw = load_raw_cleveland()
    report = validate_raw(raw)
    assert report.passed is True  # schema OK
    assert report.n_missing_total > 0


def test_validate_clean_passes_on_cleaned(cleaned_df: pd.DataFrame):
    report = validate_clean(cleaned_df)
    assert report.passed, report.errors
    assert report.n_missing_total == 0
