# Completion Plan — Remaining Tasks

> Created: May 10, 2026.
> Scope: bridge the current pipeline (training + MLflow + notebooks) to the
> full assignment deliverables. Tooling target: **podman** for containers,
> **GitHub Actions** for CI, **FastAPI** for serving, **Prefect** for
> orchestration (optional but listed in checklist).

## Guiding principles
- Implement the **graded items first** (assignment marks, in order).
- Keep the package as the single source of truth — API, tests, CI, and the
  Prefect flow all import from `heart_disease_mlops`.
- Prefer minimal, working artifacts over heavy frameworks.

---

## Phase 1 — Repo hygiene (small, do first)

### 1.1 Initialize git + ignore rules
- `git init` at repo root.
- Create `.gitignore` covering: `.venv/`, `__pycache__/`, `*.pyc`,
  `artifacts/`, `mlruns/`, `data/processed/`, `*.joblib`, `.ipynb_checkpoints/`,
  installer binaries (`*.msix`, `*.exe`), `project notes.zip`.
- First commit: current pipeline + notebooks.

### 1.2 Pyproject (optional but cleaner)
- Add a minimal `pyproject.toml` declaring the `heart_disease_mlops` package
  so `pip install -e .` works (removes need for `PYTHONPATH=src`).

**Exit criteria**: `git status` clean; `pip install -e .` succeeds in a fresh venv.

---

## Phase 2 — Tests + CI (Assignment §5, 8 marks)

### 2.1 Unit tests (`tests/`)
- `tests/test_data.py`
  - `load_raw_cleveland` returns 303 rows, 14 cols, has `?` NaNs.
  - `clean_cleveland` drops NA rows, target is binary, no NaNs remain.
  - `train_test_split_df` is stratified and reproducible.
- `tests/test_preprocessing.py`
  - `build_preprocessor().fit_transform(X)` produces finite floats.
  - Numeric block has approx. zero mean / unit variance.
  - One-hot block expands to expected number of columns.
- `tests/test_train.py`
  - `build_pipeline(LogisticRegression(...))` fits on a tiny slice.
  - `cross_validate_pipeline` returns mean ∈ [0, 1].
  - End-to-end smoke: train with reduced grids, assert
    `artifacts/models/best_model.joblib` exists, AUC > 0.7.
- `pytest.ini` (or `[tool.pytest.ini_options]` in `pyproject.toml`):
  testpaths, `addopts = -ra -q`.

### 2.2 Linting
- `ruff` config in `pyproject.toml` — line length 100, ignore notebooks.

### 2.3 GitHub Actions (`.github/workflows/ci.yml`)
Single workflow on push/PR, Python 3.11:
1. **lint** — `pip install ruff && ruff check src tests`.
2. **test** — `pip install -r requirements.txt -e . && pytest`.
3. **train-smoke** — runs `python -m heart_disease_mlops` with a fast config
   (env var to shrink grids); uploads `artifacts/` and `mlruns/` as workflow artifacts.

**Exit criteria**: green CI on push.

---

## Phase 3 — FastAPI serving (Assignment §6, 5 marks)

### 3.1 API package (`api/app.py`)
- FastAPI app with:
  - `GET /health` → `{"status":"ok"}`.
  - `GET /model-info` → best model name, training timestamp, metrics
    (read from `artifacts/reports/training_summary.json`).
  - `POST /predict` → Pydantic `PatientFeatures` (13 fields, validated
    ranges per UCI doc). Response: `prediction` (0/1), `label`
    ("disease"/"no_disease"), `probability`.
- Lazy-load `best_model.joblib` once at startup.
- Unit-tested via `httpx.AsyncClient` in `tests/test_api.py`.

### 3.2 Sample requests
- `api/example_requests.json` with two patient payloads.
- README section: how to call with `curl` / `Invoke-RestMethod`.

**Exit criteria**: `uvicorn api.app:app` returns predictions for the sample
payloads; tests pass.

---

## Phase 4 — Containerization with podman (Assignment §6, part of §7)

### 4.1 `Containerfile`
- Base: `python:3.11-slim`.
- COPY `requirements.txt` first → `pip install`.
- COPY `src/`, `api/`, and the trained model from `artifacts/models/`.
- `EXPOSE 8000`; CMD `uvicorn api.app:app --host 0.0.0.0 --port 8000`.

### 4.2 Build + run docs
- `podman build -t heart-disease-api -f Containerfile .`
- `podman run --rm -p 8000:8000 heart-disease-api`
- Capture screenshot of `/predict` returning a result for `reports/`.

