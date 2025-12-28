#!/bin/bash
# =============================================================================
# Aynux Docker Entrypoint Script
# Handles health checks, initialization, and graceful startup
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Wait for PostgreSQL to be ready
wait_for_postgres() {
    log_step "Waiting for PostgreSQL at ${DB_HOST:-localhost}:${DB_PORT:-5432}..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if python -c "
import sys
import psycopg2
try:
    conn = psycopg2.connect(
        host='${DB_HOST:-localhost}',
        port=${DB_PORT:-5432},
        dbname='${DB_NAME:-aynux}',
        user='${DB_USER:-postgres}',
        password='${DB_PASSWORD:-}',
        connect_timeout=5
    )
    conn.close()
    sys.exit(0)
except Exception as e:
    sys.exit(1)
" 2>/dev/null; then
            log_info "PostgreSQL is ready!"
            return 0
        fi
        log_warn "PostgreSQL not ready (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    log_error "PostgreSQL failed to become ready after $max_attempts attempts"
    return 1
}

# Wait for Redis to be ready
wait_for_redis() {
    log_step "Waiting for Redis at ${REDIS_HOST:-localhost}:${REDIS_PORT:-6379}..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if python -c "
import redis
import sys
try:
    r = redis.Redis(
        host='${REDIS_HOST:-localhost}',
        port=${REDIS_PORT:-6379},
        password='${REDIS_PASSWORD:-}' or None,
        socket_timeout=5
    )
    r.ping()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            log_info "Redis is ready!"
            return 0
        fi
        log_warn "Redis not ready (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    log_error "Redis failed to become ready after $max_attempts attempts"
    return 1
}

# Verify and enable pgvector extension
verify_pgvector() {
    log_step "Verifying pgvector extension..."
    python -c "
import psycopg2
conn = psycopg2.connect(
    host='${DB_HOST:-localhost}',
    port=${DB_PORT:-5432},
    dbname='${DB_NAME:-aynux}',
    user='${DB_USER:-postgres}',
    password='${DB_PASSWORD:-}'
)
cur = conn.cursor()
cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
conn.commit()
cur.execute(\"SELECT extversion FROM pg_extension WHERE extname = 'vector'\")
result = cur.fetchone()
if result:
    print(f'pgvector version: {result[0]}')
cur.close()
conn.close()
" && log_info "pgvector extension verified" || log_warn "Could not verify pgvector extension"
}

# Run Alembic database migrations
run_migrations() {
    log_step "Running database migrations..."

    # Run Alembic migrations (idempotent - safe to run multiple times)
    if alembic upgrade head; then
        log_info "Database migrations completed successfully"
    else
        log_error "Database migrations failed!"
        return 1
    fi
}

# Check Ollama connectivity (optional)
check_ollama() {
    if [ -n "${OLLAMA_API_URL:-}" ]; then
        log_step "Checking Ollama at ${OLLAMA_API_URL}..."
        if curl -sf "${OLLAMA_API_URL}/api/version" > /dev/null 2>&1; then
            log_info "Ollama is available"
        else
            log_warn "Ollama not available at ${OLLAMA_API_URL} - LLM features may not work"
        fi
    fi
}

# Main entrypoint
main() {
    echo ""
    echo "========================================"
    echo "  Aynux Application Startup"
    echo "========================================"
    echo ""
    log_info "Environment: ${ENVIRONMENT:-development}"
    log_info "Debug mode: ${DEBUG:-false}"
    echo ""

    # Wait for required services
    wait_for_postgres || exit 1
    wait_for_redis || exit 1

    # Database migrations (can be skipped with SKIP_DB_INIT=true)
    if [ "${SKIP_DB_INIT:-false}" != "true" ]; then
        verify_pgvector
        run_migrations
    else
        log_warn "Skipping database migrations (SKIP_DB_INIT=true)"
    fi

    # Optional: Check Ollama
    check_ollama

    echo ""
    log_info "All checks passed. Starting application server..."
    echo ""

    # Execute the main command
    exec "$@"
}

main "$@"
