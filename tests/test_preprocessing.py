"""Tests for the preprocessing ColumnTransformer."""

from __future__ import annotations

import numpy as np

from heart_disease_mlops.config import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from heart_disease_mlops.data import split_features_target
from heart_disease_mlops.preprocessing import build_preprocessor


def test_preprocessor_outputs_finite_floats(cleaned_df):
    X, _ = split_features_target(cleaned_df)
    pre = build_preprocessor()
    Xt = pre.fit_transform(X)
    assert isinstance(Xt, np.ndarray)
    assert Xt.dtype.kind in {"f", "i"}
    assert np.isfinite(Xt).all()


def test_preprocessor_numeric_block_is_standardized(cleaned_df):
    X, _ = split_features_target(cleaned_df)
    pre = build_preprocessor()
    Xt = pre.fit_transform(X)
    n_numeric = len(NUMERIC_FEATURES)
    numeric_block = Xt[:, :n_numeric]
    means = numeric_block.mean(axis=0)
    stds = numeric_block.std(axis=0)
    np.testing.assert_allclose(means, 0.0, atol=1e-7)
    np.testing.assert_allclose(stds, 1.0, atol=1e-2)


def test_preprocessor_expands_categoricals(cleaned_df):
    X, _ = split_features_target(cleaned_df)
    pre = build_preprocessor()
    Xt = pre.fit_transform(X)
    expected_cat_width = sum(X[c].nunique() for c in CATEGORICAL_FEATURES)
    assert Xt.shape[1] == len(NUMERIC_FEATURES) + expected_cat_width


def test_preprocessor_handles_unseen_categories(cleaned_df):
    """`handle_unknown='ignore'` should not raise on unseen one-hot codes."""
    X, _ = split_features_target(cleaned_df)
    pre = build_preprocessor()
    pre.fit(X)
    X_new = X.copy()
    X_new.loc[X_new.index[0], "cp"] = 99  # invalid value not seen during fit
    Xt = pre.transform(X_new)
    assert np.isfinite(Xt).all()
