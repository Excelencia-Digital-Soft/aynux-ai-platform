# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Bot ConversaShop is a WhatsApp e-commerce chatbot built with FastAPI and a LangGraph multi-agent system, integrated with DUX ERP. The system uses specialized agents to handle different customer intents through a sophisticated supervisor-agent architecture.

## Common Development Commands

### Using UV Package Manager (Preferred)

```bash
# Install dependencies
uv sync

# Start development server
uv run --with uvicorn uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# OR use the dev script
./dev-uv.sh  # then select option 2

# Run tests
uv run pytest -v
uv run pytest tests/test_phone_normalizer_pydantic.py  # Run specific test file
uv run pytest -m unit  # Run only unit tests
uv run pytest -m integration  # Run integration tests

# Code formatting and linting
uv run black app
uv run isort app
uv run ruff check app --fix

# Update dependencies
uv lock --upgrade && uv sync
```

### Testing Individual Components

```bash
# Test chat endpoint
python test_chat_endpoint.py

# Test graph orchestrator
python test_graph_orchestrator.py

# Test LangSmith integration
python test_langsmith_integration.py
```

### Database Operations

```bash
# View product statistics
PGPASSWORD="" psql -h localhost -U enzo -d conversashop -c "SELECT c.display_name as categoria, COUNT(p.id) as total_productos FROM categories c LEFT JOIN products p ON c.id = p.category_id GROUP BY c.display_name;"

# Check database migrations
# SQL migration files are located in app/scripts/
```

## High-Level Architecture

### Multi-Agent System (LangGraph)

The core intelligence uses a supervisor-agent pattern implemented with LangGraph:

```
WhatsApp Message → FastAPI Router → Supervisor Agent → Specialized Agents → Response
                                           ↓
                                    Intent Analysis
                                           ↓
                            Route to appropriate agent:
                            - product_agent (catalog queries)
                            - category_agent (category management)
                            - promotions_agent (deals/offers)
                            - tracking_agent (order tracking)
                            - support_agent (customer support)
                            - invoice_agent (billing/payments)
                            - data_insights_agent (analytics)
                            - fallback_agent (unclear intents)
                            - farewell_agent (conversation closing)
```

**Key Components:**

1. **Graph Orchestration** (`app/agents/graph.py`)
   - `EcommerceAssistantGraph`: Main coordinator using LangGraph StateGraph
   - PostgreSQL checkpointing for conversation persistence
   - Conditional routing between agents based on intent

2. **State Management** (`app/agents/state_schema.py`)
   - TypedDict-based `LangGraphState` for performance
   - Pydantic models in `app/agents/schemas/` for validation
   - StateManager bridges TypedDict and Pydantic models

3. **Supervisor Agent** (`app/agents/subagent/supervisor_agent.py`)
   - Analyzes messages using IntentRouter
   - Routes to specialized agents
   - Manages conversation flow and state

### Service Layer Architecture

```
API Routes (app/api/routes/)
    ↓
Service Layer (app/services/)
    ↓
Repository Layer (app/repositories/)
    ↓
Data Layer (PostgreSQL + Redis + ChromaDB)
```

### DUX-RAG Integration Pipeline

Automated background synchronization flow:
```
DUX ERP API → PostgreSQL → Vector Embeddings → ChromaDB → Agent RAG Search
```

**Key Services:**
- `DuxRagSyncService`: Integrated DB + RAG sync
- `ScheduledSyncService`: Background automation (2 AM, 2 PM daily)
- `EmbeddingUpdateService`: Vector processing with Ollama

### External Integrations

1. **DUX ERP System**
   - Base URL: `https://erp.duxsoftware.com.ar/WSERP/rest/services`
   - Clients: `app/clients/dux_api_client.py`, `dux_facturas_client.py`, `dux_rubros_client.py`
   - Rate limiting: 5 seconds between requests
   - Batch size: 50 items

2. **AI Models (Ollama)**
   - LLM: `deepseek-r1:7b` (configurable)
   - Embeddings: `mxbai-embed-large`
   - Local API: `http://localhost:11434`

