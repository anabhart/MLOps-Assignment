#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="heart-disease"
IMAGE_NAME="heart-disease-api:latest"
NAMESPACE="heart-disease"
LOCAL_PORT="8000"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Functions
log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
  if ! command -v "$1" &> /dev/null; then
    log_error "$1 is not installed. Please install it and try again."
    exit 1
  fi
}

# ==============================================================================
# PHASE 1: Prerequisites Check
# ==============================================================================

log_info "=========================================="
log_info "PHASE 1: Checking prerequisites"
log_info "=========================================="

check_command docker
check_command kubectl
check_command kind

log_success "All prerequisites found: docker, kubectl, kind"

# ==============================================================================
# PHASE 2: Build Docker Image
# ==============================================================================

log_info "=========================================="
log_info "PHASE 2: Building Docker image"
log_info "=========================================="

cd "$REPO_ROOT"
log_info "Building image: $IMAGE_NAME from $REPO_ROOT/Containerfile"
docker build -t "$IMAGE_NAME" -f Containerfile .
log_success "Docker image built successfully"

# ==============================================================================
# PHASE 3: Create Kind Cluster
# ==============================================================================

log_info "=========================================="
log_info "PHASE 3: Setting up Kind cluster"
log_info "=========================================="

if kind get clusters 2>/dev/null | grep -q "^$CLUSTER_NAME$"; then
  log_warning "Cluster '$CLUSTER_NAME' already exists. Skipping creation."
else
  log_info "Creating Kind cluster: $CLUSTER_NAME"
  kind create cluster --name "$CLUSTER_NAME"
  log_success "Kind cluster created"
fi

# ==============================================================================
# PHASE 4: Load Image into Cluster
# ==============================================================================

log_info "=========================================="
log_info "PHASE 4: Loading Docker image into cluster"
log_info "=========================================="

log_info "Loading image into $CLUSTER_NAME cluster"
kind load docker-image "$IMAGE_NAME" --name "$CLUSTER_NAME"
log_success "Image loaded into cluster"

# ==============================================================================
# PHASE 5: Deploy Kubernetes Manifests
# ==============================================================================

log_info "=========================================="
log_info "PHASE 5: Deploying Kubernetes manifests"
log_info "=========================================="

log_info "Applying namespace manifest"
kubectl apply -f "$SCRIPT_DIR/namespace.yaml"

log_info "Applying MLflow deployment manifest"
kubectl apply -f "$SCRIPT_DIR/mlflow-deployment.yaml"

log_info "Applying MLflow service manifest"
kubectl apply -f "$SCRIPT_DIR/mlflow-service.yaml"

log_info "Applying deployment manifest"
kubectl apply -f "$SCRIPT_DIR/deployment.yaml"

log_info "Applying service manifest"
kubectl apply -f "$SCRIPT_DIR/service.yaml"

log_info "Applying ingress manifest"
kubectl apply -f "$SCRIPT_DIR/ingress.yaml"

log_success "All manifests applied"

# ==============================================================================
# PHASE 6: Wait for Deployment Ready
# ==============================================================================

log_info "=========================================="
log_info "PHASE 6: Waiting for deployment to be ready"
log_info "=========================================="

log_info "Waiting for rollout of heart-disease-api deployment..."
kubectl -n "$NAMESPACE" rollout status deploy/heart-disease-api --timeout=5m
log_info "Waiting for rollout of heart-disease-mlflow deployment..."
kubectl -n "$NAMESPACE" rollout status deploy/heart-disease-mlflow --timeout=5m
log_success "Deployment is ready"

# ==============================================================================
# PHASE 7: Show Deployment Status
# ==============================================================================

log_info "=========================================="
log_info "PHASE 7: Deployment Status"
log_info "=========================================="

echo ""
log_info "Pods and Services:"
kubectl -n "$NAMESPACE" get pods,svc,ingress
echo ""

# ==============================================================================
# PHASE 8: Verify API Endpoint
# ==============================================================================

log_info "=========================================="
log_info "PHASE 8: Verifying API endpoints"
log_info "=========================================="

# Get service info
SERVICE_TYPE=$(kubectl -n "$NAMESPACE" get svc heart-disease-api -o jsonpath='{.spec.type}')

