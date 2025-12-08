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
REDIS_HOST, OLLAMA_API_URL

# LLM Model Tiers (4-tier system)
OLLAMA_API_MODEL_SIMPLE=deepseek-r1:1.5b    # Intent analysis, classification
OLLAMA_API_MODEL_COMPLEX=deepseek-r1:7b     # Complex responses
OLLAMA_API_MODEL_REASONING=deepseek-r1:7b   # Deep analysis
OLLAMA_API_MODEL_SUMMARY=llama3.2:latest    # Summaries (NON-reasoning!)
OLLAMA_API_MODEL_EMBEDDING=nomic-embed-text # Vector embeddings (768d)

# Integrations
WHATSAPP_ACCESS_TOKEN, DUX_API_KEY, LANGSMITH_API_KEY

# Multi-Tenancy
MULTI_TENANT_MODE=false  # true for SaaS mode
TENANT_HEADER=X-Tenant-ID
```

### LLM Model Selection

```python
from app.integrations.llm.model_provider import ModelComplexity, get_model_name_for_complexity

# Use appropriate tier for task
model = get_model_name_for_complexity(ModelComplexity.SIMPLE)   # Fast intent
model = get_model_name_for_complexity(ModelComplexity.COMPLEX)  # Main response
model = get_model_name_for_complexity(ModelComplexity.SUMMARY)  # Conversation summary
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
- `excelencia_agent` - Main ERP orchestrator
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
│   ├── excelencia/            # PRIMARY - ERP software domain
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

### Streamlit Admin Pages

```
streamlit_admin/pages/
├── 1_🤖_Chat_Visualizer_[Global].py
├── 2_📚_Knowledge_Base_[Global].py
├── 5_🏢_Excelencia_[Global].py
├── 8_🏢_Organizations_[Multi].py
├── 10_⚙️_Tenant_Config_[Multi].py
└── 11_📄_Tenant_Documents_[Multi].py
```

**Naming**: `[Global]` = system-wide, `[Multi]` = per-tenant

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
