# Heart Disease MLOps — Cleveland Subset

End-to-end MLOps pipeline for the **UCI Cleveland Heart Disease** dataset:
data ingestion + validation, scikit-learn training with MLflow experiment
tracking, Prefect orchestration, FastAPI serving, podman/Kubernetes
packaging, GitHub Actions CI, and Prometheus + Evidently monitoring.

## Project layout
```
data/heart+disease/processed.cleveland.data    # raw input (UCI)
src/heart_disease_mlops/                       # pipeline package
  config.py          # paths + feature schema
  data.py            # loading / cleaning / split
  validation.py      # schema + range validation
  preprocessing.py   # ColumnTransformer (impute + scale + OHE)
  train.py           # CV + GridSearch + MLflow + registry
  evaluate.py        # metrics + plots
api/                # FastAPI service (`/health`, `/predict`, `/model-info`, `/metrics`)
pipelines/          # Prefect orchestration flow
monitoring/         # Evidently drift + retraining runbook
deploy/k8s/         # Kubernetes manifests
notebooks/          # 01_eda.ipynb, 02_training_and_analysis.ipynb
tests/              # pytest suite (data, preprocessing, training, API)
.github/workflows/  # CI: lint -> test -> train-smoke -> container
reports/            # ARCHITECTURE.md, FINAL_REPORT.md, screenshots/
artifacts/          # generated models, reports, figures (git-ignored)
mlruns/             # MLflow tracking store (git-ignored)
```

## Model Development

Two classification models are trained and compared:
- **Logistic Regression**: Linear baseline (ROC-AUC: 0.8653)
- **Random Forest**: Ensemble classifier (ROC-AUC: **0.9116**, selected)

Both use the same preprocessing pipeline:
- Numeric features: Median imputation + StandardScaler
- Categorical features: Mode imputation + OneHotEncoder

Hyperparameter tuning via GridSearchCV with 5-fold stratified cross-validation on ROC-AUC. Full results in `artifacts/reports/training_summary.json` and classification reports.

## Quickstart

### 1. Install
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e ".[dev,api]"
```

### 2. Train + log to MLflow
```powershell
python -m heart_disease_mlops
# Inspect runs:
mlflow ui --backend-store-uri mlruns
```

A fast smoke run (used by CI) is available with:
```powershell
$env:HEART_DISEASE_FAST_TRAIN = "1"
python -m heart_disease_mlops
```

### 3. Serve the model
```powershell
uvicorn api.app:app --reload
# In another terminal:
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict `
     -H "Content-Type: application/json" `
     -d (Get-Content api/example_requests.json -Raw)
```

OpenAPI docs are available at <http://localhost:8000/docs>.

### 4. Run the pipeline with Prefect
```powershell
python pipelines/prefect_flow.py
# Optional: prefect server start  (in another terminal for the UI)
```

### 5. Run tests
```powershell
pytest                              # all tests
pytest -m "not slow"                # quick subset
ruff check src tests api            # lint
```

### 6. Build & run the container with podman
```powershell
podman build -t heart-disease-api:latest -f Containerfile .
podman run --rm -p 8000:8000 heart-disease-api:latest
```

### 7. Deploy to Kubernetes
See [deploy/k8s/README.md](deploy/k8s/README.md) for the kind quickstart.

### 8. Drift detection
```powershell
python monitoring/drift_detection.py
# Outputs artifacts/reports/drift_report.html + .json
# Exits non-zero when the share of drifted features exceeds the threshold.
```

## API contract

`POST /predict` (`Content-Type: application/json`)

```json
{
  "age": 63, "sex": 1, "cp": 1, "trestbps": 145, "chol": 233,
  "fbs": 1, "restecg": 2, "thalach": 150, "exang": 0,
  "oldpeak": 2.3, "slope": 3, "ca": 0, "thal": 6
}
```

Response:

```json
{ "prediction": 1, "label": "disease", "probability": 0.83 }
```

Other endpoints:
* `GET /health` — liveness/readiness.
* `GET /model-info` — best model name, training timestamp, test metrics.
* `GET /metrics` — Prometheus exposition.
* `POST /feedback` — record a corrected/confirmed example (see below).
* `POST /retrain` — schedule a retraining run that includes feedback rows.
* `GET /ui` — interactive web frontend.

## Web UI & feedback loop

A single-page frontend is bundled with the API and served at
[http://localhost:8000/ui](http://localhost:8000/ui). It lets you:

1. Fill the 13 patient features (or click *Load example*) and submit a
   prediction.
2. Confirm or correct the prediction with one click.
3. Trigger a retraining run that includes the accumulated feedback.

Submitting feedback appends a row to `data/feedback/feedback.csv` with all
13 features, the true label, and a UTC timestamp. The next call to
`train_and_log_all(include_feedback=True)` (the default) concatenates these
rows with the baseline Cleveland dataset, so the model **learns from human
corrections**. After a `/retrain` job finishes the new model is hot-reloaded
in-process — no restart required.

```bash
make ui                # opens http://localhost:8000/ui (starts API if needed)
make api               # just run the API (uvicorn) on $PORT
```

The `Makefile` is the single entry point for every common task — run
`make help` for the full list (`install`, `lint`, `test`, `train`, `prefect`,
`drift`, `api`, `ui`, `docker-build/run`, `kind-up/deploy`, `clean`, `ci`,
`all`, …).

## Documentation

* [reports/ARCHITECTURE.md](reports/ARCHITECTURE.md) — diagrams.
* [reports/FINAL_REPORT.md](reports/FINAL_REPORT.md) — written report.
* [monitoring/RETRAINING_RUNBOOK.md](monitoring/RETRAINING_RUNBOOK.md).
* [deploy/k8s/README.md](deploy/k8s/README.md).

## CI

The single workflow at `.github/workflows/ci.yml` runs **lint → test →
train-smoke → container** on every push and pull request and uploads the
trained `artifacts/` and `mlruns/` per run.
