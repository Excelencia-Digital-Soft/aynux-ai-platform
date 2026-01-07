# CLAUDE.md

Guidance for Claude Code working with this repository.

## Project Overview

**Aynux** - Multi-domain WhatsApp bot platform (FastAPI + LangGraph multi-agent system)

| Feature | Description |
|---------|-------------|
| **Architecture** | Clean Architecture + DDD, multi-domain support |
| **Orchestrator** | SuperOrchestrator for intelligent domain routing |
| **RAG** | pgvector semantic search per domain/tenant |
| **Domains** | Excelencia (primary), E-commerce, Healthcare, Credit |
| **Modes** | Global (Excelencia-specific) / Multi-tenant (SaaS) |

## Critical Development Rules

### 1. Exception Handling - Always preserve stack traces
```python
# ✅ Good
except ValueError as e:
    raise HTTPException(status_code=400, detail="Invalid") from e
```

### 2. Modern Typing (Python 3.10+)
```python
# ✅ Use native types
def func(ids: list[int], data: dict[str, str] | None) -> None: ...
# ❌ Avoid: List, Dict, Optional from typing
```

### 3. UTC Timezone
```python
from datetime import UTC, datetime
now = datetime.now(UTC)  # ✅ Always UTC
```

### 4. pgvector with asyncpg - CRITICAL Bug
When using SQLAlchemy `text()` with asyncpg and pgvector, **NEVER use `::vector` cast syntax** with named parameters:

```python
# ❌ BROKEN - asyncpg confuses :param::type syntax
sql = text("SELECT * FROM docs WHERE 1 - (embedding <=> :vec::vector) > 0.5")

# ✅ CORRECT - use CAST() instead
sql = text("SELECT * FROM docs WHERE 1 - (embedding <=> CAST(:vec AS vector)) > 0.5")
```

**Why**: asyncpg interprets `:vec` as a parameter placeholder, then `::vector` causes a syntax error.

**Affected operations**: All vector searches and updates using named parameters.

## Documentation Reference

**Before changes, review `docs/`**:
- `LangGraph.md` - Agent architecture
- `MULTI_TENANCY.md` - Multi-tenant APIs
- `DOCKER_DEPLOYMENT.md` - Docker setup
- `PGVECTOR_MIGRATION.md` - Vector search
- `TESTING_GUIDE.md` - Testing strategy

## Operating Modes

Aynux operates in **two modes** with different development patterns:

### Global Mode (Default) - Excelencia-specific

**When**: `MULTI_TENANT_MODE=false` (default)

| Aspect | Pattern |
|--------|---------|
| **Configuration** | Environment variables, `settings.py` |
| **Agents** | Database-driven via `core.agents` table |
| **Data** | Shared `company_knowledge` table |
| **Code** | ✅ OK to hardcode Excelencia-specific logic |
| **RAG** | Global pgvector, no org filtering |

```python
# ✅ OK in Global Mode - hardcoded business logic
if domain == "excelencia":
    modules = ["Inventario", "Facturación", "Contabilidad"]  # Hardcoded OK
```

### Multi-tenant Mode (In Development)

**When**: `MULTI_TENANT_MODE=true`

| Aspect | Pattern |
|--------|---------|
| **Configuration** | Database (`TenantConfig`, `TenantAgent`) |
| **Agents** | Per-org from `tenant_agents` table |
| **Data** | Isolated by `organization_id` |
| **Code** | ❌ NEVER hardcode - load from DB |
| **RAG** | Filtered by `organization_id` |

```python
# ✅ Multi-tenant - load from database
from app.core.tenancy import get_tenant_context
ctx = get_tenant_context()
config = ctx.config  # TenantConfig from DB
agents = await TenantAgentService.get_agent_registry(ctx.organization_id)

# ❌ WRONG - hardcoded in multi-tenant
modules = ["Inventario", "Facturación"]  # Never hardcode!
```

### Key Tenancy Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `TenantContext` | `app/core/tenancy/context.py` | Request-scoped context (contextvars) |
| `TenantResolver` | `app/core/tenancy/resolver.py` | JWT/Header/WhatsApp resolution |
| `TenantVectorStore` | `app/core/tenancy/vector_store.py` | Isolated pgvector per org |
| `TenantPromptManager` | `app/core/tenancy/prompt_manager.py` | 4-level prompt hierarchy |
| `TenantAgentFactory` | `app/core/tenancy/agent_factory.py` | Per-org agent filtering |

