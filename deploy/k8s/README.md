# Kubernetes Deployment Guide (Production Requirement)

This folder satisfies requirement 7 using Kubernetes manifests:

- Deployment: [deployment.yaml](deployment.yaml)
- Service (LoadBalancer): [service.yaml](service.yaml)
- Ingress: [ingress.yaml](ingress.yaml)
- Namespace: [namespace.yaml](namespace.yaml)
- MLflow Deployment: [mlflow-deployment.yaml](mlflow-deployment.yaml)
- MLflow Service: [mlflow-service.yaml](mlflow-service.yaml)
- **Deployment Script: [deploy.sh](deploy.sh)** ⭐ Use this for automated deployment
- **Helper Bring-Up Script: [bringup.sh](bringup.sh)** ⭐ Brings up K8s + MLflow + Prometheus + Grafana
- **Helper Bring-Down Script: [bringdown.sh](bringdown.sh)** ⭐ Cleans up K8s + MLflow + Prometheus + Grafana

You can deploy on local Kubernetes (kind/minikube/Docker Desktop) or managed
cloud Kubernetes (GKE/EKS/AKS).

## Recommended Ubuntu flow

If you want the exact local browser endpoints below after setup, follow this sequence from a clean Ubuntu machine:

- http://localhost:8000/
- http://127.0.0.1:5000/
- http://localhost:8000/metrics
- http://localhost:3000/d/heart-disease-api-monitoring/heart-disease-api-monitoring?orgId=1&refresh=10s

### 0. Install prerequisites

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git python3 python3-venv python3-pip

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"

curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl

curl -Lo ./kind "https://kind.sigs.k8s.io/dl/v0.24.0/kind-linux-amd64"
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

newgrp docker
docker --version
kubectl version --client
kind --version
```

### 1. Clone the repository

```bash
git clone https://github.com/anabhart/MLOps-Assignment.git
cd MLOps-Assignment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev,api]"
```

### 2. Bring everything up

```bash
./deploy/k8s/bringup.sh
```

This script now performs the full local demo flow in order:

1. Builds the Docker image.
2. Creates or reuses the `kind` cluster.
3. Deploys the API and MLflow manifests.
4. Waits for both deployments to report ready.
5. Port-forwards the API to `localhost:8000`.
6. Port-forwards MLflow to `127.0.0.1:5000`.
7. Starts Prometheus on `localhost:9090`.
8. Starts Grafana on `localhost:3000`.
9. Verifies `/health`, `/metrics`, Prometheus, and Grafana.

### 3. Open the working endpoints

```text
http://localhost:8000/
http://localhost:8000/docs
http://127.0.0.1:5000/
http://localhost:8000/metrics
http://localhost:3000/d/heart-disease-api-monitoring/heart-disease-api-monitoring?orgId=1&refresh=10s
```

Grafana login: `admin` / `admin`

### 4. Confirm the cluster and services are healthy

```bash
kubectl -n heart-disease get pods,svc,ingress
curl http://localhost:8000/health
curl http://localhost:8000/model-info
curl http://localhost:8000/metrics | head
curl http://127.0.0.1:5000/
curl http://localhost:9090/-/ready
curl http://localhost:3000/api/health
```

### 5. Bring everything down

```bash
./deploy/k8s/bringdown.sh
```

This stops API and MLflow port-forwards, removes Prometheus and Grafana, and deletes the local `kind` cluster.

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
# Bring up cluster + API + MLflow UI + Prometheus + Grafana
./deploy/k8s/bringup.sh

# Bring everything down and cleanup
./deploy/k8s/bringdown.sh
```

`bringup.sh` does all of the following:
1. Runs Kubernetes deployment via `deploy.sh`.
2. Restores kubeconfig for your user (fixes kubectl context after sudo runs).
3. Starts persistent port-forward for API on `localhost:8000`.
4. Starts persistent port-forward for MLflow on `localhost:5000`.
5. Starts Prometheus on `localhost:9090`.
6. Starts Grafana on `localhost:3000`.
7. Verifies API, MLflow, Prometheus, Grafana, and `/metrics`.

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
kubectl apply -f deploy/k8s/mlflow-deployment.yaml
kubectl apply -f deploy/k8s/mlflow-service.yaml
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml
kubectl apply -f deploy/k8s/ingress.yaml

# Wait for rollout
kubectl -n heart-disease rollout status deploy/heart-disease-api
kubectl -n heart-disease rollout status deploy/heart-disease-mlflow
kubectl -n heart-disease get pods,svc,ingress
```

If your local cluster does not provide external LoadBalancer IPs, use:

```bash
kubectl -n heart-disease port-forward svc/heart-disease-api 8000:80
kubectl -n heart-disease port-forward svc/heart-disease-mlflow 5000:5000
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
curl http://localhost:8000/health

# Model info
curl http://localhost:8000/model-info

# MLflow UI
curl http://localhost:5000/

# Predict
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
```

## 3. Required Screenshots for Submission

Capture and attach these screenshots in report:

1. `kubectl -n heart-disease get pods,svc,ingress` showing running resources.
2. Browser/API client showing `/health` returning success.
3. Browser/API client showing `/predict` response payload.
4. Optional but strong evidence: `/docs` reachable through LB or Ingress.

## 4. Cleanup

```bash
./deploy/k8s/bringdown.sh
```
