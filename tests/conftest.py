"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def cleaned_df():
    from heart_disease_mlops.data import clean_cleveland, load_raw_cleveland

    return clean_cleveland(load_raw_cleveland())