### Agent Tables Architecture

| Table | UI Management | Purpose |
|-------|---------------|---------|
| `core.agents` | `/agent-catalog` | Global agent catalog (all available agents) |
| `core.tenant_agents` | `TenantAgentSelection` | Per-organization agent configuration |

**System Organization UUID**: `00000000-0000-0000-0000-000000000000`

When webhook receives this UUID, it uses `core.agents` (global catalog) instead of `tenant_agents`.

```python
# In TenantAgentService.get_agent_registry()
SYSTEM_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")

if org_id == SYSTEM_ORG_ID:
    # Load from core.agents (global catalog)
    return await self._load_global_catalog_registry()
else:
    # Load from tenant_agents (per-org config)
    return await self._load_agents_from_db(org_id)
```

## Development Commands

```bash
# Server
uv run uvicorn app.main:app --reload --port 8080

# Quality
uv run black app && uv run isort app && uv run ruff check app --fix
uv run pytest -v
```

## Architecture (Clean Architecture + DDD)

### Layer Structure

| Layer | Location | Contents |
|-------|----------|----------|
| **Domain** | `app/domains/*/domain/` | Entities, Value Objects, Domain Services |
| **Application** | `app/domains/*/application/` | Use Cases, DTOs, Ports (Protocol) |
| **Infrastructure** | `app/domains/*/infrastructure/` | Repositories, External Services |
| **Presentation** | `app/api/` | FastAPI endpoints, webhooks |

### Multi-Agent System (LangGraph)

```
Super Orchestrator → Domain Services → Specialized Agents
     ↓                    ↓                   ↓
 Intent routing    EcommerceDomain     product_agent
                   HealthcareDomain    support_agent
                   CreditDomain        invoice_agent
```

**Key Files**:
- `app/orchestration/super_orchestrator.py` - Domain routing
- `app/agents/graph.py` - LangGraph StateGraph
- `app/agents/subagent/` - Specialized agents
- `app/core/container.py` - Dependency injection

### Dependency Injection

```python
from app.core.container import DependencyContainer
from fastapi import Depends
from app.api.dependencies import get_search_products_use_case

@router.get("/products/search")
async def search(query: str, uc = Depends(get_search_products_use_case)):
    return await uc.execute(query=query)
```

## Configuration

### Environment Variables (.env)
```bash
# Database
DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

# Services
REDIS_HOST, VLLM_BASE_URL, TEI_BASE_URL

# Multi-Tenancy
MULTI_TENANT_MODE=false  # true for SaaS mode
TENANT_HEADER=X-Tenant-ID

# Integrations
DUX_API_KEY, LANGSMITH_API_KEY
# NOTE: WhatsApp/Chattigo credentials stored in database via Admin API
```

### LLM Configuration (vLLM + TEI)

The system uses vLLM for high-performance LLM inference and TEI for embeddings:

| Component | Service | Purpose |
|-----------|---------|---------|
| **LLM Inference** | vLLM | OpenAI-compatible API with single model |
| **Embeddings** | TEI | Text Embeddings Inference - BAAI/bge-m3 (1024 dims) |

**Configuration**:
```bash
# vLLM Configuration (single model)
# Dev: localhost | Prod: 192.168.0.140
VLLM_BASE_URL=http://localhost:8090/v1
VLLM_API_KEY=EMPTY
VLLM_MODEL=qwen-3b
VLLM_REQUEST_TIMEOUT=120

# TEI Embeddings (BAAI/bge-m3, 1024 dims)
# Dev: localhost | Prod: 192.168.0.140
TEI_BASE_URL=http://localhost:7997
TEI_MODEL=BAAI/bge-m3
TEI_EMBEDDING_DIMENSION=1024
```

### LLM Model Selection

```python
from app.integrations.llm import ModelComplexity, VllmLLM

# All complexity tiers use the same model (qwen-3b)
vllm = VllmLLM()
llm = vllm.get_llm(complexity=ModelComplexity.COMPLEX)  # → qwen-3b
# Note: complexity parameter preserved for backward compatibility
```

### Agent Configuration (Database-Driven)

Agents are configured via database tables, managed through the Admin UI:

