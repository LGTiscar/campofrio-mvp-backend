# Multi-stage Dockerfile
# Builder: export requirements from pyproject (uv) and build wheelhouse
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates git && rm -rf /var/lib/apt/lists/*

# Copy lockfiles to leverage docker cache
COPY pyproject.toml uv.lock* /app/

# Install uv and pip tools, export requirements and build wheels
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir uv && \
    uv export --no-dev > requirements.txt && \
    mkdir /wheels && \
    pip wheel --wheel-dir=/wheels -r requirements.txt

# Copy application code (in case building your package is needed)
COPY . /app

# Runtime: small image with only wheels installed
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*

# Copy wheels and requirements from builder
COPY --from=builder /wheels /wheels
COPY --from=builder /app/requirements.txt /app/requirements.txt

# Copy source
COPY --from=builder /app /app

# Install from local wheelhouse (no network)
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/wheels -r /app/requirements.txt && \
    pip install --no-cache-dir gunicorn uvicorn

# Create non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8000

EXPOSE 8000

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000", "--workers", "2"]
