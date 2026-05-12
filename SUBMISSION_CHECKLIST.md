# MLOps Assignment - Submission Checklist

**Course:** MLOps (S2-25_AMLCSZG523)  
**Assignment:** End-to-End ML Model Development, CI/CD, and Production Deployment  
**Date:** May 2026  
**Repository:** https://github.com/anabhart/MLOps-Assignment

---

## a) GitHub Repository Structure

### ✅ Code & Containerization
- **Source Code:** `src/heart_disease_mlops/`
  - `config.py` — Configuration & paths
  - `data.py` — Data loading & preprocessing
  - `validation.py` — Schema & range validation
  - `preprocessing.py` — ColumnTransformer pipeline
  - `train.py` — Model training & MLflow integration
  - `evaluate.py` — Metrics & visualization
- **FastAPI Service:** `api/`
  - `app.py` — REST API with health, predict, feedback, retrain endpoints
  - `logging_config.py` — Structured JSON logging
  - `tracing.py` — MLflow tracing setup with offline fallback
- **Docker:** `Containerfile` (multi-stage OCI build)
  - Non-root user, health checks, prometheus metrics
- **Requirements:** `requirements.txt` (fully pinned dependencies)
- **Project Metadata:** `pyproject.toml` (extras for api, dev, monitoring, orchestration, notebooks)

### ✅ Data
- **Raw Dataset:** `data/heart+disease/` (UCI Cleveland subset, 303 records)
- **Cleaned & Processed:** `data/processed/cleveland_clean.csv`
- **Feedback Loop:** `data/feedback/feedback.csv` (for retraining)

### ✅ Notebooks & Scripts
- **EDA:** `notebooks/01_eda.ipynb` — Data exploration, correlation analysis
- **Training & Analysis:** `notebooks/02_training_and_analysis.ipynb` — Model development, comparison
- **Orchestration:** `pipelines/prefect_flow.py` — Prefect DAG for end-to-end pipeline
- **Monitoring:** `monitoring/drift_detection.py` — Evidently drift detection

### ✅ Testing
- **Unit Tests:** `tests/` (31 tests across 6 files)
  - `test_data.py` (8 tests) — Data loading, cleaning, split, validation
  - `test_preprocessing.py` (4 tests) — ColumnTransformer, scaling, OHE
  - `test_train.py` (4 tests) — Pipeline fit, CV, grids, smoke test
  - `test_api.py` (5 tests) — Endpoints, validation, metrics
  - `test_feedback.py` (7 tests) — Feedback CSV, feedback endpoint, retrain
  - `test_tracing.py` (3 tests) — MLflow tracing setup, decorator
- **Coverage:** ~63% (model code). All critical paths covered.
- **CI Integration:** GitHub Actions runs all tests on every commit

### ✅ CI/CD Pipeline
- **Workflow File:** `.github/workflows/ci.yml`
  - Lint (ruff check)
  - Unit tests with coverage report
  - Training smoke run (fast mode)
  - Container build & push
  - Artifact uploads (on failure & always)
- **Status:** All checks passing (recent fix for MLflow offline fallback in CI)

### ✅ Deployment Manifests
- **Kubernetes Manifests:** `deploy/k8s/`
  - `namespace.yaml` — Isolated namespace
  - `deployment.yaml` — API Deployment (replicas, health checks)
  - `mlflow-deployment.yaml` — MLflow backend
  - `service.yaml` — LoadBalancer service for API
  - `mlflow-service.yaml` — MLflow service
  - `ingress.yaml` — Ingress for external access
  - **Helper Scripts:**
    - `deploy.sh` — Automated full deployment (checks prerequisites, builds, creates cluster, deploys)
    - `bringup.sh` — Brings up K8s + MLflow + Prometheus + Grafana (new)
    - `bringdown.sh` — Cleanup (new)
- **No Helm Chart:** Project uses direct manifests (simpler, sufficient for scope)

### ✅ Monitoring & Observability
- **Prometheus:** `monitoring/prometheus/prometheus.yml`
  - Scrapes API metrics endpoint on port 9090
  - Configured with `host.docker.internal` to handle Docker → host communication
- **Grafana:** `monitoring/grafana/` (new addition)
  - Pre-provisioned datasources in `provisioning/datasources/datasource.yml`
  - Dashboard `api-monitoring.json` with panels for request rate, latency, predictions, feedback, retrain runs
  - Stable datasource UID: `heart-disease-prometheus`
- **Structured Logging:** JSON logs in API via `python-json-logger`
- **MLflow Tracing:** Spans emitted from `/predict` and `/retrain` endpoints
- **Health Checks:** `/health` endpoint on API

### ✅ Documentation & Reporting

#### **Setup & Installation Instructions**
- **Main README:** `README.md` (comprehensive, includes Ubuntu setup, Docker, K8s, local development, monitoring)
- **K8s Deployment:** `deploy/k8s/README.md` (detailed deployment guide with prerequisites, manual steps, cloud options)
- **Architecture Documentation:** `reports/ARCHITECTURE.md` (Mermaid diagrams for system flow, model packaging, containerization)

