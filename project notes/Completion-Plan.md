# Completion Plan — MLOps Assignment I (Due May 10, 2026)

## Task-by-Task Status (50 marks total)

### ✅ Done — Task 1: Data Acquisition & EDA [5 marks]
- Download script/instructions ✅ (`notebooks/eda_heart_disease.ipynb`, UCI auto-fetch)
- Missing value handling + feature encoding ✅
- Histograms, correlation heatmap, class balance ✅
- **Gap**: Notebook outputs not yet saved (cells not executed) — run and save before submitting.

---

### ✅ Done — Task 2: Feature Engineering & Model Development [8 marks]
- Scaling + encoding ✅ (`StandardScaler` + `SimpleImputer` in `train.py`'s `build_pipeline`; `OneHotEncoder` for categoricals in the training notebook)
- Logistic Regression + Random Forest ✅ (`compare_models.py`, `training_and_evaluation.ipynb`)
- Cross-validation (`cross_validate`, 5-fold) ✅ (`notebooks/training_and_evaluation.ipynb`)
- accuracy, precision, recall, ROC-AUC ✅
- Model selection documented ✅ (`models/baseline_comparison/`)
- No gaps.

---

### ✅ Done — Task 3: Experiment Tracking [5 marks]
- MLflow integration ✅
- Parameters, metrics, artifacts, plots logged ✅
- No gaps.

---

### ✅ Done — Task 4: Model Packaging & Reproducibility [7 marks]
- Model saved as `models/model.joblib` ✅
- `pyproject.toml` with pinned deps ✅
- Preprocessing pipeline for reproducibility ✅
- `requirements.txt` generated from venv (241 packages) ✅

---

### ✅ Done — Task 5: CI/CD Pipeline & Automated Testing [8 marks]
- Pytest unit/smoke tests ✅ (`tests/test_smoke.py`)
- GitHub Actions with lint + test + train + evaluate + Podman build ✅ (`.github/workflows/ci.yml`)
- `actions/upload-artifact` uploads `model.joblib`, `train_metrics.json`, `eval_metrics.json` per run ✅
- No gaps.

---

### ✅ Done — Task 6: Model Containerization [5 marks]
- Dockerfile + FastAPI `/predict` endpoint ✅
- JSON input / prediction output ✅
- Local build + run documented ✅ (`Makefile`)
- No gaps.

---

### ✅ Done — Task 7: Production Deployment [7 marks]
- `k8s/deployment.yaml` — Deployment manifest with health probes, resource limits, Prometheus annotations ✅
- `k8s/service.yaml` — NodePort service on port 30800 (Minikube/Docker Desktop) ✅
- Makefile targets: `make k8s-load`, `make k8s-deploy`, `make k8s-status`, `make k8s-url`, `make k8s-delete` ✅
- Compatible with Minikube (Podman or Docker driver) and Docker Desktop k8s without manifest changes ✅
- **Gap**: Deployment screenshots still needed (run after `make k8s-deploy`).
- **Gap**: LoadBalancer / Ingress not configured (NodePort is sufficient for Minikube demo).

---

### ✅ Done — Task 8: Monitoring & Logging [3 marks]
- API request logging ✅ (Prometheus metrics in `api/app.py`)
- Prometheus `/metrics` endpoint ✅
- `docker-compose.yml` with API + Prometheus + Grafana services ✅ (`make compose-up`)
- `monitoring/prometheus.yml` scrape config ✅
- `monitoring/grafana/provisioning/` auto-provisions datasource + dashboard ✅
- Grafana dashboard: latency percentiles, prediction rate, error count, predictions by class ✅
- Access Grafana at http://localhost:3000 (admin/admin) after `make compose-up` ✅

---

### ❌ Missing — Task 9: Documentation & Reporting [2 marks]
- Report template exists (`reports/FINAL_REPORT_TEMPLATE.md`) but content not filled in.
- Assignment requires a **10-page doc/docx file** specifically.
- **No architecture diagram** (no image file in the repo).
- **No screenshots folder**.

---

## Deliverables Gap Summary

| Deliverable | Status |
|---|---|
| GitHub repo with code, Dockerfile, pyproject.toml | ✅ |
| `requirements.txt` | ✅ Generated (`pip freeze`, 241 packages) |
| Cleaned dataset + download script | ✅ |
| Jupyter notebooks — EDA | ✅ (outputs not saved yet) |
| Jupyter notebooks — training & evaluation | ✅ `notebooks/training_and_evaluation.ipynb` |
| Jupyter notebooks — inference | ❌ Missing |
| `tests/` folder with unit tests | ✅ |
| GitHub Actions YAML | ✅ |
| Deployment manifests (`k8s/deployment.yaml`, `k8s/service.yaml`) | ✅ |
| Screenshots folder | ❌ Missing |
| Final written report (10-page DOCX) | ❌ Missing |
| Short demo video | ❌ Missing |
| Deployed API URL or local access instructions | ✅ Local k8s via `make k8s-deploy && make k8s-url` |

---

## Priority Order (May 10 — Remaining)

| Priority | Item | Status | Marks at Stake |
|---|---|---|---|
| 1 | **Kubernetes manifests + Minikube deploy** (`k8s/`) | ✅ Done | 7 |
| 2 | **`requirements.txt`** | ✅ Done | Part of Task 4 |
| 3 | **Monitoring stack** (`docker-compose.yml` + Grafana) | ✅ Done | Part of Task 8 |
| 4 | **Run + save EDA notebook** (execute all cells, save with outputs) | ⚠️ Pending | Task 1 |
| 5 | **Inference notebook** — load model + run predictions | ❌ Missing | Deliverables |
| 6 | **Screenshots folder** — MLflow UI, CI run, API response, container run, k8s pods | ❌ Missing | Task 9 |
| 7 | **Final report DOCX** — fill in `FINAL_REPORT_TEMPLATE.md` and export as DOCX | ❌ Missing | 2 |
| 8 | **Demo video** (6–10 min screen recording) | ❌ Missing | Deliverables |
