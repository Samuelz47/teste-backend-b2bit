# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.2 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false

# Install Poetry
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

WORKDIR /app

# Copy only dependency files first (cache-friendly layer)
COPY pyproject.toml poetry.lock* ./

# Install runtime dependencies only (no dev)
RUN poetry install --only main --no-interaction --no-ansi

# ── Stage 2: runtime ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project source
COPY . .

EXPOSE 8000

# Run with gunicorn in production; override in docker-compose for dev
CMD ["gunicorn", "cinereserve.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
