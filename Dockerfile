# =============================================================================
# Aynux Multi-Stage Dockerfile
# Python 3.12 + UV + spaCy + FastAPI
# =============================================================================
# Build targets:
#   - development: Hot-reload for local development
#   - production:  Optimized, secure production image
#
# Usage:
#   docker build --target development -t aynux:dev .
#   docker build --target production -t aynux:prod .
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Base image with UV package manager
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # UV configuration
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install UV via pip (fallback when astral.sh is unavailable)
# Alternative: curl -LsSf https://astral.sh/uv/install.sh | sh
RUN pip install --no-cache-dir uv \
    && uv --version

# -----------------------------------------------------------------------------
# Stage 2: Builder - Install all dependencies
# -----------------------------------------------------------------------------
FROM base AS builder

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Create virtual environment and install production dependencies only
# --frozen ensures reproducible builds from uv.lock
# --no-install-project skips installing the project itself (done after copying code)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY app/ ./app/

# Install the project itself (this installs the app package)
RUN uv sync --frozen --no-dev

# Verify critical dependencies are installed
RUN uv run python -c "import fastapi; import langchain; import langgraph; print('Core dependencies OK')"

# Verify spaCy models are installed (downloaded from direct URLs in pyproject.toml)
RUN uv run python -c "import spacy; spacy.load('en_core_web_sm'); spacy.load('es_core_news_sm'); print('spaCy models OK')"

# -----------------------------------------------------------------------------
# Stage 3: Development image (with dev dependencies and hot-reload)
# -----------------------------------------------------------------------------
FROM base AS development

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install ALL dependencies including dev (for testing, linting, etc.)
RUN uv sync --frozen --no-install-project

# Copy application code (will be overwritten by volume mount in docker-compose)
COPY app/ ./app/

# Install the project
RUN uv sync --frozen

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Expose application port
EXPOSE 8080

# Development command with hot-reload
# Using uv run ensures we use the correct virtual environment
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload", "--reload-dir", "/app/app"]

# -----------------------------------------------------------------------------
# Stage 4: Production image (minimal, secure)
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS production

# Runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    DEBUG=false \
    # Add virtual environment to PATH
    PATH="/app/.venv/bin:$PATH"

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security (following Docker best practices)
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage (includes all dependencies)
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appgroup app/ ./app/

# Copy entrypoint script
COPY --chown=appuser:appgroup docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create directories for runtime
RUN mkdir -p /app/logs /app/data \
    && chown -R appuser:appgroup /app/logs /app/data

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8080

# Health check - verifies the application is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Entrypoint handles service checks and database initialization
ENTRYPOINT ["docker-entrypoint.sh"]

# Production command with multiple workers for better performance
# Workers = 2 * CPU cores + 1 is a common formula, but 4 is a safe default
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
