# CLAUDE.md

Guidance for Claude Code working with this repository.

## Project Overview

**Aynux** - Multi-domain WhatsApp bot platform (FastAPI + LangGraph multi-agent system)

| Feature | Description |
|---------|-------------|
| **Architecture** | Clean Architecture + DDD, multi-domain support |
| **Orchestrator** | Intelligent routing to domain services |
| **RAG** | pgvector semantic search per domain |
| **Domains** | E-commerce, Healthcare, Finance (Credit) |

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

## Documentation Reference

**Before changes, review `docs/`**:
- `LangGraph.md` - Agent architecture
- `MULTI_TENANCY.md` - Multi-tenant APIs
- `DOCKER_DEPLOYMENT.md` - Docker setup
- `PGVECTOR_MIGRATION.md` - Vector search
- `TESTING_GUIDE.md` - Testing strategy

## Development Commands

```bash
# Server
uv run uvicorn app.main:app --reload --port 8000

# Quality
uv run black app && uv run isort app && uv run ruff check app --fix
uv run pytest -v

# Tools
streamlit run streamlit_agent_visualizer.py    # Agent debugger
streamlit run streamlit_knowledge_manager.py   # Knowledge base
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
REDIS_HOST, OLLAMA_API_URL, OLLAMA_API_MODEL_COMPLEX

# Integrations
WHATSAPP_ACCESS_TOKEN, DUX_API_KEY, LANGSMITH_API_KEY

# Multi-Tenancy
MULTI_TENANT_MODE=true
TENANT_HEADER=X-Tenant-ID
```

### Agent Enablement
```bash
ENABLED_AGENTS=greeting_agent,product_agent,fallback_agent,farewell_agent
```

**Core Agents** (always on): `orchestrator`, `supervisor`

**Configurable**: `greeting_agent`, `product_agent`, `promotions_agent`, `tracking_agent`, `support_agent`, `invoice_agent`, `excelencia_agent`, `data_insights_agent`, `fallback_agent`, `farewell_agent`

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

## DUX-RAG Integration (E-commerce)

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
│   ├── ecommerce/             # domain/, application/, infrastructure/
│   ├── healthcare/
│   ├── credit/
│   └── shared/
├── integrations/              # LLM, vector_stores, whatsapp, monitoring
├── core/                      # container.py, interfaces/, tenancy/
├── orchestration/             # super_orchestrator.py
├── api/                       # routes/, dependencies.py, middleware/
├── agents/                    # graph.py, subagent/, schemas/
└── services/                  # Legacy (deprecated)
```

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
