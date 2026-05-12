# Kubernetes Deployment Guide (Production Requirement)

This folder satisfies requirement 7 using Kubernetes manifests:

- Deployment: [deployment.yaml](deployment.yaml)
- Service (LoadBalancer): [service.yaml](service.yaml)
- Ingress: [ingress.yaml](ingress.yaml)
- Namespace: [namespace.yaml](namespace.yaml)
- MLflow Deployment: [mlflow-deployment.yaml](mlflow-deployment.yaml)
- MLflow Service: [mlflow-service.yaml](mlflow-service.yaml)
- **Deployment Script: [deploy.sh](deploy.sh)** ⭐ Use this for automated deployment
- **Helper Bring-Up Script: [bringup.sh](bringup.sh)** ⭐ Brings up K8s + MLflow UI
- **Helper Bring-Down Script: [bringdown.sh](bringdown.sh)** ⭐ Cleans up K8s + MLflow UI

You can deploy on local Kubernetes (kind/minikube/Docker Desktop) or managed
cloud Kubernetes (GKE/EKS/AKS).

## Quick Start (Automated)

The `deploy.sh` script automates all deployment steps:

```bash
# From repository root
./deploy/k8s/deploy.sh
```

This single command will:
1. ✓ Check prerequisites (docker, kubectl, kind)
2. ✓ Build the Docker image
3. ✓ Create Kind cluster
4. ✓ Load image into cluster
5. ✓ Deploy all Kubernetes manifests
6. ✓ Wait for deployment readiness
7. ✓ Verify API endpoints
8. ✓ Provide access instructions

**Requirements:** Docker, kubectl, and kind installed on your system.

## Quick Start (Helper Scripts)

Use these two commands for daily workflow:

```bash
# Bring up cluster + API + MLflow UI
./deploy/k8s/bringup.sh

# Bring everything down and cleanup
./deploy/k8s/bringdown.sh
```

`bringup.sh` does all of the following:
1. Runs Kubernetes deployment via `deploy.sh`.
2. Restores kubeconfig for your user (fixes kubectl context after sudo runs).
3. Starts persistent port-forward for API on `localhost:8000`.
4. Starts persistent port-forward for MLflow on `localhost:5000`.
5. Verifies both API and MLflow health endpoints.

### 1.1 Build the API image

```bash
docker build -t heart-disease-api:latest -f Containerfile .
```

### 1.2 Local Kubernetes path (kind)

```bash
# Create cluster
kind create cluster --name heart-disease

# Load local image into cluster
kind load docker-image heart-disease-api:latest --name heart-disease

# Deploy manifests
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml

# Wait for rollout
kubectl -n heart-disease rollout status deploy/heart-disease-api
kubectl -n heart-disease get pods,svc
```

If your local cluster does not provide external LoadBalancer IPs, use:

```bash
kubectl -n heart-disease port-forward svc/heart-disease-api 8080:80
```

### 1.3 Ingress exposure path

Apply ingress only if an ingress controller is installed:

```bash
kubectl apply -f deploy/k8s/ingress.yaml
kubectl -n heart-disease get ingress
```

For local testing, add this to hosts file:

```text
127.0.0.1 heart-disease.local
```

Then call the API through ingress:

```bash
curl http://heart-disease.local/health
```

### 1.4 Managed cloud path (GKE/EKS/AKS)

Push the image to a registry and update [deployment.yaml](deployment.yaml) image
value before applying manifests.

Example image format:

```text
<registry>/<project>/heart-disease-api:<tag>
```

After apply:

```bash
kubectl -n heart-disease get svc heart-disease-api
kubectl -n heart-disease get ingress
```

Use the external IP/hostname in endpoint checks below.

## 2. Endpoint Verification Commands

Use either LoadBalancer URL, ingress host, or port-forward URL.

```bash
# Health
curl http://localhost:8080/health

# Model info
curl http://localhost:8080/model-info

# Predict
curl -X POST http://localhost:8080/predict \
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
```

## 3. Required Screenshots for Submission

Capture and attach these screenshots in report:

1. `kubectl -n heart-disease get pods,svc,ingress` showing running resources.
2. Browser/API client showing `/health` returning success.
3. Browser/API client showing `/predict` response payload.
4. Optional but strong evidence: `/docs` reachable through LB or Ingress.

## 4. Cleanup

```bash
kubectl delete -f deploy/k8s/
kind delete cluster --name heart-disease
```