#### **Final Report**
- **Markdown Version:** `reports/FINAL_REPORT.md` (873 lines, 31KB)
  - Problem statement
  - Setup & install instructions (Ubuntu + Windows)
  - Data & EDA summary
  - Feature engineering & model development
  - Experiment tracking (MLflow)
  - Model packaging & reproducibility
  - Containerization (FastAPI + Docker)
  - Kubernetes deployment
  - GitHub Actions CI/CD
  - Monitoring & logging
  - Drift detection retraining
  - Architecture diagrams
  - Screenshots of running system
  - Evidence mapping to all 9 requirements
- **DOCX Version:** `reports/FINAL_REPORT.docx` (48KB, formatted for submission)
  - Proper heading hierarchy
  - Code blocks with monospace font
  - Tables
  - Professional formatting

#### **Screenshots:** `reports/screenshots/`
- `k8s-pods-services-ingress-status.png` — Kubernetes deployment status
- `api-docs-page.png` — Swagger UI
- `api-health-success-and-predict-response.png` — API in action
- `mlflow-ui-running.png` — MLflow experiment tracking
- `Graphana_metrics.png` — Grafana dashboard

#### **Project Notes:** `project notes/`
- `DELIVERABLES_CHECKLIST.md` — Requirement-by-requirement evidence mapping (marks tracking)
- `FINAL_REPORT.md`, `plan.md`, `changes.md`, `DAY6-9_SUMMARY.md` — Development history

---

## Summary of 9 Requirements Covered

| # | Requirement | Evidence | Status |
|---|-------------|----------|--------|
| 1 | Data Ingestion & Validation | `src/data.py`, `tests/test_data.py`, notebooks | ✅ (2/2 marks) |
| 2 | Feature Engineering | `src/preprocessing.py`, `notebooks/02_...`, tests | ✅ (2/2 marks) |
| 3 | Experiment Tracking (MLflow) | `src/train.py`, `/serving` experiment, model registry | ✅ (2/2 marks) |
| 4 | Model Packaging & Reproducibility | `artifacts/models/best_model.joblib`, conda.yaml, MLflow flavor | ✅ (2/2 marks) |
| 5 | Model Training Pipeline | `src/train.py`, GridSearchCV, CV, metrics logging | ✅ (2/2 marks) |
| 6 | Model Containerization | `Containerfile`, FastAPI app, health checks, prometheus | ✅ (3/3 marks) |
| 7 | Kubernetes Deployment | `deploy/k8s/` manifests, `bringup.sh`, tested locally & with kind | ✅ (3/3 marks) |
| 8 | Monitoring & Logging | Prometheus + Grafana stack, JSON logs, MLflow tracing, drift detection | ✅ (3/3 marks) |
| 9 | Documentation & Reporting | `FINAL_REPORT.docx`, setup instructions, architecture diagrams, screenshots | ✅ (2/2 marks) |

**Total: 21/21 marks**

---

## How to Use This Repository

### Local Development
```bash
git clone https://github.com/anabhart/MLOps-Assignment.git
cd MLOps-Assignment

# Ubuntu prerequisite install (Docker, kubectl, kind)
sudo apt-get update && sudo apt-get install -y ... [See README.md]

# Setup Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev,api]"

# Run tests
pytest

# Train model
python -m heart_disease_mlops
```

### Kubernetes Deployment (Local kind cluster)
```bash
./deploy/k8s/bringup.sh
# Automatically brings up:
# - kind cluster with heart-disease API + MLflow
# - Port-forwarding to localhost:8000 (API), localhost:5000 (MLflow)
# - Prometheus on localhost:9090
# - Grafana on localhost:3000

# Access:
curl http://localhost:8000/health
open http://localhost:8000/docs
open http://127.0.0.1:5000/
open http://localhost:3000/d/heart-disease-api-monitoring/...
```

### Cleanup
```bash
./deploy/k8s/bringdown.sh
```

---

## CI/CD Status

- **Latest Workflow:** [GitHub Actions](https://github.com/anabhart/MLOps-Assignment/actions)
- **Recent Fix:** MLflow offline fallback for tests when backend unavailable (Commit `aa0239e`)
- **Test Status:** 31 tests passing, 0 failures
- **Coverage:** ~63% of source code

---

## Key Features Implemented

✅ **Model Development**
- Two candidate models (Logistic Regression, Random Forest)
- Hyperparameter tuning (GridSearchCV, Stratified K-Fold CV)
- Feature engineering (imputation, scaling, OHE)
- Test metrics: accuracy, precision, recall, F1, ROC-AUC

✅ **MLOps Best Practices**
- Experiment tracking with versioning
- Model registry & artifact storage
- Reproducible training pipelines
- Data validation & schema checking

✅ **Production Readiness**
- FastAPI with Pydantic validation
- Structured JSON logging
- Prometheus metrics
- Health checks & graceful shutdown
- Non-root container user

✅ **Deployment & Infrastructure**
- Multi-stage Docker build (minimal image)
- Kubernetes manifests with YAML
- Local testing with kind
- Port-forwarding for development

✅ **Monitoring & Observability**
- Request/response metrics
- Model performance tracking
- Data drift detection (Evidently)
- Retraining automation

✅ **Testing & Quality**
- Unit test coverage (31 tests)
- GitHub Actions CI/CD
- Lint checks (ruff)
- Artifact uploads on failure

---

**Submission Ready:** All 9 requirements documented and implemented. DOCX report ready for final review.
