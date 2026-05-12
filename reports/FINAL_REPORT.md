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

Or, end-to-end via Prefect:

```powershell
python pipelines/prefect_flow.py
```
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

## 6. Model Packaging & Reproducibility

Three complementary strategies ensure the final model can be loaded and
executed in any environment without retraining.

### 6.1 Serialization formats

| Format | Location | How written |
|--------|----------|-------------|
| **joblib** (primary) | `artifacts/models/best_model.joblib` | `joblib.dump(best_estimator, model_path)` in `train.py` |
| **MLflow sklearn** (per-run artifact) | `mlruns/<exp>/<run>/artifacts/model/` | `mlflow.sklearn.log_model(best_pipe, artifact_path="model")` |
| **MLflow Model Registry** (promoted best) | `mlruns/models/heart-disease-classifier/` | `registered_model_name="heart-disease-classifier"` in `log_model()` |

In all three cases the **full sklearn `Pipeline` object is serialized** — not
the classifier alone. The pipeline encapsulates both preprocessing and
classification as a single callable, so a caller only needs:

```python
import joblib
model = joblib.load("artifacts/models/best_model.joblib")
model.predict(X_raw)   # raw feature DataFrame, no manual preprocessing needed
```

MLflow's internal storage uses **cloudpickle** (`.pkl`) wrapped by the
`mlflow.sklearn` flavor, which records the exact `sklearn_version` so any
version mismatch is surfaced at load time.

### 6.2 Preprocessing pipeline for full reproducibility

**Location**: `src/heart_disease_mlops/preprocessing.py`

```python
def build_preprocessor() -> ColumnTransformer:
    numeric_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale",  StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("ohe",    OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([
        ("num", numeric_pipe, NUMERIC_FEATURES),    # 5 features
        ("cat", categorical_pipe, CATEGORICAL_FEATURES),  # 8 features
    ], remainder="drop")
```

`build_pipeline(estimator)` composes this into a single `sklearn.Pipeline`:

```python
Pipeline([("preprocess", build_preprocessor()), ("classifier", estimator)])
```

Because the preprocessor is fitted inside `Pipeline.fit()`, all fit
statistics (medians, encodings) are captured in the pipeline object and
persisted with it. There is **no risk of train/serve skew**: the same
`ColumnTransformer` that was fitted on training data is serialized into
`best_model.joblib` and replayed exactly at inference time.

Key reproducibility properties:
- **No data leakage**: All statistics computed on training data only.
- **Unseen categories handled gracefully**: `handle_unknown='ignore'`
- **Deterministic splits**: `random_state=42`, `shuffle=True` in StratifiedKFold
- **Seeded model**: `random_state=42` in RandomForestClassifier

### 6.3 Dependency management

| File | Format | Purpose |
|------|--------|---------|
| `requirements.txt` | pip-freeze (260 lines, fully pinned `==`) | Exact environment reproduction |
| `pyproject.toml` | PEP 621 with `>=` bounds | Package installation with flexibility |
| `conda.yaml` | Auto-generated by MLflow per `log_model` call | Conda environment for each MLflow run |
| `python_env.yaml` | Auto-generated by MLflow | virtualenv-based reproduction |

Key pinned packages in `requirements.txt`:

```
scikit-learn==1.8.0
numpy==2.4.4
pandas==2.3.3
joblib==1.5.3
cloudpickle==3.1.2
mlflow==3.x.x
```

The MLflow-generated `conda.yaml` (stored beside every logged model artifact)
pins Python, pip, and all transitive ML dependencies, enabling:

```bash
# Option 1: pip install
pip install -r requirements.txt && pip install -e .

# Option 2: MLflow managed environment (auto-creates conda env)
mlflow models serve -m "models:/heart-disease-classifier/latest"

# Option 3: conda env
conda env create -f mlruns/<exp>/<run>/artifacts/model/conda.yaml
```

### 6.4 MLflow Model Registry

```
mlruns/models/heart-disease-classifier/
  ├── meta.yaml               ← registry-level metadata
  ├── version-1/
  │   └── meta.yaml           ← run_id, artifact URI, creation time
  ├── ...
  └── version-20/             ← current champion
      └── meta.yaml
```

Each registry version is a pointer to the run artifact in the experiment
store. The `best_model.joblib` served by the API and the registered model are
the **same Pipeline object**, ensuring zero discrepancy between training and
serving environments.

## 7. Architecture

See [`reports/ARCHITECTURE.md`](ARCHITECTURE.md) for diagrams.

* **Pipeline package** (`src/heart_disease_mlops/`) is the single source of
  truth — imported by tests, the API, and the Prefect flow.