3. **WhatsApp Business API**
   - Webhook handler: `app/api/routes/webhook.py`
   - Message processing: `app/services/whatsapp_service.py`

4. **Data Storage**
   - PostgreSQL: Main database (async with SQLAlchemy)
   - Redis: Caching and session management
   - ChromaDB: Vector store for semantic search

## Admin API Endpoints

Monitor and control system operations:

```bash
# Check sync status
curl http://localhost:8000/api/v1/admin/dux/sync/status

# Force immediate sync
curl -X POST http://localhost:8000/api/v1/admin/dux/sync/force

# Health check
curl http://localhost:8000/api/v1/admin/dux/sync/health

# Performance metrics
curl http://localhost:8000/api/v1/admin/dux/sync/metrics
```

## Critical Configuration

Essential environment variables in `.env`:

```bash
# Database
DB_HOST=localhost
DB_NAME=conversashop
DB_USER=postgres
DB_PASSWORD=

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# AI Models
OLLAMA_API_MODEL=deepseek-r1:7b
OLLAMA_API_URL=http://localhost:11434
OLLAMA_API_MODEL_EMBEDDING=mxbai-embed-large

# DUX ERP
DUX_API_BASE_URL=https://erp.duxsoftware.com.ar/WSERP/rest/services
DUX_API_KEY=your_key_here
DUX_SYNC_ENABLED=true
DUX_SYNC_HOURS=2,14  # 2 AM, 2 PM

# WhatsApp
WHATSAPP_ACCESS_TOKEN=your_token
WHATSAPP_PHONE_NUMBER_ID=your_number_id

# LangSmith Monitoring
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=conversashop-production
LANGSMITH_TRACING_ENABLED=true
```

## Development Patterns

### Creating New Agents

1. Extend `BaseAgent` from `app/agents/subagent/base_agent.py`
2. Implement `_process_internal()` method
3. Add to `AgentType` enum in `app/agents/schemas/`
4. Register in `EcommerceAssistantGraph._init_agents()`
5. Update supervisor routing logic

### API Endpoint Development

- Use dependency injection via `app/api/dependencies.py`
- Follow patterns in `app/api/routes/`
- Pydantic models in `app/models/` for validation
- Repository pattern in `app/repositories/`

### Code Style

- Python 3.13+ with type hints
- Black formatter (line length 120)
- isort for imports
- Ruff for linting
- Async/await throughout
- Structured logging

## Testing Strategy

```bash
# Run all tests
uv run pytest -v

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test markers
uv run pytest -m unit        # Unit tests only
uv run pytest -m integration # Integration tests
uv run pytest -m api        # API tests requiring external connections
```

Test files:
- Unit tests: Individual component testing
- Integration tests: Multi-component interactions
- E2E tests: Full conversation flows (`test_chat_endpoint.py`)

## Required Services

For local development, ensure these services are running:

1. **PostgreSQL** (port 5432)
2. **Redis** (port 6379)
3. **Ollama** with models:
   - `ollama pull deepseek-r1:7b`
   - `ollama pull mxbai-embed-large`

## Troubleshooting

### Common Issues

1. **DUX Sync Failures**
   - Check `DUX_API_KEY` in `.env`
   - Verify DUX API connectivity
   - Force sync: `POST /api/v1/admin/dux/sync/force`

2. **Ollama Connection Errors**
   - Ensure Ollama is running: `ollama serve`
   - Check models are pulled
   - Verify `OLLAMA_API_URL` in `.env`

3. **Database Connection Issues**
   - Check PostgreSQL is running
   - Verify database exists: `createdb conversashop`
   - Check credentials in `.env`

### Monitoring

- LangSmith traces: Check `LANGSMITH_PROJECT` dashboard
- Sentry errors: Automatic error tracking in production
- Application logs: Structured logging throughout

## Key Documentation

- **LangGraph Implementation**: `docs/LangGraph.md`
- **Supervisor-Agent Pattern**: `docs/9_agent_supervisor.md`
- **Multi-Agent Networks**: `docs/8_multi_agent_network.md`
- **Agent Teams**: `docs/7_hierarchical_agent_teams.md`
