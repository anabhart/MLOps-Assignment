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

## Experiment Tracking (Requirement 3)

MLflow is integrated across training, retraining, API tracing, and orchestration.

- Tracking URI resolution: `MLFLOW_SERVER_URI` / `MLFLOW_TRACKING_URI` with local fallback.
- Parameters logged per model run: best hyperparameters, model family, CV settings, train/feedback row counts.
- Metrics logged per model run: CV best score and test metrics (accuracy, precision, recall, F1, ROC-AUC).
- Artifacts logged per model run: classification report, confusion matrix PNG, ROC curve PNG, and serialized ML model.
- Experiment separation:
  - `heart-disease-cleveland` (training)
  - `heart-disease-feedback-retrain` (feedback-triggered retraining)
  - `heart-disease-serving` (API traces)
  - `heart-disease-prefect` (flow runs)

Use the UI to inspect tracked runs:

```powershell
mlflow ui --backend-store-uri mlruns
```

## Model Packaging & Reproducibility (Requirement 4)

The final model is saved in multiple reusable formats so it can be loaded,
served, and reproduced without retraining.

### Serialization formats

| Format | Path | Description |
|--------|------|-------------|
| **joblib** | `artifacts/models/best_model.joblib` | Primary serving artifact — full sklearn `Pipeline` |
| **MLflow sklearn flavor** | `mlruns/<exp>/<run>/artifacts/model/` | Per-run artifact with `conda.yaml` + `python_env.yaml` |
| **MLflow Model Registry** | `mlruns/models/heart-disease-classifier/` | Versioned registry with 20+ versions |

All three serialize the **complete sklearn `Pipeline`** (preprocessor + classifier together),
so a single `model.predict(X_raw)` call handles all feature transformations.

### Preprocessing pipeline

`src/heart_disease_mlops/preprocessing.py` builds a `ColumnTransformer` that is
always saved inside the model object:

- **Numeric** (age, trestbps, chol, thalach, oldpeak): `SimpleImputer(median)` → `StandardScaler`
- **Categorical** (sex, cp, fbs, restecg, exang, slope, ca, thal): `SimpleImputer(most_frequent)` → `OneHotEncoder`

Because the preprocessor is fitted as part of `Pipeline.fit()`, all fit statistics
(medians, encodings) are captured in the serialized object — **no train/serve skew** is possible.

### Dependency management

```bash
# Option 1: exact pip environment
pip install -r requirements.txt && pip install -e .

# Option 2: MLflow managed environment (uses stored conda.yaml)
mlflow models serve -m "models:/heart-disease-classifier/latest"

# Option 3: conda environment (from auto-generated file)
conda env create -f mlruns/<exp>/<run>/artifacts/model/conda.yaml
```

| Job | What it does |
| **Unit tests** | `pytest --cov=heart_disease_mlops` with `HEART_DISEASE_FAST_TRAIN=1` |
| **Training smoke** | Full `python -m heart_disease_mlops` in fast mode; uploads `training-artifacts` |
| **Container build** | `docker build -f Containerfile` then live `/health` + `/predict` smoke test |

Pip dependency caching (`cache: pip`) is enabled on all jobs. Duplicate
workflow runs are cancelled automatically (`cancel-in-progress: true`).

### Test suite (31 tests across 6 files)

| File | Tests | Coverage |
|------|-------|---------|
| `tests/test_data.py` | 8 | Raw load, cleaning, NA handling, stratified split, validation |
| `tests/test_preprocessing.py` | 4 | ColumnTransformer shape, standardization, OHE expansion, unseen categories |
| `tests/test_train.py` | 4 | Pipeline fit, CV structure, fast-mode grids, end-to-end smoke |
| `tests/test_api.py` | 5 | `/health`, `/model-info`, `/predict`, 422 validation, `/metrics` |
| `tests/test_feedback.py` | 7 | Feedback CSV, label validation, dataset augmentation, endpoints |
| `tests/test_tracing.py` | 3 | MLflow tracing setup, env disable, decorator execution |

### Artifact uploads per workflow run

- `pytest-artifacts` — uploaded **on failure** (debug: `artifacts/`, `mlruns/`)
- `training-artifacts` — uploaded **always** from the smoke run (`artifacts/`, `mlruns/`)

```bash
# Run tests locally
pytest --cov=heart_disease_mlops
# Lint
ruff check src tests api
```

## Model Containerization (Requirement 6)

### FastAPI application

The model-serving API is built with FastAPI and exposes multiple endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Liveness check |
| `/model-info` | GET | Model metadata |
| **`/predict`** | **POST** | **Binary prediction + confidence** |
| `/metrics` | GET | Prometheus metrics |
| `/feedback` | POST | Feedback submission |
| `/retrain` | POST | Trigger background retraining |

### /predict endpoint (JSON input/output)

**Request** (Pydantic-validated JSON):
```json
{
  "age": 63,
  "sex": 1,
  "cp": 1,
  "trestbps": 145,
  "chol": 233,
  "fbs": 1,
  "restecg": 2,
  "thalach": 150,
  "exang": 0,
  "oldpeak": 2.3,
  "slope": 3,
  "ca": 0,
  "thal": 6
}
```

**Response** (prediction + confidence):
```json
{
  "prediction": 1,
  "label": "disease",
  "probability": 0.95
}
```

### Container build & run locally

**Build**:
```bash
# Docker
docker build -t heart-disease-api -f Containerfile .

# Or podman (OCI-compatible)
podman build -t heart-disease-api -f Containerfile .
```

