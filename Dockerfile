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

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

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

EXPOSE 8000

# Run migrations then start server
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.api.main:app --host 0.0.0.0 --port 8000"]
