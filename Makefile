# Heart Disease MLOps — Makefile
# Works with GNU make (Git Bash, WSL) and `make` shipped with most CI runners.
# On Windows PowerShell run targets directly, e.g. `make install` from
# Git Bash, or invoke the underlying commands as documented in README.md.

PYTHON ?= python
PIP ?= pip
IMAGE ?= heart-disease-api
TAG ?= latest
PORT ?= 8000
KIND_CLUSTER ?= heart-disease

.DEFAULT_GOAL := help

.PHONY: help install install-dev lint format test test-fast train train-fast \
        clean api ui notebook prefect drift docker-build docker-run docker-stop \
        kind-up kind-load kind-deploy kind-down k8s-apply k8s-delete \
        report-pdf all ci

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

## ---------- Setup ----------
install: ## Install runtime + dev + api dependencies
	$(PIP) install -r requirements.txt
	$(PIP) install -e ".[dev,api]"

install-dev: install ## Alias for install (kept for compatibility)

## ---------- Quality ----------
lint: ## Run ruff
	ruff check src tests api

format: ## Auto-fix lint issues
	ruff check --fix src tests api
	ruff format src tests api

test: ## Run full pytest suite
	pytest --cov=heart_disease_mlops --cov-report=term-missing

test-fast: ## Run quick tests only (skip slow markers)
	pytest -m "not slow"

## ---------- ML pipeline ----------
train: ## Full training run (writes artifacts/, mlruns/)
	$(PYTHON) -m heart_disease_mlops

train-fast: ## Reduced-grid training run (used by CI)
	HEART_DISEASE_FAST_TRAIN=1 $(PYTHON) -m heart_disease_mlops

prefect: ## Run the Prefect orchestration flow
	$(PYTHON) pipelines/prefect_flow.py

drift: ## Generate Evidently drift report
	$(PYTHON) monitoring/drift_detection.py

notebook: ## Launch JupyterLab in the notebooks folder
	jupyter lab --notebook-dir=notebooks

## ---------- Serving ----------
api: ## Run the FastAPI app with uvicorn (auto-reload)
	uvicorn api.app:app --host 0.0.0.0 --port $(PORT) --reload

ui: ## Open the prediction UI in the default browser (api must be running)
	@$(PYTHON) -c "import webbrowser; webbrowser.open('http://localhost:$(PORT)/ui')"

## ---------- Container (podman or docker) ----------
RUNTIME ?= $(shell command -v podman >/dev/null 2>&1 && echo podman || echo docker)

docker-build: ## Build the OCI image with $(RUNTIME)
	$(RUNTIME) build -t $(IMAGE):$(TAG) -f Containerfile .

docker-run: ## Run the container, mapping $(PORT)
	$(RUNTIME) run --rm -d --name heart-disease-api -p $(PORT):8000 \
		-v "$$(pwd)/data/feedback:/app/data/feedback:Z" \
		-v "$$(pwd)/artifacts:/app/artifacts:Z" \
		$(IMAGE):$(TAG)

docker-stop: ## Stop the running container
	-$(RUNTIME) rm -f heart-disease-api

## ---------- Kubernetes (kind) ----------
kind-up: ## Create a local kind cluster
	kind create cluster --name $(KIND_CLUSTER)

kind-load: docker-build ## Load the local image into the kind cluster
	$(RUNTIME) save $(IMAGE):$(TAG) -o $(IMAGE).tar
	kind load image-archive $(IMAGE).tar --name $(KIND_CLUSTER)
	rm $(IMAGE).tar

k8s-apply: ## Apply all Kubernetes manifests
	kubectl apply -f deploy/k8s/namespace.yaml
	kubectl apply -f deploy/k8s/deployment.yaml
	kubectl apply -f deploy/k8s/service.yaml

k8s-delete: ## Delete all Kubernetes resources
	-kubectl delete -f deploy/k8s/

kind-deploy: kind-load k8s-apply ## Build, load, and deploy in one step
	kubectl -n heart-disease rollout status deploy/heart-disease-api

kind-down: ## Delete the kind cluster
	kind delete cluster --name $(KIND_CLUSTER)

## ---------- Reporting ----------
report-pdf: ## Convert reports/FINAL_REPORT.md to docx + pdf via pandoc
	pandoc reports/FINAL_REPORT.md -o reports/FINAL_REPORT.docx
	-pandoc reports/FINAL_REPORT.md -o reports/FINAL_REPORT.pdf

## ---------- Cleanup ----------
clean: ## Remove generated caches and artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov
	rm -rf artifacts/*
	find . -type d -name __pycache__ -exec rm -rf {} +

## ---------- Bundles ----------
ci: lint test train-fast ## What CI runs
all: install lint test train docker-build ## Full local pipeline
