"""Evaluation utilities: metrics, plots, and report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def compute_metrics(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
    y_proba: np.ndarray | None = None,
) -> dict[str, float]:
    """Return a dict of standard binary classification metrics."""
    metrics: dict[str, float] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    if y_proba is not None:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba))
    return metrics


def plot_confusion_matrix(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
    title: str = "Confusion matrix",
    save_path: Path | str | None = None,
) -> plt.Figure:
    """Plot a confusion matrix and optionally persist it to ``save_path``."""
    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay(cm, display_labels=["No disease", "Disease"]).plot(
        ax=ax, cmap="Blues", colorbar=False
    )
    ax.set_title(title)
    fig.tight_layout()
    if save_path is not None:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150)
    return fig


def plot_roc_curve(
    y_true: np.ndarray | pd.Series,
    y_proba: np.ndarray,
    title: str = "ROC curve",
    save_path: Path | str | None = None,
) -> plt.Figure:
    """Plot a single ROC curve."""
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    auc = roc_auc_score(y_true, y_proba)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(fpr, tpr, label=f"AUC = {auc:.3f}")
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", linewidth=1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(title)
    ax.legend(loc="lower right")
    fig.tight_layout()
    if save_path is not None:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150)
    return fig


def evaluation_report(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    """Run the model on the test set and return metrics + text report."""
    y_pred = model.predict(X_test)
    y_proba = (
        model.predict_proba(X_test)[:, 1]
        if hasattr(model, "predict_proba")
        else None
    )
    metrics = compute_metrics(y_test, y_pred, y_proba)
    report = classification_report(
        y_test, y_pred, target_names=["No disease", "Disease"], zero_division=0
    )
    return {
        "metrics": metrics,
        "classification_report": report,
        "y_pred": y_pred,
        "y_proba": y_proba,
    }