if [ "$SERVICE_TYPE" = "LoadBalancer" ]; then
  log_info "Service type is LoadBalancer. Waiting for external IP..."
  EXTERNAL_IP=$(kubectl -n "$NAMESPACE" get svc heart-disease-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
  
  if [ -z "$EXTERNAL_IP" ]; then
    log_warning "No external IP assigned (expected on local kind cluster)"
    log_info "Using local port-forward on localhost:$LOCAL_PORT"
    API_URL="localhost:$LOCAL_PORT"
  else
    API_URL="$EXTERNAL_IP"
  fi
else
  log_info "Service type: $SERVICE_TYPE. Using port-forward for access."
  API_URL="localhost:$LOCAL_PORT"
fi

# Set up port-forward in background for local testing and keep it running
if [ "$SERVICE_TYPE" = "LoadBalancer" ] || [ "$SERVICE_TYPE" = "ClusterIP" ]; then
  if pgrep -f "kubectl -n $NAMESPACE port-forward svc/heart-disease-api $LOCAL_PORT:80" >/dev/null 2>&1; then
    log_info "Port-forward already running on localhost:$LOCAL_PORT"
  else
    log_info "Starting persistent port-forward on localhost:$LOCAL_PORT"
    nohup kubectl -n "$NAMESPACE" port-forward svc/heart-disease-api "$LOCAL_PORT":80 >/tmp/heart-disease-port-forward.log 2>&1 &
  fi
  sleep 2
fi

log_info "Testing API endpoints at http://$API_URL"
echo ""

# Health check
log_info "Testing /health endpoint..."
if HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "http://$API_URL/health" 2>/dev/null); then
  if [ "$HEALTH_RESPONSE" = "200" ]; then
    log_success "/health returned HTTP $HEALTH_RESPONSE ✓"
  else
    log_warning "/health returned HTTP $HEALTH_RESPONSE"
  fi
else
  log_warning "Could not reach /health endpoint. Wait a moment and try manually:"
  log_warning "  curl http://$API_URL/health"
fi
echo ""

# Model info check
log_info "Testing /model-info endpoint..."
if MODEL_RESPONSE=$(curl -s "http://$API_URL/model-info" 2>/dev/null); then
  if echo "$MODEL_RESPONSE" | grep -q "model_name\|version"; then
    log_success "/model-info returned data ✓"
    echo "$MODEL_RESPONSE" | head -n 5
  else
    log_warning "Unexpected /model-info response"
  fi
else
  log_warning "Could not reach /model-info endpoint"
fi
echo ""

# ==============================================================================
# PHASE 9: Provide Access Instructions
# ==============================================================================

log_info "=========================================="
log_info "PHASE 9: Deployment Complete - Access Instructions"
log_info "=========================================="

echo ""
echo "✓ Kubernetes cluster '$CLUSTER_NAME' is running"
echo "✓ heart-disease-api is deployed in namespace '$NAMESPACE'"
echo ""
echo -e "${YELLOW}Quick Access:${NC}"
echo "  Namespace:  $NAMESPACE"
echo "  Deployment: heart-disease-api"
echo "  Service:    heart-disease-api (LoadBalancer)"
echo ""

echo -e "${YELLOW}API Base URL:${NC}"
echo "  http://localhost:$LOCAL_PORT"
echo ""

echo -e "${YELLOW}Available Endpoints:${NC}"
echo "  GET  http://localhost:$LOCAL_PORT/health         (Health check)"
echo "  GET  http://localhost:$LOCAL_PORT/model-info     (Model metadata)"
echo "  GET  http://localhost:$LOCAL_PORT/docs           (Swagger UI)"
echo "  POST http://localhost:$LOCAL_PORT/predict        (Make predictions)"
echo "  POST http://localhost:$LOCAL_PORT/retrain        (Trigger retraining)"
echo ""

echo -e "${YELLOW}Example Prediction Request:${NC}"
cat << 'EOF'
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
EOF
echo ""

echo -e "${YELLOW}Useful kubectl Commands:${NC}"
echo "  kubectl -n $NAMESPACE get pods              (Show pods)"
echo "  kubectl -n $NAMESPACE logs deploy/heart-disease-api     (Show logs)"
echo "  kubectl -n $NAMESPACE describe pod <pod-name>          (Pod details)"
echo "  kubectl -n $NAMESPACE port-forward svc/heart-disease-api $LOCAL_PORT:80  (Port forward)"
echo ""

echo -e "${YELLOW}Cleanup:${NC}"
echo "  kind delete cluster --name $CLUSTER_NAME"
echo ""

log_success "=========================================="
log_success "Deployment successful!"
log_success "=========================================="