**Exit criteria**: container starts cleanly; `curl localhost:8000/health` →
`ok`; `/predict` returns expected schema.

---

## Phase 5 — Production deployment (Assignment §7, 7 marks)

Pick **one** of the two paths below depending on environment access:

### Path A — Local Kubernetes via podman + kind (recommended)
- `deploy/k8s/deployment.yaml` (1 replica, image pulled from local registry).
- `deploy/k8s/service.yaml` (`type: LoadBalancer` — works with kind +
  `cloud-provider-kind`, or fall back to `NodePort`).
- `deploy/k8s/ingress.yaml` (optional, nginx-ingress on kind).
- Documented commands: `kind create cluster`, `kind load docker-image …`,
  `kubectl apply -f deploy/k8s/`.
- Screenshot of `kubectl get pods,svc` and a successful `/predict` call.

### Path B — Free cloud (only if account available)
- Push image to GHCR.
- Deploy to fly.io / Render / a small Azure Container App.
- Document URL + usage.

**Exit criteria**: working endpoint reachable from outside the local API
process; screenshots saved to `reports/screenshots/`.

---

## Phase 6 — Monitoring & logging (Assignment §8, 3 marks)

- Add structured logging in the FastAPI app (request method, path, latency,
  prediction class) using stdlib `logging` + JSON formatter.
- Add **prometheus-client**:
  - `predict_requests_total` (Counter, labels: status).
  - `predict_latency_seconds` (Histogram).
  - Expose `/metrics`.
- Optional: `monitoring/grafana_dashboard.json` skeleton + screenshot.

**Exit criteria**: `/metrics` returns Prometheus exposition; screenshot of
basic dashboard or metrics output stored under `reports/`.

---

## Phase 7 — Orchestration (checklist §5, optional for marks)

- `pipelines/prefect_flow.py`:
  - Tasks: `ingest → validate → train → evaluate → register`.
  - Retry on transient errors; failure logs.
  - Local schedule example (cron, weekly).
- README section on running with `prefect server start` + `python pipelines/prefect_flow.py`.

**Exit criteria**: flow runs end-to-end; Prefect UI shows run history.

---

## Phase 8 — Drift + retraining runbook (checklist §11–12, optional)

- `monitoring/drift_detection.py` using **Evidently**:
  - Compare `data/processed/cleveland_clean.csv` (reference) vs a
    perturbed sample (simulate drift) → HTML report under `artifacts/`.
- `monitoring/RETRAINING_RUNBOOK.md`:
  - Trigger conditions (drift score, AUC drop, schedule).
  - Steps to retrain + redeploy + rollback.

---

## Phase 9 — Reporting & submission (Assignment §9, 2 marks + deliverables)

### 9.1 Architecture diagram
- Mermaid diagram in README **and** exported PNG (use mermaid-cli or VS Code
  preview screenshot).

### 9.2 Final report (10-page docx)
- Sections from assignment §9:
  1. Setup/install
  2. EDA & modelling choices
  3. Experiment tracking summary (MLflow screenshots)
  4. Architecture diagram
  5. CI/CD + deployment screenshots
  6. Repo link
- Draft in markdown (`reports/FINAL_REPORT.md`), then export to `.docx`
  via `pandoc reports/FINAL_REPORT.md -o reports/FINAL_REPORT.docx`.

### 9.3 Slides
- Short deck (~10 slides) — can be marp or PowerPoint export.

### 9.4 Demo video
- 6–10 min screencast: repo tour → train → MLflow UI → API call →
  container build → CI run → deployment.

---

## Suggested execution order (today → submission)

1. Phase 1 (repo hygiene) — quick win, unblocks CI.
2. Phase 2 (tests + CI) — graded heavily, lock in correctness early.
3. Phase 3 (FastAPI) — needed by every later phase.
4. Phase 4 (podman container) — verify reproducible serving.
5. Phase 5 (deployment) — assignment-critical.
6. Phase 6 (monitoring) — small, do alongside deployment.
7. Phase 7–8 (orchestration + drift) — optional, only if time remains.
8. Phase 9 (report, slides, video) — final day.

## Definition of "done" for the assignment
- `pytest` green locally and in CI.
- `podman build && podman run` serves predictions from a fresh checkout.
- Deployment screenshot proves live endpoint.
- MLflow UI screenshot proves logged runs.
- Final `.docx` report + slides + video uploaded with submission.
