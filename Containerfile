# Multi-stage Containerfile for the heart-disease classifier API.
# Build:  podman build -t heart-disease-api -f Containerfile .
# Run:    podman run --rm -p 8000:8000 heart-disease-api

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system deps needed by scikit-learn / numpy wheels (slim image).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so they cache between code changes.
COPY requirements.txt pyproject.toml README.md ./
RUN pip install -r requirements.txt \
    && pip install "fastapi>=0.110" "uvicorn[standard]>=0.29" \
       "pydantic>=2.5" "prometheus-client>=0.20" "python-json-logger>=2.0"

# Copy source + API + pre-trained model artifacts.
COPY src ./src
COPY api ./api
COPY artifacts ./artifacts
COPY data ./data

# Install package itself so `import heart_disease_mlops` works without PYTHONPATH.
RUN pip install --no-deps -e .

# Pre-create writable directories that may be bind-mounted at runtime so
# the container still works when the host directories don't exist yet, and
# so `data/feedback/feedback.csv` can be appended to under any UID that
# has access to the volume.
RUN mkdir -p /app/data/feedback /app/artifacts/models /app/artifacts/reports \
    && chmod -R a+rwX /app/data /app/artifacts

# Non-root user for safety.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV HEART_DISEASE_MODEL_PATH=/app/artifacts/models/best_model.joblib

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