* **Serving** is FastAPI + uvicorn, packaged in an OCI image built with
  podman, deployed to Kubernetes via the manifests in `deploy/k8s/`.
* **Orchestration** uses Prefect 2 with retries and a weekly cron schedule.
* **Monitoring** combines structured JSON logs, a Prometheus
  `/metrics` endpoint, and Evidently drift reports.

## 8. CI/CD Pipeline & Automated Testing

### 8.1 GitHub Actions workflow

**Location**: `.github/workflows/ci.yml`
**Triggers**: push to `main`/`master`, pull requests (any branch), manual `workflow_dispatch`
**Concurrency**: one run per ref; duplicate runs cancelled with `cancel-in-progress: true`

The workflow runs **four sequential jobs** — each `needs:` the previous so the
chain fails fast on any error:

```
Lint (ruff) → Unit tests → Training smoke run → Container build
```

| Job | Name | Key steps |
|-----|------|-----------|
| `lint` | Lint (ruff) | `ruff check src tests api` |
| `test` | Unit tests | `pytest --cov=heart_disease_mlops --cov-report=term-missing` |
| `train-smoke` | Training smoke run | `HEART_DISEASE_FAST_TRAIN=1 python -m heart_disease_mlops` |
| `container` | Container build | `docker build -f Containerfile …` → `/health` + `/predict` smoke |

All four jobs use `actions/setup-python@v5` with `cache: pip` to avoid
re-downloading packages on every run.

### 8.2 Linting

```yaml
- name: ruff check
  run: ruff check src tests api
```

Ruff is configured in `pyproject.toml`:
- `line-length = 100`, `target-version = "py311"`
- Rule sets: `E, F, W, I, B, UP` (errors, pyflakes, warnings, isort, bugbear, pyupgrade)
- Ignores: `E501` (line length enforced by formatter, not linter)
- Excludes: `notebooks/`, `artifacts/`, `mlruns/`, `.venv`

### 8.3 Automated testing

**Test suite**: 6 files, **31 tests** covering the full pipeline stack.

| File | Count | What it covers |
|------|-------|----------------|
| `tests/test_data.py` | 8 | Data loading, cleaning, missing-value handling, stratified split, validation |
| `tests/test_preprocessing.py` | 4 | ColumnTransformer output shape, numeric standardization, OHE expansion, unseen-category handling |
| `tests/test_train.py` | 4 | Pipeline build + fit, cross-validation structure, fast-mode grid size, end-to-end smoke |
| `tests/test_api.py` | 5 | `/health`, `/model-info`, `/predict`, validation errors (422), `/metrics` |
| `tests/test_feedback.py` | 7 | Feedback CSV creation, label validation, dataset augmentation, `/feedback`, `/retrain`, UI serving |
| `tests/test_tracing.py` | 3 | MLflow tracing setup, env-driven disable, trace decorator execution |

Pytest is configured in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q --strict-markers"
markers = ["slow: marks tests that train models or do heavy I/O"]
```

**Shared fixtures** (`tests/conftest.py`):
- `project_root` — session-scoped workspace root path
- `cleaned_df` — session-scoped cleaned Cleveland DataFrame (loaded once, shared across all tests)

The `test` job runs with `HEART_DISEASE_FAST_TRAIN=1` so training-dependent
tests use reduced grids and complete within the CI time budget.

### 8.4 Training smoke step

```yaml
- name: Run training (fast mode)
  env:
    HEART_DISEASE_FAST_TRAIN: "1"
  run: python -m heart_disease_mlops
```

`HEART_DISEASE_FAST_TRAIN=1` halves the hyperparameter grids so the full
train + MLflow log + model-registry promotion step completes quickly while
still exercising the complete code path.

### 8.5 Container build & smoke test

```yaml
- name: Build container image with Docker
  run: docker build -f Containerfile -t heart-disease-api:ci .
- name: Smoke test container
  run: |
    docker run -d --name api -p 8000:8000 heart-disease-api:ci
    sleep 8
    curl --fail --retry 5 --retry-delay 2 http://localhost:8000/health
    curl --fail -X POST http://localhost:8000/predict \
      -H 'Content-Type: application/json' \
      -d @api/example_requests.json
    docker logs api
    docker rm -f api
