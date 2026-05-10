# Architecture

## High-level diagram

```mermaid
flowchart LR
    subgraph Source["Data Source"]
        UCI[(UCI Heart Disease<br/>Cleveland subset)]
    end

    subgraph Pipeline["ML Pipeline (heart_disease_mlops)"]
        Ingest[ingest<br/>data.py]
        Validate[validate<br/>validation.py]
        Preprocess[preprocess<br/>preprocessing.py]
        Train[train + tune<br/>train.py]
        Eval[evaluate<br/>evaluate.py]
    end

    subgraph Tracking["Experiment Tracking"]
        MLflow[(MLflow runs +<br/>model registry)]
    end

    subgraph Orchestrator["Orchestration"]
        Prefect[Prefect flow<br/>pipelines/prefect_flow.py]
    end

    subgraph Serving["Serving"]
        Model[(best_model.joblib)]
        API[FastAPI app<br/>api/app.py]
        Container[Podman / OCI image]
        K8s[Kubernetes Deployment<br/>+ Service]
    end

    subgraph Observability["Observability"]
        Logs[JSON logs<br/>stdout]
        Prom[Prometheus<br/>/metrics]
        Drift[Evidently drift report]
    end

    subgraph CI["CI/CD"]
        GH[GitHub Actions<br/>lint → test → train-smoke → container]
    end

    UCI --> Ingest --> Validate --> Preprocess --> Train --> Eval
    Train --> Model
    Train --> MLflow
    Prefect --> Ingest
    Prefect --> Train
    Model --> API
    API --> Container --> K8s
    API --> Logs
    API --> Prom
    Pipeline --> Drift
    GH --> Container
    GH --> MLflow
```

## Component summary

| Layer | Component | Path |
|-------|-----------|------|
| Data | UCI Cleveland CSV | `data/heart+disease/processed.cleveland.data` |
| Pipeline | `config`, `data`, `validation`, `preprocessing`, `train`, `evaluate` | `src/heart_disease_mlops/` |
| Notebooks | EDA + training analysis | `notebooks/` |
| Tracking | MLflow file store + model registry | `mlruns/` |
| Orchestration | Prefect 2 flow + weekly schedule | `pipelines/prefect_flow.py` |
| Serving | FastAPI + Pydantic + Prometheus | `api/app.py` |
| Container | Podman/Docker image | `Containerfile` |
| Deployment | Kubernetes manifests | `deploy/k8s/` |
| Monitoring | JSON logs, `/metrics`, Evidently drift | `api/`, `monitoring/` |
| Tests | pytest unit + API + smoke | `tests/` |
| CI | GitHub Actions (lint/test/train/container) | `.github/workflows/ci.yml` |

## Request path

```mermaid
sequenceDiagram
    participant Client
    participant Ingress as K8s Service
    participant API as FastAPI Pod
    participant Model as best_model.joblib
    participant Prom as Prometheus

    Client->>Ingress: POST /predict {patient JSON}
    Ingress->>API: forward
    API->>API: Pydantic validation
    API->>Model: predict_proba(row)
    Model-->>API: probability
    API->>Prom: increment counters / observe latency
    API-->>Client: {prediction, label, probability}
```
