#!/bin/bash

set -euo pipefail

CLUSTER_NAME="heart-disease"
NAMESPACE="heart-disease"
LOCAL_API_PORT="8000"
LOCAL_MLFLOW_PORT="5000"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

info() {
  echo "[INFO] $1"
}

success() {
  echo "[SUCCESS] $1"
}

cd "$REPO_ROOT"

info "Stopping local API port-forward on localhost:${LOCAL_API_PORT} (if running)..."
pkill -f "kubectl -n ${NAMESPACE} port-forward svc/heart-disease-api ${LOCAL_API_PORT}:80" >/dev/null 2>&1 || true

info "Stopping local MLflow port-forward on localhost:${LOCAL_MLFLOW_PORT} (if running)..."
pkill -f "kubectl -n ${NAMESPACE} port-forward svc/heart-disease-mlflow ${LOCAL_MLFLOW_PORT}:5000" >/dev/null 2>&1 || true

info "Stopping Prometheus and Grafana containers started for monitoring (if running)..."
if [ "$(id -u)" -eq 0 ]; then
  docker compose -f compose.yaml rm -sf prometheus grafana >/dev/null 2>&1 || true
else
  sudo docker compose -f compose.yaml rm -sf prometheus grafana >/dev/null 2>&1 || true
fi

info "Deleting Kind cluster '${CLUSTER_NAME}' (if it exists)..."
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  kind delete cluster --name "$CLUSTER_NAME"
fi

success "Cleanup complete."
echo "Stopped: K8s cluster, API/MLflow port-forwards, Prometheus, and Grafana."