| Table | UI | Purpose | When Used |
|-------|-----|---------|-----------|
| `core.agents` | `/agent-catalog` | Global agent catalog | System org (`00000000-0000-0000-0000-000000000000`) |
| `core.tenant_agents` | `TenantAgentSelection` | Per-organization agents | Specific tenant orgs |

**Core Agents** (always on): `orchestrator`, `supervisor`

**Available Agents by Domain:**

| Domain | Agents |
|--------|--------|
| **Global** (domain_key=None) | `greeting_agent`, `support_agent`, `fallback_agent`, `farewell_agent` |
| **Excelencia** (domain_key="excelencia") | `excelencia_agent`, `excelencia_invoice_agent`, `excelencia_support_agent`, `excelencia_promotions_agent`, `data_insights_agent` |
| **E-commerce** (domain_key="ecommerce") | `ecommerce_agent` |
| **Pharmacy** (domain_key="pharmacy") | `pharmacy_operations_agent` |

**Managing Agents:**
- **Seed Builtin**: `POST /admin/agents/seed/builtin` - Creates default agents in DB
- **Enable/Disable**: Toggle in `/agent-catalog` UI or via API `POST /admin/agents/{id}/toggle`
- **List Enabled**: `GET /admin/agents/enabled-keys` - Returns enabled agent keys from DB

**Admin APIs**: `GET /api/v1/admin/agents/status|enabled|enabled-keys|config`

## Code Quality Standards

### SOLID Principles (Mandatory)

| Principle | Rule |
|-----------|------|
| **SRP** | One responsibility per class. Functions <20 lines. |
| **OCP** | Extend via inheritance, don't modify base. |
| **LSP** | Subclasses honor parent contracts. |
| **ISP** | Small, focused Protocol interfaces. |
| **DIP** | Depend on abstractions, inject dependencies. |

### Quality Rules
- **DRY**: Extract common logic, use base classes
- **KISS**: Simple solutions, no premature optimization
- **YAGNI**: Only implement current requirements

### Naming Conventions
- Classes: `PascalCase` (`ProductService`)
- Functions: `snake_case` (`get_product`)
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

### Size Limits
- Functions: <20 lines (max 50)
- Classes: <200 lines (max 500)

## Development Patterns

### Adding Use Cases
1. Create in `app/domains/{domain}/application/use_cases/`
2. Define Port (Protocol) in `ports/`
3. Implement Repository in `infrastructure/repositories/`
4. Register in `DependencyContainer`
5. Add FastAPI dependency in `app/api/dependencies.py`

### Adding Agents
1. Extend `BaseAgent` from `app/agents/subagent/base_agent.py`
2. Implement `_process_internal()` method
3. Add to `AgentType` enum
4. Register in `AynuxGraph._init_agents()`

### Agent Template Method Pattern
```python
class MyAgent(BaseAgent):
    async def _process_internal(self, state: dict) -> dict:
        # Your logic here - process() wrapper handles:
        # - Input validation
        # - Error handling with stack traces
        # - Metrics collection
        pass
```

## Multi-Tenancy

See `docs/MULTI_TENANCY.md` for complete documentation.

**Components** (`app/core/tenancy/`):
- `TenantContext` - Request-scoped context
- `TenantResolver` - JWT/header/WhatsApp resolution
- `TenantVectorStore` - Isolated RAG per tenant
- `TenantPromptManager` - Hierarchical prompts

**APIs**: `/api/v1/admin/organizations/*`

## DUX-RAG Integration (E-commerce) - DISABLED

**Pipeline**: `DUX API → PostgreSQL → Embeddings → pgvector`

**Schedule**: Auto sync every 12h (2:00 AM, 2:00 PM)

**Admin APIs**:
- `GET /api/v1/admin/dux/sync/status`
- `POST /api/v1/admin/dux/sync/force`

## Database Schema

### Core Tables
| Domain | Tables |
|--------|--------|
| E-commerce | products, categories, orders, promotions |
| Healthcare | patients, appointments |
| Credit | accounts, collections |
| Shared | conversations |

### Vector Search
- **Extension**: pgvector with HNSW indexing
- **Model**: `BAAI/bge-m3` (1024 dims) via TEI

## File Structure

