# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install system dependencies (pg_dump for backup, Calibre for MOBI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with home directory for uv cache
RUN groupadd -r bookcompanion && useradd -r -g bookcompanion -m bookcompanion

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies
COPY backend/pyproject.toml backend/uv.lock* ./backend/
WORKDIR /app/backend
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Copy backend source
COPY backend/ ./

# Copy built frontend to static directory
COPY --from=frontend-build /app/frontend/dist ./static/

# Copy alembic config
COPY backend/alembic.ini ./
COPY backend/alembic/ ./alembic/

# Create dirs for backups and config, set ownership
RUN mkdir -p /app/backups /app/config && chown -R bookcompanion:bookcompanion /app

USER bookcompanion

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Run migrations then start server
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.api.main:app --host 0.0.0.0 --port 8000"]
