# Retraining Runbook

## When to retrain

Trigger a retraining run when **any** of the following conditions is met:

| # | Condition | Detection | Severity |
|---|-----------|-----------|----------|
| 1 | Drift share > 30% of features | `monitoring/drift_detection.py` exits non-zero | High |
| 2 | Test ROC-AUC drops > 5% vs. last accepted model | Compare `artifacts/reports/training_summary.json` runs | High |
| 3 | API `predict_requests_total{status="error"}` > 1% sustained for 30 min | Prometheus alert | Medium |
| 4 | New labelled batch available (>= 50 rows) | Manual / data-ops handoff | Medium |
| 5 | Quarterly cadence (every 90 days) | Scheduled Prefect run | Low |

## Procedure

1. **Capture state.** Note current image tag, MLflow run id of the production model, and Grafana dashboard screenshot.
2. **Reproduce locally.**
   ```powershell
   git pull
   python -m venv .venv ; .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt -e ".[dev,api]"
   python -m heart_disease_mlops
   ```
3. **Validate the new model.**
   - `pytest -k "not slow"` must pass.
   - Inspect `artifacts/reports/training_summary.json`. Reject if ROC-AUC < previous model − 1%.
4. **Build & smoke-test the container.**
   ```powershell
   podman build -t heart-disease-api:candidate -f Containerfile .
   podman run --rm -d -p 8001:8000 --name candidate heart-disease-api:candidate
   curl http://localhost:8001/health
   curl -X POST http://localhost:8001/predict -H 'Content-Type: application/json' -d '@api/example_requests.json'
   podman rm -f candidate
   ```
5. **Promote in MLflow.** The training pipeline auto-registers under
   `heart-disease-classifier`. Transition the new version to `Production`
   in the MLflow UI and the previous version to `Archived`.
6. **Roll out.**
   ```powershell
   podman tag heart-disease-api:candidate heart-disease-api:latest
   kubectl -n heart-disease rollout restart deploy/heart-disease-api
   kubectl -n heart-disease rollout status deploy/heart-disease-api
   ```
7. **Verify.** Hit `/health`, `/model-info`, and `/predict` against the live
   endpoint. Confirm `model-info.best_model` reflects the new training
   timestamp.

## Rollback

If `/health` fails or error rate spikes within 15 minutes:

```powershell
kubectl -n heart-disease rollout undo deploy/heart-disease-api
kubectl -n heart-disease rollout status deploy/heart-disease-api
```

Then re-tag the previous image as `heart-disease-api:latest` and revert the
MLflow registry stage (`Production` ← previous version).

## Audit trail

For every retrain, archive the following under `reports/retraining/<date>/`:
- `training_summary.json`
- `drift_report.html` / `.json`
- `kubectl rollout history` output
- Screenshot of the MLflow run + registry promotion
