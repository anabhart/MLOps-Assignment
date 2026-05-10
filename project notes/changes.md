# Change Log

## 2026-05-02

### 1) Initial project scaffold (committed)
- Commit: `5041d2d`
- Summary: Bootstrapped end-to-end MLOps project structure and baseline pipeline.

**Added/Configured**
- Project structure: `src/`, `pipelines/`, `api/`, `tests/`, `data/`, `models/`, `reports/`, `slides/`, `demo/`, `monitoring/`
- Core config: `pyproject.toml`, `Makefile`, `.gitignore`, `.env.example`, `README.md`
- Baseline ML package:
  - `src/heart_disease_mlops/data.py`
  - `src/heart_disease_mlops/train.py`
  - `src/heart_disease_mlops/evaluate.py`
- Orchestration/API/CI/DVC:
  - `pipelines/prefect_flow.py`
  - `api/app.py`
  - `.github/workflows/ci.yml`
  - `dvc.yaml`
  - `Dockerfile`
- Initial test:
  - `tests/test_smoke.py`

### 2) UCI dataset integration (working tree)
- Goal: Replace mandatory local CSV dependency with UCI fetch (`ucimlrepo`) + local cache.

**Updated files**
- `pyproject.toml`
  - Added dependency: `ucimlrepo>=0.0.3`

- `src/heart_disease_mlops/data.py`
  - Added UCI integration:
    - `UCI_DATASET_ID = 45`
    - `fetch_from_uci(cache_path=...)`
  - Implemented automatic cache at `data/raw/heart.csv`
  - Converted UCI target to binary:
    - `num == 0 -> 0`
    - `num > 0 -> 1`
  - Updated `load_dataset(path=None)` behavior:
    - If `path` provided: load local CSV
    - If `path` omitted: fetch from UCI (or cached CSV)

- `src/heart_disease_mlops/train.py`
  - `--input` changed from required to optional (`default=None`)
  - `train_model` now accepts `input_path: str | None`
  - Switched logistic regression solver to `liblinear` for better numerical stability

- `src/heart_disease_mlops/evaluate.py`
  - `--input` changed from required to optional (`default=None`)
  - `evaluate_model` now accepts `input_path: str | None`

- `Makefile`
  - `train` no longer requires `--input data/raw/heart.csv`
  - `evaluate` no longer requires `--input data/raw/heart.csv`

- `dvc.yaml`
  - Train stage no longer depends on `data/raw/heart.csv` as input
  - Train stage now outputs cached dataset `data/raw/heart.csv`
  - Evaluate stage keeps `data/raw/heart.csv` as dependency (via cache)

### 3) Verification run results
- UCI fetch successful:
  - Dataset ID: `45`
  - Samples: `303`
  - Features: `13`
  - Final training table shape: `(303, 14)` including `target`
  - Cache created: `data/raw/heart.csv`

- End-to-end train/evaluate successful:
  - Model artifact: `models/model.joblib`
  - Train metrics: `models/train_metrics.json`
  - Eval metrics: `models/eval_metrics.json`

- Latest observed metrics:
  - Accuracy: `0.8689`
  - Precision: `0.8125`
  - Recall: `0.9286`
  - F1: `0.8667`
  - ROC-AUC: `0.9513`

### 4) How to run now
```bash
make train
make evaluate
make test
```

Notes:
- `make train`/`make evaluate` fetch from UCI automatically if cache is missing.
- Once fetched, runs use local cache at `data/raw/heart.csv`.

## 2026-05-02 (Environment Decision Update)

### 5) Python runtime policy updated
- Runtime policy was explicitly set to Python `>=3.12` in `pyproject.toml`.
- This supersedes the temporary Python 3.9 compatibility direction.

### 6) Type-hint style restored to modern syntax
- Function signatures in the dataset/training/evaluation modules were restored to modern union syntax (`str | None`, `str | Path | None`).

## 2026-05-03

### 7) Container infrastructure upgrade
- Updated `Dockerfile` base image from `python:3.11-slim` to `python:3.12-slim`
  - Ensures compatibility with Python 3.12 runtime specification
  
- Enhanced `Makefile` with container CLI auto-detection:
  - Added `CONTAINER_CLI` variable with shell-based runtime detection: `$(shell if command -v podman ...)`
  - Allows transparent switching between Podman and Docker without user intervention
  - Added `container-build` and `container-run` primary targets (runtime-agnostic)
  - Maintained backward compatibility with `docker-build` and `docker-run` aliases
  - Added `make run` convenience alias for `make container-run`

- Updated `.github/workflows/ci.yml`:
  - Added Podman installation step for GitHub Actions runners
  - Added explicit Podman build verification: `CONTAINER_CLI=podman make docker-build`
  - Ensures pipeline supports both container runtimes natively

### 8) Test suite import path fix
- Issue: `make test` failed with `ModuleNotFoundError: No module named 'api'`
- Root cause: pytest only had `src/` in pythonpath; tests needed to import `api.app`

- Updated `pyproject.toml`:
  - Changed `[tool.pytest.ini_options] pythonpath` from `["src"]` to `["src", "."]`
  - Now supports both package imports and top-level module imports (integration tests)
  
- Validation: Tests now pass successfully; `6 passed in 1.00s`

### 9) API root endpoint and frontend implementation
- Added root endpoint `GET /` returning navigation JSON with links to health, predict, docs

- Implemented comprehensive web dashboard (`GET /ui`):
  - Single-page HTML application with 3 interactive panels:
    1. **Prediction Panel**: JSON textarea form for feature input + real-time predictions
    2. **MLruns Panel**: Displays recent training runs from local `mlruns/` directory with metrics
    3. **Prefect Panel**: Shows flow metadata and allows triggering new training runs
  - Embedded CSS styling and JavaScript fetch logic
  - No external dependencies; all frontend served inline

- Added MLruns discovery API (`GET /api/mlruns/runs`):
  - Scans local `mlruns/` directory tree for recent training runs
  - Returns up to 20 most recent runs with full metrics (accuracy, precision, recall, F1, ROC-AUC)
  - Includes run timestamps and model information

- Added Prefect orchestration APIs:
  - `GET /api/prefect/status`: Returns flow metadata and last train/eval metrics
  - `POST /api/prefect/run`: Executes Prefect flow subprocess and returns execution status
  - Subprocess-based execution with returncode tracking

- Updated `README.md`:
  - Added reference to frontend dashboard at `http://localhost:8000/ui`
  - Documented Podman usage with explicit `CONTAINER_CLI=podman` examples
  - Clarified container runtime flexibility

### 10) Validation results
- Container builds successfully with Python 3.12-slim
- All 6 smoke tests pass post-changes (no regressions)
- Frontend endpoint validation (all returning HTTP 200):
  - `GET /ui` → HTML dashboard response
  - `GET /api/mlruns/runs` → 13 runs discovered with full metrics
  - `GET /api/prefect/status` → Flow metadata with train/eval metrics
- API backwards-compatible: `/predict`, `/health`, `/model-info` unchanged
- Affected files:
  - `src/heart_disease_mlops/data.py`
  - `src/heart_disease_mlops/train.py`
  - `src/heart_disease_mlops/evaluate.py`

### 7) Current state summary
- Editable install now works in your current environment.
- Training and test commands continue to run with the UCI-integrated workflow.
- Changelog reflects the final decision to target a modern Python baseline.