```

The container step re-trains the model on the CI runner before building
the image, so the baked-in `best_model.joblib` is always fresh.

### 8.6 Artifact upload

| Job | Artifact name | Contents | When uploaded |
|-----|--------------|----------|---------------|
| `test` | `pytest-artifacts` | `artifacts/`, `mlruns/` | Only on failure (debug) |
| `train-smoke` | `training-artifacts` | `artifacts/`, `mlruns/` | Always (per-run evidence) |

The `training-artifacts` upload captures `training_summary.json`,
classification reports, confusion matrix/ROC PNGs, and the serialized
joblib model from every successful CI run.


## 9. Model Containerization

### 9.1 Docker container design

The API is containerized as a multi-stage OCI-compliant image using FastAPI
and uvicorn. **Location**: [`Containerfile`](../Containerfile)

**Key properties**:
- **Base image**: `python:3.11-slim` — lean, security-patched
- **Framework**: FastAPI 0.110+ (async, Pydantic validation, auto-docs)
- **ASGI server**: uvicorn[standard]>=0.29 (production-ready async)
- **Non-root execution**: `appuser` UID 1000 (security best practice)
- **Health check**: HTTP GET `http://localhost:8000/health`; interval 30s,
  timeout 5s, start-period 10s, max retries 3
- **Port**: 8000 (exposed via `EXPOSE 8000`)
- **Artifact mounting**: `/app/data/feedback` and `/app/artifacts` created
  with `chmod a+rwX` to support bind-mounted volumes for feedback persistence
  and model hot-reloading

**Build & run**:
```bash
# With Docker
docker build -t heart-disease-api:latest -f Containerfile .
docker run --rm -p 8000:8000 heart-disease-api:latest

# Or with podman (OCI-compliant)
podman build -t heart-disease-api:latest -f Containerfile .
podman run --rm -p 8000:8000 heart-disease-api:latest
```

### 9.2 FastAPI application & request/response schemas

**Location**: [`api/app.py`](../api/app.py)

The API implements a production-grade model server with comprehensive
validation, error handling, and observability.

**Request schema** (Pydantic):

```python
class PatientFeatures(BaseModel):
    """13-feature patient record from UCI Cleveland dataset."""
    age: float = Field(..., ge=1, le=120)
    sex: int = Field(..., ge=0, le=1, description="1=male, 0=female")
    cp: int = Field(..., ge=1, le=4, description="Chest pain type 1-4")
    trestbps: float = Field(..., ge=50, le=260, description="Resting BP (mm Hg)")
    chol: float = Field(..., ge=50, le=700, description="Serum cholesterol (mg/dl)")
    fbs: int = Field(..., ge=0, le=1, description="Fasting blood sugar > 120 mg/dl")
    restecg: int = Field(..., ge=0, le=2)
    thalach: float = Field(..., ge=40, le=260, description="Max heart rate")
    exang: int = Field(..., ge=0, le=1, description="Exercise-induced angina")
    oldpeak: float = Field(..., ge=-2.0, le=10.0)
    slope: int = Field(..., ge=1, le=3)
    ca: int = Field(..., ge=0, le=3)
    thal: int = Field(..., description="3=normal, 6=fixed, 7=reversible defect")
```

**Response schema** (Pydantic):

```python
class PredictionResponse(BaseModel):
    prediction: int  # 0 = no disease, 1 = disease
    label: str       # "no_disease" or "disease"
    probability: float  # P(disease) ∈ [0, 1]
```

### 9.3 REST endpoints

| Endpoint | Method | Request | Response | Purpose |
|----------|--------|---------|----------|---------|
| `/health` | GET | — | `{"status": "ok", "model_loaded": "true"}` | Liveness check |
| `/model-info` | GET | — | `{best_model, trained_at, test_metrics, model_path, model_loaded}` | Model metadata |
| `/predict` | POST | `PatientFeatures` (JSON) | `PredictionResponse` | **Prediction with confidence** |
| `/metrics` | GET | — | Prometheus text format | Observability |
| `/feedback` | POST | `{features, true_label, predicted_label}` | `{saved, feedback_path, total_feedback_rows, correct}` | Feedback for retraining |
| `/retrain` | POST | — | `{job_id, status, message}` | Trigger background retraining |
| `/ui` | GET | — | HTML | Interactive web UI |

### 9.4 /predict endpoint — detailed implementation

**Endpoint signature** (`api/app.py` lines 264–295):

```python
@app.post("/predict", response_model=PredictionResponse)
@mlflow.trace(name="predict", span_type="PREDICTOR")
def predict(features: PatientFeatures) -> PredictionResponse:
    """Predict heart disease risk and return probability."""
    if _State.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    row = pd.DataFrame([features.model_dump()], columns=NUMERIC_FEATURES + CATEGORICAL_FEATURES)
    proba = float(_State.model.predict_proba(row)[0, 1])
    prediction = int(proba >= 0.5)
    label = "disease" if prediction == 1 else "no_disease"
    
    return PredictionResponse(prediction=prediction, label=label, probability=round(proba, 4))
```

