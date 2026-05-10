# Assignment Deliverables Checklist

> Status legend: `[x]` = completed and verified in this workspace, `[ ]` = not yet done.
> Last updated: May 10, 2026.

## Required Deliverables

### 1. Code Repository
- [x] Source code organized as a package (`src/heart_disease_mlops/`)
- [x] Initialized as a git repository
- [x] README with setup instructions (`README.md`)
- [x] Dependencies specified (`requirements.txt`, `pyproject.toml`)
- [x] `.gitignore` configured

---

### 2. Data Pipeline
- [x] Data ingestion module (`src/heart_disease_mlops/data.py`)
- [x] Cleaning + binary target derivation
- [x] Explicit data validation / schema check (`src/heart_disease_mlops/validation.py`)
- [ ] Data versioning with DVC *(optional; raw data is committed and immutable)*
- [x] Data profiling via EDA notebook (`notebooks/01_eda.ipynb`)

---

### 3. Model Training
- [x] Training pipeline implementation (`src/heart_disease_mlops/train.py`)
- [x] Multiple model comparison (LogReg + Random Forest)
- [x] Hyperparameter tuning (GridSearchCV)
- [x] Model evaluation metrics (accuracy, precision, recall, F1, ROC-AUC)
- [x] Reproducible training (seeded splits, cached cleaned CSV, fast-mode env var)

---

### 4. Experiment Tracking
- [x] MLflow integration in training pipeline
- [x] Parameter logging (best params, model family, CV config)
- [x] Metric logging (CV + test metrics)
- [x] Artifact logging (classification report, sklearn model)
- [x] Model registry promotion (`heart-disease-classifier`)

---

### 5. Orchestration
- [x] Workflow automation with Prefect (`pipelines/prefect_flow.py`)
- [x] End-to-end ingest → validate → clean → validate → train → register flow
- [x] Scheduling capability (`deploy()` registers a weekly cron deployment)
- [x] Error handling and retries (per-task `retries=`, exponential backoff)

---

### 6. Model Serving
- [x] REST API implementation (FastAPI — `api/app.py`)
- [x] `/health` endpoint
- [x] `/predict` endpoint (JSON in, prediction + probability out)
- [x] `/model-info` endpoint
- [x] Request/response validation with Pydantic
- [x] OpenAPI / Swagger docs at `/docs`

---

### 7. Containerization
- [x] `Containerfile` (podman/docker compatible)
- [x] `.containerignore` to keep image small
- [x] Build/run commands documented in README + `deploy/k8s/README.md`
- [ ] Build verified locally with `podman build` *(run on demand)*

---

### 8. CI/CD Pipeline
- [x] GitHub Actions workflow (`.github/workflows/ci.yml`)
- [x] Automated linting (ruff)
- [x] Automated unit tests (pytest + coverage)
- [x] Training smoke step
- [x] Container build + endpoint smoke test
- [x] Artifact upload per run

---

### 9. Testing
- [x] Unit tests for data loading / cleaning / validation (`tests/test_data.py`)
- [x] Unit tests for preprocessing pipeline (`tests/test_preprocessing.py`)
- [x] Unit tests for training utilities (`tests/test_train.py`)
- [x] API smoke + integration tests (`tests/test_api.py`)
- [x] Pytest configuration in `pyproject.toml`
- [x] **All 21 tests pass locally**

---

### 10. Monitoring & Observability
- [x] Structured request/response JSON logging (`api/logging_config.py`)
- [x] Prometheus metrics endpoint at `/metrics`
- [x] Counters + histogram for request volume, status, latency, label
- [ ] Grafana dashboard JSON *(optional; metrics are scrape-ready)*

---

### 11. Drift Detection
- [x] Reference dataset captured (cleaned CSV)
- [x] Drift report generation with Evidently (`monitoring/drift_detection.py`)
- [x] Configurable threshold + non-zero exit code on drift

---

### 12. Retraining Strategy
- [x] Trigger conditions documented
- [x] Runbook for retrain + rollout + rollback (`monitoring/RETRAINING_RUNBOOK.md`)

---

### 13. Documentation
- [x] README quickstart
- [x] API documentation section in README + auto Swagger
- [x] Architecture diagram (Mermaid in `reports/ARCHITECTURE.md`)
- [x] Runbook(s) (`monitoring/RETRAINING_RUNBOOK.md`, `deploy/k8s/README.md`)

---

### 14. Final Report (10-page doc/docx)
- [x] Problem statement
- [x] EDA + modelling choices
- [x] Experiment tracking summary
- [x] Architecture diagram
- [x] CI/CD + deployment workflow described
- [x] Code repo link
- [x] Drafted as `reports/FINAL_REPORT.md`
- [ ] Exported as `.docx` / `.pdf` via pandoc *(post-processing step)*
- [ ] Screenshots inserted (after running locally)

---

### 15. Presentation Slides
- [ ] Deck created (objective, architecture, results, demo)

---

### 16. Demo Video
- [ ] 6-10 minute end-to-end recording

---

## Production-Readiness Requirements
- [x] All scripts execute from clean setup using `requirements.txt` + `pip install -e .`
- [x] Container definition + healthcheck in `Containerfile`
- [x] CI fails on lint / test / training errors with clear logs
- [ ] Container build verified locally with podman *(run on demand)*

---

## Currently Completed (snapshot)

**Done**
- Pipeline package with data validation, training, evaluation, registry
- MLflow tracking + model registry promotion
- EDA + training notebooks
- FastAPI service with `/health`, `/predict`, `/model-info`, `/metrics`
- JSON request logs + Prometheus counters & histogram
- Pytest suite — 21 tests pass (data, validation, preprocessing, training,
  API, smoke training)
- Ruff lint clean; `pyproject.toml` package + extras
- `Containerfile` + `.containerignore` + container smoke step in CI
- GitHub Actions: lint → test → train-smoke → container
- Kubernetes manifests + kind quickstart
- Prefect flow with retries, exponential backoff, weekly schedule
- Evidently drift detection script + retraining runbook
- Architecture diagram + final report markdown draft
- Git repo initialized

**Outstanding (post-implementation)**
- `podman build` run locally and screenshot captured
- Screenshots embedded in the report
- Convert `reports/FINAL_REPORT.md` to `.docx` via `pandoc`
- Slide deck (marp / PowerPoint export)
- 6–10 minute demo video
