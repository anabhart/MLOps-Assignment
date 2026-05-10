# Kubernetes deployment (local kind cluster)

These manifests deploy the heart-disease classifier API to a local Kubernetes
cluster. They have been validated against [kind](https://kind.sigs.k8s.io/),
but apply to any conformant cluster.

## Prerequisites
- A working container image: `podman build -t heart-disease-api:latest -f Containerfile .`
- `kubectl` and `kind` installed.
- (Optional) `cloud-provider-kind` for `LoadBalancer` services on kind, or use
  `kubectl port-forward` instead.

## Quickstart

```powershell
# 1. Create cluster
kind create cluster --name heart-disease

# 2. Load the locally-built image into the cluster
podman save heart-disease-api:latest -o heart-disease-api.tar
kind load image-archive heart-disease-api.tar --name heart-disease
Remove-Item heart-disease-api.tar

# 3. Apply manifests
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml

# 4. Watch rollout
kubectl -n heart-disease rollout status deploy/heart-disease-api
kubectl -n heart-disease get pods,svc

# 5. Access the API (port-forward when no LoadBalancer is available)
kubectl -n heart-disease port-forward svc/heart-disease-api 8080:80
# Then in another terminal:
curl http://localhost:8080/health
```

## Optional: Ingress
If you have nginx-ingress installed in the cluster:
```powershell
kubectl apply -f deploy/k8s/ingress.yaml
# Add `127.0.0.1 heart-disease.local` to your hosts file.
```

## Cleanup
```powershell
kubectl delete -f deploy/k8s/
kind delete cluster --name heart-disease
```
