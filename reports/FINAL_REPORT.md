# Heart Disease MLOps — Final Report

**Course**: MLOps (S2-25_AMLCSZG523)
**Assignment**: I — End-to-End ML Model Development, CI/CD, and Production Deployment
**Date**: May 2026

---

## 1. Problem statement

Cardiovascular disease remains the leading cause of mortality worldwide.
The objective of this assignment is to build a reproducible binary
classifier that predicts the presence of heart disease from 13 standard
clinical measurements of the **UCI Cleveland Heart Disease** dataset, and
to deliver it as a cloud-ready, monitored REST API following modern MLOps
practices.

Per the dataset README, only the **Cleveland** subset (303 records) is used
for modelling — it is the only subset with complete attribute coverage and
the only one used in published literature.

## 2. Setup & install

```powershell
# Windows PowerShell
git clone <repo-url>
cd MLOPS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e ".[dev,api]"
```

Run the full pipeline:

```powershell
python -m heart_disease_mlops          # train + log + persist best model
mlflow ui --backend-store-uri mlruns   # inspect runs
uvicorn api.app:app --reload           # serve the model on :8000
```

Or, end-to-end via Prefect:

```powershell
python pipelines/prefect_flow.py
```

## 3. Data & EDA

| Item | Value |
|------|-------|
| Records (raw) | 303 |
| Records (cleaned) | 297 |
| Features | 5 numeric + 8 categorical |
| Target | Binary (`num >= 1` ⇒ disease) |
| Class balance | ~54% no-disease / 46% disease |
| Missing values | 6 rows (in `ca`, `thal`) → dropped |

EDA highlights (`notebooks/01_eda.ipynb`):
* Strongest correlates with disease: `cp`, `ca`, `thal`, `oldpeak`,
  `exang`, and `thalach` (negative).
* Numeric features have very different scales → standard scaling required.
* Categorical codes are non-ordinal → one-hot encoding preferred.

## 4. Feature Engineering & Model Development

### 4.1 Feature Engineering Pipeline

**Location**: `src/heart_disease_mlops/preprocessing.py`

| Feature Type | Imputation | Transformation | Output |
|--------------|-----------|-----------------|--------|
| **Numeric** (5 features: age, trestbps, chol, thalach, oldpeak) | Median | StandardScaler | Normalized float |
| **Categorical** (8 features: sex, cp, fbs, restecg, exang, slope, ca, thal) | Most-frequent | OneHotEncoder | Binary indicators |

The preprocessing pipeline is implemented as a `ColumnTransformer` that ensures:
- **No data leakage**: All statistics (median, mode) computed on training data only
- **Unseen categories at inference**: `handle_unknown='ignore'` gracefully handles novel categorical values
- **Pipeline integration**: Full preprocessing + classifier pipeline for proper cross-validation

### 4.2 Model Candidates & Hyperparameter Tuning

**Location**: `src/heart_disease_mlops/train.py` (lines 40–100)

#### Model 1: Logistic Regression
```python
Param grid: C ∈ [0.1, 1.0, 10.0] × penalty ∈ ['l1', 'l2']
Total combinations: 6
Best params: C=10.0, penalty='l1'
CV ROC-AUC: 0.9246
```

#### Model 2: Random Forest (SELECTED)
```python
Param grid: 
  - n_estimators ∈ [200, 400]
  - max_depth ∈ [None, 5, 10]
  - min_samples_split ∈ [2, 5]
Total combinations: 12
Best params: n_estimators=200, max_depth=5, min_samples_split=2
CV ROC-AUC: 0.9075 → Test ROC-AUC: 0.9116 ✓ BEST
```

### 4.3 Cross-Validation Strategy

**Configuration** (`train.py` lines 106–116):
- **Strategy**: Stratified K-fold (preserves class distribution)
- **Splits**: 5 folds
- **Scoring**: ROC-AUC (robust to class imbalance: 46% disease, 54% healthy)
- **Reproducibility**: `random_state=42`, shuffle=True
- **Parallelization**: `n_jobs=-1` for multiprocessing

### 4.4 Model Evaluation Results

**Test Set Performance** (61 samples, 244 train / 8 feedback split):

**Logistic Regression**:
```
Accuracy:  78.69%    Precision: 83.33%    Recall: 68.97%
F1-Score:  75.47%    ROC-AUC:   86.53%
```

**Random Forest (SELECTED)**:
```
Accuracy:  78.69%    Precision: 80.77%    Recall: 72.41%
F1-Score:  76.36%    ROC-AUC:   91.16% ← BEST MODEL
```

**Classification Report (Random Forest - test set)**:
```
Class 0 (No disease):   Precision 77%, Recall 84%, F1 81%
Class 1 (Disease):      Precision 81%, Recall 72%, F1 76%
```

### 4.5 Model Selection Criteria

- **Primary metric**: ROC-AUC (robust to class imbalance)
- **Rationale**: Logistic Regression (86.53%) vs Random Forest (91.16%)
- **Decision**: Random Forest selected (≈4.6% improvement in ROC-AUC)
- **Trade-off**: Slight recall improvement for disease class (72.41% vs 68.97%)

### 4.6 Training Artifacts

Full training workflow documented in `notebooks/02_training_and_analysis.ipynb`:
1. Load + preprocess data (ColumnTransformer integration)
2. Stratified train/test split (80/20)
3. Cross-validation baseline scores
4. GridSearchCV hyperparameter optimization
5. Best model evaluation on held-out test set
6. ROC curves, confusion matrices, feature importance plots
7. MLflow logging and model registry promotion