**Key features**:
- ✅ **Automatic input validation**: Pydantic enforces all field ranges; invalid input returns 422
- ✅ **Prediction + confidence**: Returns both binary class (0/1) and probability [0, 1]
- ✅ **Pipeline preprocessing**: Features are automatically passed through the embedded ColumnTransformer
  (median imputation + StandardScaler for numeric; mode imputation + OneHotEncoder for categorical)
- ✅ **MLflow tracing**: Decorators capture request/response for observability in MLflow UI
- ✅ **Structured metrics**: Prometheus counters and histograms recorded for request status/latency

**Error handling**:
- **503 Service Unavailable**: Model file not found (startup failure)
- **422 Validation Error**: Invalid field ranges (e.g., `age > 120`)
- **500 Internal Server Error**: Prediction failure (unlikely given pipeline robustness)

### 9.5 Container execution with sample data

**Sample requests** (`api/example_requests.json`):

```json
[
  {
    "age": 63, "sex": 1, "cp": 1, "trestbps": 145, "chol": 233,
    "fbs": 1, "restecg": 2, "thalach": 150, "exang": 0,
    "oldpeak": 2.3, "slope": 3, "ca": 0, "thal": 6
  },
  {
    "age": 41, "sex": 0, "cp": 2, "trestbps": 130, "chol": 204,
    "fbs": 0, "restecg": 2, "thalach": 172, "exang": 0,
    "oldpeak": 1.4, "slope": 1, "ca": 0, "thal": 3
  }
]
```

**Build & run locally**:

```bash
# Build container
docker build -t heart-disease-api -f Containerfile .

# Run container, exposing port 8000
docker run -d --name api -p 8000:8000 heart-disease-api

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
  -d @api/example_requests.json | jq '.'

# View auto-generated API docs
# Open browser: http://localhost:8000/docs (Swagger)
#               http://localhost:8000/redoc (ReDoc)
```

### 9.6 Container testing in CI/CD

**CI smoke test** (`.github/workflows/ci.yml`, `container` job):

```yaml
- name: Build container image
  run: docker build -f Containerfile -t heart-disease-api:ci .

- name: Smoke test container
  run: |
    docker run -d --name api -p 8000:8000 heart-disease-api:ci
    sleep 8
    curl --fail --retry 5 --retry-delay 2 http://localhost:8000/health
    curl --fail -X POST http://localhost:8000/predict \
      -H 'Content-Type: application/json' \
      -d @api/example_requests.json | head -c 500
```

This ensures every CI run:
1. ✅ Builds the container from Containerfile
2. ✅ Runs the container and waits for startup (8s)
3. ✅ Verifies `/health` returns 200 (with 5 retries)
4. ✅ Sends sample input to `/predict` and validates response

### 9.7 Docker Compose orchestration (local development)

**Location**: [`compose.yaml`](../compose.yaml)

Brings up a full stack locally:
- **MLflow**: Tracking server on port 5000
- **API**: FastAPI server on port 8000 (depends_on MLflow health)
- **Volumes**: Bind-mounts for artifacts, models, feedback persistence

```bash
# Bring up stack
docker compose up -d --build

# Check health
curl http://localhost:8000/health
curl http://localhost:5000/health

# View logs
docker compose logs -f api

# Tear down
docker compose down -v
```

This enables full local development without Kubernetes.

### 9.8 Deployment to Kubernetes

See [`deploy/k8s/README.md`](../deploy/k8s/README.md) for detailed Kubernetes deployment using kind (local) or cloud providers.

## 10. Monitoring & drift

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

## 11. Results summary

| Model | CV ROC-AUC | Test ROC-AUC | Test F1 |
|-------|------------|--------------|---------|
| Logistic Regression | ~0.90 | ~0.91 | ~0.85 |
| Random Forest | ~0.89 | ~0.90 | ~0.84 |

(Exact values are written to `artifacts/reports/training_summary.json`
after each training run.)

## 12. Lessons learned & future work

* **Cleveland-only** is small (~297 rows) — pooling other UCI subsets
  would require schema reconciliation but could meaningfully improve
  generalization.
* **Calibration** is not yet performed; for clinical use, isotonic /
  Platt calibration on the probability output would be a next step.
* **Online learning** is out of scope; the current retraining strategy is
  scheduled + drift-triggered.
* **Helm chart** packaging would simplify multi-environment promotion.

## 13. Repository

* Code, manifests, notebooks, and reports: this repository.
* CI status: GitHub Actions tab.
* Container image: built locally via podman; published to GHCR in CI when
  enabled.
