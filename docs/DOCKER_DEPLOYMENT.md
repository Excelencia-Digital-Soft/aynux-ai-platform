# Docker Deployment Guide

Complete guide for setting up, developing, and deploying Aynux using Docker on macOS and Linux.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start (5 minutes)](#quick-start-5-minutes)
4. [Development Environment](#development-environment)
5. [Production Deployment](#production-deployment)
6. [Testing with Docker](#testing-with-docker)
7. [Troubleshooting](#troubleshooting)
8. [Command Reference](#command-reference)
9. [Maintenance & Operations](#maintenance--operations)

---

## Architecture Overview

### Service Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      Docker Network (aynux-network)             │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   PostgreSQL    │  │      Redis      │  │     Ollama      │ │
│  │   + pgvector    │  │    7-alpine     │  │  (optional)     │ │
│  │     :5432       │  │     :6379       │  │    :11434       │ │
│  │                 │  │                 │  │   CPU mode      │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                     │         │
│           └────────────────────┼─────────────────────┘         │
│                                │                               │
│                       ┌────────┴────────┐                      │
│                       │    FastAPI      │                      │
│                       │    App :8001    │                      │
│                       │   (aynux-app)   │                      │
│                       └────────┬────────┘                      │
│                                │                               │
└────────────────────────────────┼───────────────────────────────┘
                                 │
            host.docker.internal │ (macOS/Windows only)
                                 ▼
                        ┌─────────────────┐
                        │     Ollama      │  ← Native on Mac
                        │  GPU Accelerated│     (recommended)
                        │     :11434      │
                        └─────────────────┘
```

### Services Description

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **postgres** | `pgvector/pgvector:pg16` | 5432 | Database with vector similarity search |
| **redis** | `redis:7-alpine` | 6379 | Caching, session storage, rate limiting |
| **ollama** | `ollama/ollama:latest` | 11434 | LLM inference (CPU mode in Docker) |
| **app** | `aynux-app:dev` | 8001 | FastAPI application with LangGraph |
| **admin** | (same as app) | 8501 | Unified Streamlit Admin Dashboard |

### Apple Silicon vs Linux Considerations

| Aspect | macOS (Apple Silicon) | Linux (x86/ARM) |
|--------|----------------------|-----------------|
| **Ollama** | Run natively for GPU acceleration | Can run in Docker with GPU passthrough |
| **GPU Support** | Docker Desktop cannot pass GPU | Supported with NVIDIA Container Toolkit |
| **host.docker.internal** | Available by default | Requires `extra_hosts` configuration |
| **Performance** | Near-native with Rosetta | Native performance |

> **Important**: On Apple Silicon (M1/M2/M3/M4), Docker Desktop **cannot** pass GPU to containers. For best performance, run Ollama natively on the host and use `host.docker.internal:11434` to connect.

---

## Prerequisites

### macOS

```bash
# 1. Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install Docker Desktop
brew install --cask docker

# 3. Install Ollama (native - recommended for Apple Silicon)
brew install ollama

# 4. Start Ollama and pull required models
ollama serve  # In a separate terminal, or run as background service
ollama pull deepseek-r1:7b
ollama pull nomic-embed-text

# 5. Verify installations
docker --version    # Docker version 27.x+
docker compose version  # Docker Compose version v2.x+
ollama --version    # ollama version 0.x+
```

### Linux (Ubuntu/Debian)

```bash
# 1. Install Docker Engine
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# 2. Install Docker Compose V2 (included with Docker Engine)
docker compose version  # Should show v2.x+

# 3. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 4. Start Ollama and pull models
sudo systemctl enable ollama
sudo systemctl start ollama
ollama pull deepseek-r1:7b
ollama pull nomic-embed-text

# 5. Verify installations
docker --version
docker compose version
ollama --version
```

### Linux with NVIDIA GPU (Optional)

```bash
# Install NVIDIA Container Toolkit for GPU support
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Verify GPU access in Docker
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

---

## Quick Start (5 minutes)

### Step 1: Clone and Configure

```bash
# Clone the repository
git clone https://github.com/your-org/aynux.git
cd aynux

# Create environment file
cp .env.example .env

# Edit .env with your configuration (minimum required):
# DB_USER=aynux
# DB_PASSWORD=aynux_dev
# DB_NAME=aynux
```

### Step 2: Build the Application

```bash
# Build the development image
docker build --target development -t aynux-app:dev .

# Verify the image was created
docker images | grep aynux-app
```

### Step 3: Start Services

```bash
# Start all services (PostgreSQL, Redis, App)
docker compose up -d

# Check service status
docker compose ps
```

### Step 4: Verify Everything Works

```bash
# Check all containers are healthy
docker compose ps

# Expected output:
# NAME             IMAGE                    STATUS                   PORTS
# aynux-app        aynux-app:dev            Up X minutes (healthy)   0.0.0.0:8001->8001/tcp
# aynux-postgres   pgvector/pgvector:pg16   Up X minutes (healthy)   0.0.0.0:5432->5432/tcp
# aynux-redis      redis:7-alpine           Up X minutes (healthy)   0.0.0.0:6379->6379/tcp

# Test the health endpoint
curl http://localhost:8001/health
# {"status":"ok","environment":"development"}

# Test pgvector extension
docker compose exec postgres psql -U aynux -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
# extversion: 0.8.1

# Test Redis
docker compose exec redis redis-cli ping
# PONG
```

### Step 5: Access the Application

- **API Documentation**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health
- **API Endpoint**: http://localhost:8001/api/v1/

---

## Development Environment

### Hot-Reload Development

The development setup mounts your source code as volumes, enabling hot-reload:

```bash
# Start development environment
docker compose up -d

# View application logs (with live updates)
docker compose logs -f app

# Edit code locally - changes are reflected automatically
# The app watches /app/app for changes
```

### Using Ollama (Native vs Docker)

#### Option A: Native Ollama (Recommended for macOS)

```bash
# Start Ollama natively (in separate terminal or as service)
ollama serve

# docker-compose.yml automatically uses host.docker.internal:11434
docker compose up -d
```

#### Option B: Ollama in Docker (Linux with GPU)

```bash
# Start with Ollama profile
docker compose --profile ollama up -d

# Update .env to use Docker Ollama
# OLLAMA_API_URL=http://ollama:11434
```

### Optional Tools

#### Streamlit Admin Dashboard

The unified admin dashboard includes:
- 🤖 Chat Visualizer - Test chat and visualize agent flow
- 📚 Knowledge Base - Browse, edit, and search documents
- 📤 Upload Documents - Upload PDFs and text content
- 🔧 Embeddings - Manage embedding coverage
- 🏢 Excelencia - Manage modules and demos
- ⚙️ Agent Config - Configure agents
- 📊 Statistics - View knowledge base stats

```bash
# Start with tools profile
docker compose --profile tools up -d

# Access at http://localhost:8501
```

#### All Services Including Ollama

```bash
# Start everything
docker compose --profile ollama --profile tools up -d
```

### Development Workflow Commands

```bash
# Rebuild after changing Dockerfile or dependencies
docker compose build app

# Rebuild without cache (when dependencies change)
docker compose build --no-cache app

# Restart app container
docker compose restart app

# View logs
docker compose logs -f app

# Execute commands in container
docker compose exec app uv run pytest -v

# Access app shell
docker compose exec app bash

# Access database
docker compose exec postgres psql -U aynux -d aynux
```

---

## Production Deployment

### Building Production Image

```bash
# Build production image (optimized, non-root user)
docker build --target production -t aynux-app:prod .

# Tag for registry
docker tag aynux-app:prod your-registry.com/aynux-app:v1.0.0
docker push your-registry.com/aynux-app:v1.0.0
```

### Production Configuration

Create a `.env.production` file:

```bash
# Database (use strong passwords!)
DB_USER=aynux_prod
DB_PASSWORD=<strong-random-password>
DB_NAME=aynux_prod
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30

# Redis with authentication
REDIS_PASSWORD=<strong-random-password>

# Ollama (internal network in production)
OLLAMA_API_URL=http://ollama:11434
OLLAMA_API_MODEL=deepseek-r1:7b

# Application
ENVIRONMENT=production
DEBUG=false

# WhatsApp (if using)
WHATSAPP_ACCESS_TOKEN=<your-token>
WHATSAPP_PHONE_NUMBER_ID=<your-phone-id>
WHATSAPP_VERIFY_TOKEN=<your-verify-token>

# Monitoring
LANGSMITH_API_KEY=<your-langsmith-key>
LANGSMITH_PROJECT=aynux-production
SENTRY_DSN=<your-sentry-dsn>
```

### Deploy to Production

```bash
# Use production compose override
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check deployment
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f app
```

### Production Features

The production configuration (`docker-compose.prod.yml`) includes:

| Feature | Description |
|---------|-------------|
| **Resource Limits** | Memory and CPU limits for each service |
| **Replicas** | 2 app instances for high availability |
| **Rolling Updates** | Zero-downtime deployments with health checks |
| **Redis Auth** | Password-protected Redis |
| **No Port Exposure** | Internal ports only (except app) |
| **Health Checks** | All services with health monitoring |

### Scaling

```bash
# Scale app instances
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale app=4

# Check running instances
docker compose ps
```

---

## Testing with Docker

### Run Tests in Docker

```bash
# Run complete test suite
docker compose -f docker-compose.test.yml up --abort-on-container-exit

# Get exit code (for CI/CD)
docker compose -f docker-compose.test.yml up --exit-code-from app

# Clean up after tests
docker compose -f docker-compose.test.yml down -v
```

### Test Configuration

The test environment (`docker-compose.test.yml`):
- Uses ephemeral databases (no persistent volumes)
- Isolated network
- Coverage reporting to `./coverage/`
- Compatible with GitHub Actions

### GitHub Actions Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build test image
        run: docker build --target development -t aynux-app:test .

      - name: Run tests
        run: |
          docker compose -f docker-compose.test.yml up \
            --abort-on-container-exit \
            --exit-code-from app

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage/coverage.xml
```

---

## Troubleshooting

### Common Issues

#### 1. Docker Desktop Credential Store Error (macOS)

**Error:**
```
error getting credentials - err: exit status 1, out: ``
failed to resolve source metadata for docker.io/library/python:3.12-slim
```

**Cause:** Docker Desktop's `credsStore: desktop` in `~/.docker/config.json` can fail.

**Solutions:**

**Option A: Build manually (recommended)**
```bash
# Build image directly instead of via docker compose
docker build --target development -t aynux-app:dev .

# Then use compose with pre-built image
docker compose up -d
```

**Option B: Fix credential store**
```bash
# Edit Docker config
nano ~/.docker/config.json

# Option 1: Remove credsStore entirely
# Change from:
{
  "credsStore": "desktop"
}
# To:
{}

# Option 2: Use osxkeychain instead
{
  "credsStore": "osxkeychain"
}
```

#### 2. Image Pull Access Denied

**Error:**
```
pull access denied for aynux-app, repository does not exist
```

**Cause:** Docker Compose tries to pull instead of using local image.

**Solution:** Ensure `pull_policy: never` in docker-compose.yml:
```yaml
app:
  image: aynux-app:dev
  pull_policy: never  # Use local image only
```

#### 3. Ollama Connection Failed

**Error:**
```
Connection refused to http://host.docker.internal:11434
```

**Solutions:**

```bash
# Verify Ollama is running
curl http://localhost:11434/api/version

# If not running, start it
ollama serve

# If running but still failing, check Docker Desktop settings
# Ensure "host.docker.internal" DNS is enabled (usually default)
```

#### 4. pgvector Extension Not Found

**Error:**
```
ERROR: could not open extension control file "vector.control"
```

**Cause:** Using wrong PostgreSQL image.

**Solution:** Use the pgvector image:
```yaml
postgres:
  image: pgvector/pgvector:pg16  # NOT postgres:16
```

#### 5. Container Health Check Failing

```bash
# Check container health status
docker compose ps
docker inspect --format='{{.State.Health.Status}}' aynux-app

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' aynux-app

# Check application logs
docker compose logs app
```

#### 6. Database Connection Errors

```bash
# Verify database is ready
docker compose exec postgres pg_isready -U aynux -d aynux

# Check database logs
docker compose logs postgres

# Connect manually
docker compose exec postgres psql -U aynux -d aynux -c "SELECT 1;"
```

#### 7. Permission Denied Errors

```bash
# Fix volume permissions (Linux)
sudo chown -R $USER:$USER ./app ./tests

# Or run container as root temporarily for debugging
docker compose exec -u root app bash
```

### Debug Mode

```bash
# Start with verbose output
docker compose up --verbose

# Check Docker daemon logs (macOS)
tail -f ~/Library/Containers/com.docker.docker/Data/log/host/com.docker.driver.amd64-linux.log

# Check Docker daemon logs (Linux)
sudo journalctl -u docker.service -f
```

---

## Command Reference

### Essential Commands

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start all services in background |
| `docker compose down` | Stop and remove containers |
| `docker compose ps` | Show running containers |
| `docker compose logs -f app` | Follow app logs |
| `docker compose restart app` | Restart app container |
| `docker compose build` | Build/rebuild images |

### Development Commands

| Command | Description |
|---------|-------------|
| `docker compose exec app bash` | Shell into app container |
| `docker compose exec app uv run pytest -v` | Run tests |
| `docker compose exec postgres psql -U aynux` | Access database |
| `docker compose exec redis redis-cli` | Access Redis CLI |
| `docker compose build --no-cache app` | Rebuild without cache |

### Production Commands

| Command | Description |
|---------|-------------|
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` | Start production |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f` | Production logs |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml down` | Stop production |

### Profile Commands

| Command | Description |
|---------|-------------|
| `docker compose --profile ollama up -d` | Include Ollama in Docker |
| `docker compose --profile tools up -d` | Include Admin Dashboard |
| `docker compose --profile ollama --profile tools up -d` | Include all optional services |

### Testing Commands

| Command | Description |
|---------|-------------|
| `docker compose -f docker-compose.test.yml up --abort-on-container-exit` | Run tests |
| `docker compose -f docker-compose.test.yml down -v` | Clean up test environment |

---

## Maintenance & Operations

### Backup Database

```bash
# Create backup
docker compose exec postgres pg_dump -U aynux -d aynux > backup_$(date +%Y%m%d).sql

# Restore backup
docker compose exec -T postgres psql -U aynux -d aynux < backup_20241128.sql
```

### Backup Volumes

```bash
# List volumes
docker volume ls | grep aynux

# Backup PostgreSQL data
docker run --rm -v aynux-postgres-data:/data -v $(pwd):/backup alpine \
    tar czf /backup/postgres_backup.tar.gz -C /data .

# Restore PostgreSQL data
docker run --rm -v aynux-postgres-data:/data -v $(pwd):/backup alpine \
    tar xzf /backup/postgres_backup.tar.gz -C /data
```

### Update Services

```bash
# Pull latest base images
docker compose pull

# Rebuild application
docker compose build --no-cache app

# Rolling update (production)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps app
```

### Clean Up

```bash
# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes data!)
docker compose down -v

# Remove unused Docker resources
docker system prune -a

# Remove dangling images
docker image prune

# Remove all aynux images
docker images | grep aynux | awk '{print $3}' | xargs docker rmi -f
```

### Monitor Resources

```bash
# Real-time container stats
docker stats

# Disk usage
docker system df

# Container resource usage
docker compose top
```

---

## Environment Variables Reference

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | postgres | Database host |
| `DB_PORT` | 5432 | Database port |
| `DB_NAME` | aynux | Database name |
| `DB_USER` | aynux | Database user |
| `DB_PASSWORD` | aynux_dev | Database password |
| `DB_POOL_SIZE` | 5 | Connection pool size |
| `DB_MAX_OVERFLOW` | 10 | Max additional connections |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | redis | Redis host |
| `REDIS_PORT` | 6379 | Redis port |
| `REDIS_DB` | 0 | Redis database number |
| `REDIS_PASSWORD` | (empty) | Redis password |

### Ollama

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_API_URL` | http://host.docker.internal:11434 | Ollama API URL |
| `OLLAMA_API_MODEL` | deepseek-r1:7b | Main LLM model |
| `OLLAMA_API_MODEL_EMBEDDING` | nomic-embed-text | Embedding model |

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | development | Environment name |
| `DEBUG` | true | Enable debug mode |
| `TESTING` | false | Testing mode |
| `API_V1_STR` | /api/v1 | API prefix |

---

## Files Reference

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build (development + production) |
| `docker-compose.yml` | Development environment |
| `docker-compose.prod.yml` | Production overrides |
| `docker-compose.test.yml` | Testing environment |
| `docker-entrypoint.sh` | Production startup script with health checks |
| `scripts/init-db.sql` | Database initialization (pgvector extension) |
| `.dockerignore` | Build context exclusions |

---

## Related Documentation

- [README.md](../README.md) - Project overview
- [CLAUDE.md](../CLAUDE.md) - Development guidelines
- [TESTING_GUIDE.md](./TESTING_GUIDE.md) - Testing strategy
- [PGVECTOR_MIGRATION.md](./PGVECTOR_MIGRATION.md) - Vector search setup