**Persisted Artifacts** (`artifacts/reports/`):
- `training_summary.json` — all metrics, best params, timestamps
- `logistic_regression_classification_report.txt`
- `random_forest_classification_report.txt`
- `best_model.joblib` — saved Random Forest pipeline (preprocessing + classifier)

## 5. Experiment tracking

MLflow is integrated directly in the training and serving stack and satisfies
the experiment-tracking requirement (parameters, metrics, artifacts, plots).

### 5.1 Tracking setup and experiments

Training resolves tracking with `MLFLOW_SERVER_URI` / `MLFLOW_TRACKING_URI`
and falls back to local file tracking under `mlruns/` when unset.

Experiments are separated by workload:
- `heart-disease-cleveland`: baseline training runs
- `heart-disease-feedback-retrain`: feedback-driven retraining runs
- `heart-disease-serving`: API trace spans
- `heart-disease-prefect`: orchestration-triggered runs

### 5.2 What is logged for each training run

For every model run (Logistic Regression and Random Forest), the pipeline logs:

- **Parameters**
  - Best hyperparameters from GridSearchCV
  - Model family
  - CV scoring strategy and number of folds
  - Training and feedback row counts

- **Metrics**
  - `cv_best_score` (ROC-AUC)
  - Test metrics: accuracy, precision, recall, F1, ROC-AUC

- **Artifacts**
  - Classification report text file
  - Confusion matrix plot (`*_confusion_matrix.png`)
  - ROC curve plot (`*_roc_curve.png`)
  - Serialized MLflow model artifact (`mlflow.sklearn.log_model`)

The best model is persisted locally as `artifacts/models/best_model.joblib`
and registered in MLflow Model Registry as `heart-disease-classifier`.

### 5.3 Trace logging

Beyond run-level logging, API predict/retrain paths emit MLflow traces/spans,
so both model-quality history and serving-time behavior are observable in the
same tracking system.

## 6. Architecture

See [`reports/ARCHITECTURE.md`](ARCHITECTURE.md) for diagrams.

* **Pipeline package** (`src/heart_disease_mlops/`) is the single source of
  truth — imported by tests, the API, and the Prefect flow.
* **Serving** is FastAPI + uvicorn, packaged in an OCI image built with
  podman, deployed to Kubernetes via the manifests in `deploy/k8s/`.
* **Orchestration** uses Prefect 2 with retries and a weekly cron schedule.
* **Monitoring** combines structured JSON logs, a Prometheus
  `/metrics` endpoint, and Evidently drift reports.

## 7. CI/CD

The single GitHub Actions workflow at `.github/workflows/ci.yml` runs four
sequential jobs on every push / PR:

1. **lint** — `ruff check src tests api`
2. **test** — `pytest --cov=heart_disease_mlops`
3. **train-smoke** — `python -m heart_disease_mlops` with reduced grids
   (`HEART_DISEASE_FAST_TRAIN=1`); uploads artifacts.
4. **container** — builds the image from `Containerfile` and exercises
   `/health` + `/predict` from inside the workflow.

The pipeline fails on any lint, test, training, or container error and
surfaces clear logs.

## 8. Containerization & deployment

```powershell
# Build with podman
podman build -t heart-disease-api:latest -f Containerfile .

# Run locally
podman run --rm -p 8000:8000 heart-disease-api:latest

# Smoke test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict `
     -H "Content-Type: application/json" `
     -d (Get-Content api/example_requests.json -Raw)
```

Kubernetes deployment instructions: see [`deploy/k8s/README.md`](../deploy/k8s/README.md).

## 9. Monitoring & drift

* **Logs**: `api/logging_config.py` configures JSON logs on stdout. Each
  request emits `method`, `path`, `status`, `latency_ms`, `client`.
* **Metrics**: `prometheus_client` exposes `/metrics`:
  * `predict_requests_total{status}`
  * `predict_latency_seconds` (histogram)
  * `predict_predictions_total{label}`
* **Drift**: `python monitoring/drift_detection.py` writes
  `artifacts/reports/drift_report.html` + `.json` and exits non-zero when
  the share of drifted features exceeds the configurable threshold.
* **Retraining runbook**: [`monitoring/RETRAINING_RUNBOOK.md`](../monitoring/RETRAINING_RUNBOOK.md).

## 10. Results summary

| Model | CV ROC-AUC | Test ROC-AUC | Test F1 |
|-------|------------|--------------|---------|
| Logistic Regression | ~0.90 | ~0.91 | ~0.85 |
| Random Forest | ~0.89 | ~0.90 | ~0.84 |

(Exact values are written to `artifacts/reports/training_summary.json`
after each training run.)

## 11. Lessons learned & future work

* **Cleveland-only** is small (~297 rows) — pooling other UCI subsets
  would require schema reconciliation but could meaningfully improve
  generalization.
* **Calibration** is not yet performed; for clinical use, isotonic /
  Platt calibration on the probability output would be a next step.
* **Online learning** is out of scope; the current retraining strategy is
  scheduled + drift-triggered.
* **Helm chart** packaging would simplify multi-environment promotion.

## 12. Repository

* Code, manifests, notebooks, and reports: this repository.
* CI status: GitHub Actions tab.
* Container image: built locally via podman; published to GHCR in CI when
  enabled.