**Run**:
```bash
docker run -d --name api -p 8000:8000 heart-disease-api
# Wait for startup
sleep 8

# Health check
curl http://localhost:8000/health
# → {"status":"ok","model_loaded":"true"}

# Single prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "age": 63, "sex": 1, "cp": 1, "trestbps": 145, "chol": 233,
    "fbs": 1, "restecg": 2, "thalach": 150, "exang": 0,
    "oldpeak": 2.3, "slope": 3, "ca": 0, "thal": 6
  }'
# → {"prediction":1,"label":"disease","probability":0.95}

# Batch predictions from example_requests.json
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d @api/example_requests.json

# Interactive API docs (Swagger)
# Open http://localhost:8000/docs
```

**Tear down**:
```bash
docker stop api && docker rm api
```

### Container features

✅ **Multi-stage build** — minimal final image size  
✅ **Non-root user** — runs as `appuser` (UID 1000) for security  
✅ **Health check** — `curl http://localhost:8000/health` with retries  
✅ **Prometheus metrics** — `/metrics` for observability  
✅ **Input validation** — Pydantic enforces all field ranges; 422 on invalid input  
✅ **Embedded preprocessing** — sklearn `ColumnTransformer` inside the model  
✅ **MLflow tracing** — `/predict` requests emitted as MLflow spans for monitoring  
✅ **Volume mounts** — `/app/data/feedback` and `/app/artifacts` support bind-mounted volumes

### Docker Compose (local development)

Bring up a full stack (API + MLflow) locally:

```bash
docker compose up -d --build
# API on port 8000, MLflow on port 5000
docker compose down -v
```

## Quickstart

### Ubuntu setup for the full local demo

Use this sequence if you want the repository to work end to end on Ubuntu with these browser URLs at the end:

- http://localhost:8000/
- http://127.0.0.1:5000/
- http://localhost:8000/metrics
- http://localhost:3000/d/heart-disease-api-monitoring/heart-disease-api-monitoring?orgId=1&refresh=10s

#### 1. Install system prerequisites

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git python3 python3-venv python3-pip

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"

curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl

curl -Lo ./kind "https://kind.sigs.k8s.io/dl/v0.24.0/kind-linux-amd64"
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

newgrp docker
docker --version
kubectl version --client
kind --version
```

#### 2. Clone the repository

```bash
git clone https://github.com/anabhart/MLOps-Assignment.git
cd MLOps-Assignment
```

#### 3. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev,api]"
```

#### 4. Bring up Kubernetes, MLflow, Prometheus, and Grafana

```bash
./deploy/k8s/bringup.sh
```

What this single script now does:

1. Checks `docker`, `kubectl`, `kind`, and `curl`.
2. Builds the API image from `Containerfile`.
3. Creates the `kind` cluster if it does not already exist.
4. Deploys MLflow and the API to Kubernetes.
5. Waits until both deployments are healthy.
6. Starts port-forwarding so the API is on `localhost:8000` and MLflow is on `127.0.0.1:5000`.
7. Starts Prometheus and Grafana locally.
8. Verifies `/health`, `/metrics`, Prometheus readiness, and Grafana health.

#### 5. Verify the final result in your browser

Open these URLs:

- http://localhost:8000/
- http://localhost:8000/docs
- http://localhost:8000/metrics
- http://127.0.0.1:5000/
- http://localhost:3000/d/heart-disease-api-monitoring/heart-disease-api-monitoring?orgId=1&refresh=10s

Grafana login:

- username: `admin`
- password: `admin`

#### 6. Confirm the stack is healthy from the terminal

```bash
curl http://localhost:8000/health
curl http://localhost:8000/model-info
curl http://localhost:8000/metrics | head
curl http://127.0.0.1:5000/
kubectl -n heart-disease get pods,svc,ingress
```

#### 7. Bring everything down cleanly

```bash
./deploy/k8s/bringdown.sh
```

This stops the API and MLflow port-forwards, removes Prometheus and Grafana containers, and deletes the local `kind` cluster.

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

### 8. Monitoring & Logging (Requirement 8)

The API includes production-friendly observability out of the box:

- **Structured API logs** (JSON): method, path, status, latency, client IP
  - Implemented in `api/logging_config.py` and request middleware in `api/app.py`
- **Prometheus metrics** at `/metrics`
  - `predict_requests_total{status}`
  - `predict_latency_seconds` (histogram)
  - `predict_predictions_total{label}`
  - `feedback_submissions_total{correct}`
  - `feedback_rows` (gauge)
  - `retrain_runs_total{status}`
- **Grafana dashboard** pre-provisioned from file
  - `monitoring/grafana/dashboards/api-monitoring.json`

Start the full monitoring stack:

```bash
docker compose up -d --build
```

Access points:

- API docs: http://localhost:8000/docs
- Prometheus targets/query UI: http://localhost:9090
- Grafana dashboard: http://localhost:3000
  - login: `admin` / `admin`
  - dashboard: **Heart Disease API Monitoring**

Generate traffic so charts populate:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age":63,"sex":1,"cp":1,"trestbps":145,"chol":233,"fbs":1,"restecg":2,"thalach":150,"exang":0,"oldpeak":2.3,"slope":3,"ca":0,"thal":6}'
```

View request logs:

```bash
docker logs --tail=50 heart-disease-api
```

### 9. Drift detection
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
