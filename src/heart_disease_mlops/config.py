"""Project configuration: paths, schema, and feature groups.

Only the Cleveland subset of the UCI Heart Disease dataset is used, in line
with the dataset README (`data/heart+disease/heart-disease.names`).
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "heart+disease"
PROCESSED_DIR: Path = DATA_DIR / "processed"
FEEDBACK_DIR: Path = DATA_DIR / "feedback"
ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts"
MODELS_DIR: Path = ARTIFACTS_DIR / "models"
REPORTS_DIR: Path = ARTIFACTS_DIR / "reports"
FIGURES_DIR: Path = ARTIFACTS_DIR / "figures"
MLRUNS_DIR: Path = PROJECT_ROOT / "mlruns"

RAW_CLEVELAND_PATH: Path = RAW_DIR / "processed.cleveland.data"
CLEAN_CLEVELAND_PATH: Path = PROCESSED_DIR / "cleveland_clean.csv"
FEEDBACK_PATH: Path = FEEDBACK_DIR / "feedback.csv"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
# Column order in the UCI processed.*.data files (14 columns).
COLUMNS: list[str] = [
    "age",
    "sex",
    "cp",
    "trestbps",
    "chol",
    "fbs",
    "restecg",
    "thalach",
    "exang",
    "oldpeak",
    "slope",
    "ca",
    "thal",
    "num",
]

TARGET: str = "target"  # binary target derived from `num`
RAW_TARGET: str = "num"

# Treat features by their semantic type (per UCI documentation), not by their
# raw dtype. Several columns are encoded as floats but represent categories.
NUMERIC_FEATURES: list[str] = [
    "age",
    "trestbps",
    "chol",
    "thalach",
    "oldpeak",
]

CATEGORICAL_FEATURES: list[str] = [
    "sex",
    "cp",
    "fbs",
    "restecg",
    "exang",
    "slope",
    "ca",
    "thal",
]

ALL_FEATURES: list[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Human-readable descriptions used in EDA / reports.
FEATURE_DESCRIPTIONS: dict[str, str] = {
    "age": "Age in years",
    "sex": "Sex (1 = male, 0 = female)",
    "cp": "Chest pain type (1=typical, 2=atypical, 3=non-anginal, 4=asymptomatic)",
    "trestbps": "Resting blood pressure (mm Hg)",
    "chol": "Serum cholesterol (mg/dl)",
    "fbs": "Fasting blood sugar > 120 mg/dl (1=true, 0=false)",
    "restecg": "Resting ECG (0=normal, 1=ST-T abnormality, 2=LV hypertrophy)",
    "thalach": "Maximum heart rate achieved",
    "exang": "Exercise induced angina (1=yes, 0=no)",
    "oldpeak": "ST depression induced by exercise relative to rest",
    "slope": "Slope of peak exercise ST segment (1=up, 2=flat, 3=down)",
    "ca": "Number of major vessels (0-3) colored by fluoroscopy",
    "thal": "Thalassemia (3=normal, 6=fixed defect, 7=reversible defect)",
    "num": "Diagnosis of heart disease (0 = none, 1-4 = increasing severity)",
}

# ---------------------------------------------------------------------------
# Training defaults
# ---------------------------------------------------------------------------
RANDOM_STATE: int = 42
TEST_SIZE: float = 0.20
CV_FOLDS: int = 5


def ensure_dirs() -> None:
    """Create all output directories used by the pipeline."""
    for d in (
        PROCESSED_DIR,
        FEEDBACK_DIR,
        ARTIFACTS_DIR,
        MODELS_DIR,
        REPORTS_DIR,
        FIGURES_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
