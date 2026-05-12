#!/bin/bash

set -euo pipefail

CLUSTER_NAME="heart-disease"
NAMESPACE="heart-disease"
LOCAL_API_PORT="8000"
LOCAL_MLFLOW_PORT="5000"
INVOKING_USER="${SUDO_USER:-$USER}"
INVOKING_HOME="$(eval echo ~${SUDO_USER:-$USER})"
PF_LOG="/tmp/heart-disease-port-forward-${INVOKING_USER}-$(date +%s).log"
MLFLOW_PF_LOG="/tmp/heart-disease-mlflow-port-forward-${INVOKING_USER}-$(date +%s).log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

info() {
  echo "[INFO] $1"
}

success() {
  echo "[SUCCESS] $1"
}

warn() {
  echo "[WARNING] $1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Missing command: $1"
    exit 1
  fi
}

require_cmd sudo
require_cmd kubectl
require_cmd kind
require_cmd curl

cd "$REPO_ROOT"

info "Deploying Kubernetes workload (cluster + manifests)..."
if [ "$(id -u)" -eq 0 ]; then
  ./deploy/k8s/deploy.sh
else
  sudo ./deploy/k8s/deploy.sh
fi

info "Restoring kubeconfig for user '${INVOKING_USER}' after deployment..."
if [ "$(id -u)" -eq 0 ]; then
  mkdir -p "${INVOKING_HOME}/.kube"
  kind get kubeconfig --name "$CLUSTER_NAME" > "${INVOKING_HOME}/.kube/config"
  chown -R "${INVOKING_USER}:${INVOKING_USER}" "${INVOKING_HOME}/.kube"
else
  sudo sh -c "mkdir -p '${INVOKING_HOME}/.kube' && kind get kubeconfig --name '$CLUSTER_NAME' > '${INVOKING_HOME}/.kube/config' && chown -R '${INVOKING_USER}:${INVOKING_USER}' '${INVOKING_HOME}/.kube'"
fi

info "Ensuring kubectl context points to kind cluster..."
kubectl config use-context "kind-$CLUSTER_NAME" >/dev/null

info "Starting persistent port-forward on localhost:${LOCAL_API_PORT}..."
pkill -f "kubectl -n ${NAMESPACE} port-forward svc/heart-disease-api ${LOCAL_API_PORT}:80" >/dev/null 2>&1 || true
nohup kubectl -n "$NAMESPACE" port-forward svc/heart-disease-api "${LOCAL_API_PORT}:80" >"${PF_LOG}" 2>&1 &

sleep 2

info "Starting persistent MLflow port-forward on localhost:${LOCAL_MLFLOW_PORT}..."
pkill -f "kubectl -n ${NAMESPACE} port-forward svc/heart-disease-mlflow ${LOCAL_MLFLOW_PORT}:5000" >/dev/null 2>&1 || true
nohup kubectl -n "$NAMESPACE" port-forward svc/heart-disease-mlflow "${LOCAL_MLFLOW_PORT}:5000" >"${MLFLOW_PF_LOG}" 2>&1 &

info "Verifying endpoints (with startup retries)..."

API_CODE="000"
for _ in $(seq 1 15); do
  API_CODE=$(curl --max-time 5 -s -o /dev/null -w "%{http_code}" "http://localhost:${LOCAL_API_PORT}/health" || true)
  if [ "$API_CODE" = "200" ]; then
    break
  fi
  sleep 2
done

MLFLOW_CODE="000"
for _ in $(seq 1 20); do
  MLFLOW_CODE=$(curl --max-time 5 -s -o /dev/null -w "%{http_code}" "http://localhost:${LOCAL_MLFLOW_PORT}/" || true)
  if [ "$MLFLOW_CODE" = "200" ]; then
    break
  fi
  sleep 2
done

if [ "$API_CODE" != "200" ]; then
  warn "API health check returned HTTP ${API_CODE}"
else
  success "API is reachable at http://localhost:${LOCAL_API_PORT}"
fi

if [ "$MLFLOW_CODE" != "200" ]; then
  warn "MLflow UI check returned HTTP ${MLFLOW_CODE}"
else
  success "MLflow UI is reachable at http://localhost:${LOCAL_MLFLOW_PORT}"
fi

echo
echo "Endpoints:"
echo "  API:    http://localhost:${LOCAL_API_PORT}"
echo "  Docs:   http://localhost:${LOCAL_API_PORT}/docs"
echo "  MLflow: http://localhost:${LOCAL_MLFLOW_PORT}"
echo "  API port-forward log: ${PF_LOG}"
echo "  MLflow port-forward log: ${MLFLOW_PF_LOG}"
