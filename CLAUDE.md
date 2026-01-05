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
| **Agents** | `ENABLED_AGENTS` from env |
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
REDIS_HOST, OLLAMA_API_URL

# Multi-Tenancy
MULTI_TENANT_MODE=false  # true for SaaS mode
TENANT_HEADER=X-Tenant-ID

# Integrations
DUX_API_KEY, LANGSMITH_API_KEY
# NOTE: WhatsApp/Chattigo credentials stored in database via Admin API
```

### LLM Configuration (Hybrid Architecture)

The system supports two LLM modes:

| Mode | Description |
|------|-------------|
| **Ollama Only** (default) | All tiers use local Ollama models |
| **Hybrid** | COMPLEX/REASONING → External API, SIMPLE/SUMMARY → Ollama |

**Model Tiers**:

| Tier | Purpose | Ollama Mode | Hybrid Mode |
|------|---------|-------------|-------------|
| SIMPLE | Intent analysis, classification | gemma3 | gemma3 (Ollama) |
| SUMMARY | Conversation summaries | llama3.2 | llama3.2 (Ollama) |
| COMPLEX | Complex responses | gemma2 | deepseek-chat (DeepSeek API) |
| REASONING | Deep multi-step analysis | deepseek-r1:8b | deepseek-reasoner (DeepSeek API) |

**Ollama-Only Mode** (default):
```bash
# All tiers use Ollama local
EXTERNAL_LLM_ENABLED=false
OLLAMA_API_MODEL_SIMPLE=gemma3
OLLAMA_API_MODEL_SUMMARY=llama3.2
OLLAMA_API_MODEL_COMPLEX=gemma2
OLLAMA_API_MODEL_REASONING=deepseek-r1:8b
OLLAMA_API_MODEL_EMBEDDING=nomic-embed-text
```

**Hybrid Mode** (DeepSeek API + Ollama):
```bash
# External API for COMPLEX/REASONING
EXTERNAL_LLM_ENABLED=true
EXTERNAL_LLM_PROVIDER=deepseek
EXTERNAL_LLM_API_KEY=sk-your-deepseek-key
EXTERNAL_LLM_MODEL_COMPLEX=deepseek-chat
EXTERNAL_LLM_MODEL_REASONING=deepseek-reasoner
EXTERNAL_LLM_FALLBACK_MODEL=llama3.1
EXTERNAL_LLM_TIMEOUT=120

# Ollama for SIMPLE/SUMMARY
OLLAMA_API_MODEL_SIMPLE=gemma3
OLLAMA_API_MODEL_SUMMARY=llama3.2
```

**Fallback Behavior**: If DeepSeek API fails, automatically falls back to Ollama with `EXTERNAL_LLM_FALLBACK_MODEL`.

### LLM Model Selection

```python
from app.integrations.llm import ModelComplexity

# Agents use complexity tiers - routing is automatic
response = await llm.generate("query", complexity=ModelComplexity.SIMPLE)   # → Ollama
response = await llm.generate("query", complexity=ModelComplexity.COMPLEX)  # → DeepSeek (if enabled)
```

> **Warning**: SUMMARY tier must use non-reasoning models. DeepSeek-R1's "thinking tokens" cause 10-50x slowdown.

### Agent Enablement
```bash
# Global mode (Excelencia-focused)
ENABLED_AGENTS=greeting_agent,excelencia_agent,excelencia_invoice_agent,excelencia_support_agent,excelencia_promotions_agent,support_agent,data_insights_agent,fallback_agent,farewell_agent
```

**Core Agents** (always on): `orchestrator`, `supervisor`

**Global Agents** (domain_key=None):
- `greeting_agent` - Multi-domain greeting
- `support_agent` - General support
- `fallback_agent` - Catch-all
- `farewell_agent` - Goodbye

**Excelencia Domain** (domain_key="excelencia"):
- `excelencia_agent` - Main Software orchestrator
- `excelencia_invoice_agent` - Client invoicing
- `excelencia_support_agent` - Software support
- `excelencia_promotions_agent` - Software promotions
- `data_insights_agent` - Analytics

**E-commerce Domain** (domain_key="ecommerce", disabled by default):
- `ecommerce_agent` - Product search, orders

**Admin APIs**: `GET /api/v1/admin/agents/status|enabled|disabled|config`

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
- **Model**: `nomic-embed-text` (768 dims) via Ollama

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
│   ├── llm/                   # OllamaLLM, model_provider.py (4-tier system)
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
- Ollama

### Docker Quick Start
```bash
cp .env.example .env
ollama pull deepseek-r1:7b && ollama pull nomic-embed-text
docker compose up -d
curl http://localhost:8001/health
```

### Profiles
```bash
docker compose up -d                                    # Base
docker compose --profile ollama up -d                   # + LLM
docker compose --profile tools up -d                    # + Dashboard
docker compose --profile ollama --profile tools up -d   # All
```

## Code Review Checklist

- [ ] SRP: Single responsibility per class?
- [ ] Functions <20 lines?
- [ ] Dependencies injected?
- [ ] Type hints complete?
- [ ] Error handling with `from e`?
- [ ] Tests can run independently?
