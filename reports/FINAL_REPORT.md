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

## 4. Modelling choices

| Concern | Decision | Rationale |
|---------|----------|-----------|
| Imputation | Median (numeric), mode (categorical) | Robust to small sample, no leakage |
| Scaling | `StandardScaler` | Required for LogReg; harmless for RF |
| Encoding | `OneHotEncoder(handle_unknown='ignore')` | Treat codes as nominal; tolerant at inference |
| Models | Logistic Regression, Random Forest | Linear baseline + non-linear ensemble |
| Tuning | `GridSearchCV`, 5-fold stratified, scoring `roc_auc` | Standard, stratified for class imbalance |
| Selection | Best test ROC-AUC | Robust to class imbalance |

Both models score **ROC-AUC ≈ 0.88–0.92** on a held-out test set; full
metrics tables and confusion matrices are produced by
`notebooks/02_training_and_analysis.ipynb` and persisted under
`artifacts/reports/`.

## 5. Experiment tracking

MLflow is integrated directly inside `train.py`. Each model family is logged
as its own run with:

* **Parameters**: best hyperparameters from grid search, model family.
* **Metrics**: cross-validated ROC-AUC + test accuracy / precision / recall /
  F1 / ROC-AUC.
* **Artifacts**: per-model classification report (`*_classification_report.txt`).
* **Model**: `mlflow.sklearn.log_model` with the full preprocessing +
  classifier pipeline.

The selected best model is also registered in the MLflow Model Registry as
`heart-disease-classifier`. The local file store lives at `mlruns/`.

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