```
app/
├── domains/                    # DDD Bounded Contexts
│   ├── excelencia/            # PRIMARY - Software domain
│   │   ├── agents/            # excelencia_agent, invoice, support, promotions
│   │   ├── application/       # Use cases
│   │   └── infrastructure/    # Repositories
│   ├── ecommerce/             # E-commerce domain (disabled by default)
│   ├── healthcare/            # Healthcare domain
│   ├── credit/                # Finance/Credit domain
│   └── shared/                # Shared agents (greeting, farewell, fallback)
├── integrations/
│   ├── llm/                   # VllmLLM, TEIEmbeddings, model_provider.py
│   ├── vector_stores/         # pgvector, embeddings
│   └── whatsapp/              # WhatsApp Business API
├── core/
│   ├── tenancy/               # Multi-tenant isolation
│   │   ├── context.py         # TenantContext (contextvars)
│   │   ├── middleware.py      # TenantContextMiddleware
│   │   ├── resolver.py        # JWT/Header/WhatsApp resolution
│   │   ├── vector_store.py    # TenantVectorStore
│   │   └── prompt_manager.py  # 4-level prompt hierarchy
│   ├── container/             # DI containers
│   ├── interfaces/            # IRepository, ILLM protocols
│   └── agents/                # BaseAgent
├── orchestration/             # SuperOrchestrator (domain routing)
├── api/
│   ├── routes/admin/          # Admin APIs (orgs, config, agents)
│   └── routes/webhook.py      # WhatsApp webhook
├── models/db/tenancy/         # Organization, TenantConfig, TenantAgent...
└── prompts/templates/         # YAML prompt templates
```

## PostgreSQL Connection (Docker)

### Connection Details

| Context | Host | Port | User | Password | Database |
|---------|------|------|------|----------|----------|
| **From host** | `localhost` | `5432` | `enzo` | `aynux_dev` | `aynux` |
| **From Docker containers** | `postgres` | `5432` | `enzo` | `aynux_dev` | `aynux` |

### Quick Connect Commands

```bash
# From host machine (psql)
PGPASSWORD=aynux_dev psql -h localhost -p 5432 -U enzo -d aynux

# Via docker exec (direct to container)
docker exec -it aynux-postgres psql -U enzo -d aynux

# Connection string (from host)
postgresql://enzo:aynux_dev@localhost:5432/aynux

# Connection string (from Docker network)
postgresql://enzo:aynux_dev@postgres:5432/aynux
```

### Docker Container Info
- **Container**: `aynux-postgres`
- **Image**: `pgvector/pgvector:pg18` (PostgreSQL 18 with pgvector)
- **Network**: `aynux-network`
- **Volume**: `aynux-postgres-data`

## Redis Connection (Docker)

### Connection Details

| Context | Host | Port | Password | Database |
|---------|------|------|----------|----------|
| **From host** | `localhost` | `6379` | `Excelenci@5948` | `0` |
| **From Docker containers** | `redis` | `6379` | `Excelenci@5948` | `0` |

### Quick Connect Commands

```bash
# Via docker exec (recommended - no local redis-cli needed)
docker exec aynux-redis redis-cli -a 'Excelenci@5948' ping

# Interactive session
docker exec -it aynux-redis redis-cli -a 'Excelenci@5948'

# Connection URL (from host)
redis://:Excelenci@5948@localhost:6379/0

# Connection URL (from Docker network)
redis://:Excelenci@5948@redis:6379/0
```

### Docker Container Info
- **Container**: `aynux-redis`
- **Image**: `redis:7-alpine`
- **Network**: `aynux-network`
- **Volume**: `aynux-redis-data`

## Deployment

### Required Services
- PostgreSQL (with pgvector)
- Redis
- vLLM (LLM inference)
- TEI (embeddings)

### Docker Quick Start
```bash
cp .env.example .env
# Ensure vLLM and TEI services are running
docker compose up -d
curl http://localhost:8001/health
```

### Profiles
```bash
docker compose up -d                                    # Base
docker compose --profile llm up -d                      # + vLLM/TEI
docker compose --profile tools up -d                    # + Dashboard
docker compose --profile llm --profile tools up -d      # All
```

## Code Review Checklist

- [ ] SRP: Single responsibility per class?
- [ ] Functions <20 lines?
- [ ] Dependencies injected?
- [ ] Type hints complete?
- [ ] Error handling with `from e`?
- [ ] Tests can run independently?
