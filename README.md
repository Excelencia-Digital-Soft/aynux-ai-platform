# 🤖 Aynux

> Multi-domain WhatsApp bot platform powered by AI agents

**Aynux** is an intelligent, multi-domain conversational AI platform built for WhatsApp Business. It uses specialized AI agents to handle different business domains (e-commerce, healthcare, finance) in a single unified system, with support for custom domain configuration and RAG-based knowledge.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-latest-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](docs/DOCKER_DEPLOYMENT.md)
[![Multi-Tenant](https://img.shields.io/badge/Multi--Tenant-ready-purple.svg)](docs/MULTI_TENANCY.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌟 Key Features

### 🎯 Multi-Domain Intelligence
- **Domain Routing**: Automatically detects user intent and routes to specialized business domains
- **Configurable Agents**: Each domain has dedicated AI agents for specific tasks
- **Context Awareness**: Maintains conversation context across multiple interactions
- **RAG-Enabled**: Semantic search over domain-specific knowledge bases

### 🏢 Supported Business Domains

#### 🛍️ E-commerce
- Product catalog search and recommendations
- Order tracking and status updates
- Customer support and FAQ
- Promotions and discount queries

#### 🏥 Healthcare (Hospital)
- Patient record management
- Appointment scheduling
- Medical information queries
- Doctor availability checks

#### 💰 Finance (Credit)
- Account balance inquiries
- Collection management
- Payment processing
- Transaction history

### 🔧 Technical Capabilities
- **Multi-Agent Architecture**: Powered by LangGraph for sophisticated conversation flows
- **Vector Search**: pgvector + ChromaDB for semantic search capabilities
- **Real-time Processing**: Async architecture for high-performance message handling
- **External Integrations**: DUX ERP, WhatsApp Business API, Ollama AI
- **Monitoring**: LangSmith tracing and Sentry error tracking
- **Caching**: Multi-layer Redis cache for optimized performance

### 🏢 Multi-Tenant Architecture
- **Organization Isolation**: Each tenant has isolated data, prompts, and configuration
- **Flexible Resolution**: Detect tenant from JWT, `X-Tenant-ID` header, or WhatsApp ID
- **Per-Tenant RAG**: Isolated knowledge bases with pgvector filtering
- **Configurable Agents**: Enable/disable agents per organization
- **Prompt Hierarchy**: 4-level override system (USER > ORG > GLOBAL > SYSTEM)
- **LLM Customization**: Per-tenant model, temperature, and token limits

See **[Multi-Tenancy Guide](docs/MULTI_TENANCY.md)** for complete documentation.

---

## 🚀 Quick Start

### Option A: Docker (Recommended)

The fastest way to get started. See **[Docker Deployment Guide](docs/DOCKER_DEPLOYMENT.md)** for complete documentation.

```bash
# 1. Clone and configure
git clone https://github.com/your-username/aynux.git
cd aynux
cp .env.example .env

# 2. Install Ollama and pull models (macOS - run natively for GPU acceleration)
brew install ollama
ollama serve  # In separate terminal
ollama pull deepseek-r1:7b && ollama pull nomic-embed-text

# 3. Build and start
docker build --target development -t aynux-app:dev .
docker compose up -d

# 4. Verify
curl http://localhost:8001/health
# {"status":"ok","environment":"development"}
```

#### Docker Compose Profiles
```bash
docker compose up -d                                    # Base (PostgreSQL, Redis, App)
docker compose --profile ollama up -d                   # + Ollama LLM (Docker)
docker compose --profile tools up -d                    # + Admin Dashboard
docker compose --profile ollama --profile tools up -d   # All services
```

#### Production Deployment
```bash
docker build --target production -t aynux-app:prod .
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Option B: Manual Installation

### Prerequisites

- Python 3.13+
- PostgreSQL 14+ with pgvector extension
- Redis 7+
- Ollama (for local LLM inference)
- WhatsApp Business API account (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/aynux.git
   cd aynux
   ```

2. **Install UV package manager** (recommended)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Setup database**
   ```bash
   # Install pgvector extension
   psql -h localhost -U your_user -d aynux -c "CREATE EXTENSION IF NOT EXISTS vector;"

   # Run migrations
   psql -h localhost -U your_user -d aynux -f app/scripts/migrations/001_add_pgvector_support.sql
   ```

6. **Start Ollama and pull models**
   ```bash
   ollama pull deepseek-r1:7b
   ollama pull nomic-embed-text
   ```

7. **Run the development server**
   ```bash
   ./dev-uv.sh
   # Or manually:
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```

8. **Access the API**
   - API Documentation: http://localhost:8001/docs
   - Health Check: http://localhost:8001/health

---

## 💬 Usage Examples

### Chat via API

```python
import requests

response = requests.post(
    "http://localhost:8001/api/v1/chat/message",
    json={
        "user_id": "user_123",
        "message": "¿Tienen laptops disponibles?",
        "session_id": "session_456"
    }
)

print(response.json())
# {
#   "response": "Sí, tenemos varias laptops disponibles. Te muestro algunas opciones...",
#   "agent_used": "product_agent",
#   "processing_time_ms": 1234
# }
```

### WhatsApp Integration

```python
# Configure webhook in your .env
WHATSAPP_ACCESS_TOKEN=your_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_VERIFY_TOKEN=your_verify_token

# The webhook endpoint automatically handles incoming WhatsApp messages
# POST /webhook
```

### Domain-Specific Queries

```python
# E-commerce domain
"¿Cuánto cuesta la laptop ASUS ROG?"
# → Routes to ProductAgent → Returns product details with price

# Healthcare domain
"Necesito agendar una cita con el Dr. García"
# → Routes to HospitalDomainService → Appointment scheduling flow

# Finance domain
"¿Cuál es mi saldo actual?"
# → Routes to CreditDomainService → Account balance query
```

### Multi-Tenant Usage

```bash
# 1. Register and login
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@acme.com", "password": "secure123", "name": "Admin"}'

TOKEN=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@acme.com", "password": "secure123"}' | jq -r '.access_token')

# 2. Create organization
ORG_ID=$(curl -s -X POST http://localhost:8001/api/v1/admin/organizations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "slug": "acme", "llm_model": "deepseek-r1:7b"}' | jq -r '.id')

# 3. Configure tenant
curl -X PATCH "http://localhost:8001/api/v1/admin/organizations/$ORG_ID/config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled_domains": ["ecommerce"], "rag_enabled": true}'

# 4. Chat with tenant context
curl -X POST http://localhost:8001/api/v1/chat/message \
  -H "X-Tenant-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-123", "message": "Show me products"}'
```

See **[Multi-Tenancy Guide](docs/MULTI_TENANCY.md)** for complete API documentation.

### Using the New Clean Architecture

#### Use Cases (Business Operations)

```python
from app.core.container import DependencyContainer
from app.domains.ecommerce.application.use_cases import SearchProductsUseCase

# Get Use Case from DependencyContainer
container = DependencyContainer()
search_products_uc = container.create_search_products_use_case()

# Execute Use Case
result = await search_products_uc.execute(
    query="laptop gaming",
    limit=5
)

# result = SearchProductsResult(
#     products=[...],
#     total_count=42,
#     search_type="vector_similarity"
# )
```

#### Dependency Injection

```python
from fastapi import Depends
from app.api.dependencies import get_search_products_use_case
from app.domains.ecommerce.application.use_cases import SearchProductsUseCase

@router.get("/products/search")
async def search_products(
    query: str,
    use_case: SearchProductsUseCase = Depends(get_search_products_use_case)
):
    """FastAPI automatically injects Use Case via DependencyContainer"""
    result = await use_case.execute(query=query)
    return result
```

#### Repository Pattern

```python
from app.domains.ecommerce.application.ports import IProductRepository
from app.domains.ecommerce.infrastructure.repositories import ProductRepository

# Depend on abstraction (IProductRepository), not concrete implementation
class SearchProductsUseCase:
    def __init__(self, repository: IProductRepository):
        self.repository = repository  # Protocol (interface)

    async def execute(self, query: str):
        # Business logic uses abstract interface
        products = await self.repository.search_by_query(query)
        return products
```

---

## 📚 Documentation

### Core Documentation
- **[docs/FINAL_MIGRATION_SUMMARY.md](docs/FINAL_MIGRATION_SUMMARY.md)**: Clean Architecture migration complete guide
- **[docs/LangGraph.md](docs/LangGraph.md)**: Complete LangGraph architecture guide
- **[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)**: Testing strategy and best practices
- **[docs/PGVECTOR_MIGRATION.md](docs/PGVECTOR_MIGRATION.md)**: Vector search implementation

### Multi-Tenancy & Deployment
- **[docs/MULTI_TENANCY.md](docs/MULTI_TENANCY.md)**: Multi-tenant architecture, Admin APIs, and organization isolation
- **[docs/DOCKER_DEPLOYMENT.md](docs/DOCKER_DEPLOYMENT.md)**: Complete Docker setup for development and production (macOS/Linux)

### Quick References
- **[QUICKSTART_TESTING.md](docs/QUICKSTART_TESTING.md)**: Quick testing setup
- **[IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md)**: Technical implementation details
- **[PHASE_4_COMPLETION_SUMMARY.md](docs/PHASE_4_COMPLETION_SUMMARY.md)**: Recent enhancements

---

## 🏗️ Architecture Overview

### Clean Architecture with DDD

Aynux follows **Clean Architecture** principles with **Domain-Driven Design** (DDD), ensuring scalability, testability, and maintainability.

```mermaid
graph TB
    subgraph "Presentation Layer"
        WA[WhatsApp User] --> Webhook[Webhook Handler]
        API[API Client] --> REST[REST Endpoints]
    end

    subgraph "Application Layer"
        Webhook --> SO[Super Orchestrator]
        REST --> UC[Use Cases]
        SO --> UC
    end

    subgraph "Domain Layer - Bounded Contexts"
        UC --> ECOM[E-commerce Domain]
        UC --> HEALTH[Healthcare Domain]
        UC --> CREDIT[Credit Domain]
        UC --> SHARED[Shared Domain]

        ECOM --> ECOM_ENT[Entities: Product, Order]
        HEALTH --> HEALTH_ENT[Entities: Patient, Appointment]
        CREDIT --> CREDIT_ENT[Entities: Account, Collection]
        SHARED --> SHARED_ENT[Entities: Customer, Knowledge]
    end

    subgraph "Infrastructure Layer"
        ECOM_ENT --> REPO[Repositories]
        HEALTH_ENT --> REPO
        CREDIT_ENT --> REPO
        SHARED_ENT --> REPO

        REPO --> PG[(PostgreSQL + pgvector)]
        REPO --> RD[(Redis Cache)]

        UC --> INT[Integrations]
        INT --> DUX[DUX ERP]
        INT --> OL[Ollama LLM]
        INT --> WS[WhatsApp API]
        INT --> VEC[Vector Stores]
    end

    subgraph "LangGraph Multi-Agent System"
        ECOM --> AGENTS[Domain Agents]
        AGENTS --> PA[Product Agent]
        AGENTS --> CA[Category Agent]
        AGENTS --> SA[Support Agent]
        AGENTS --> TA[Tracking Agent]
    end

    style SO fill:#e1f5fe
    style UC fill:#fff3e0
    style ECOM fill:#c8e6c9
    style HEALTH fill:#f8bbd0
    style CREDIT fill:#ffe0b2
    style SHARED fill:#e1bee7
```

### Clean Architecture Layers

#### 1. **Domain Layer** (`app/domains/`)
Core business logic independent of frameworks and external systems.

- **Bounded Contexts**: `ecommerce/`, `healthcare/`, `credit/`, `shared/`
- **Entities**: Business objects with identity (`Product`, `Customer`, `Order`)
- **Value Objects**: Immutable objects without identity (`Price`, `Email`)
- **Domain Services**: Domain-specific business logic
- **Domain Events**: Business events for cross-domain communication

#### 2. **Application Layer** (`app/domains/*/application/`)
Use Cases that orchestrate domain logic.

- **Use Cases**: Business operations (`SearchProductsUseCase`, `CreateOrderUseCase`)
- **DTOs**: Data Transfer Objects for input/output
- **Ports (Interfaces)**: Abstract interfaces using Python `Protocol`

#### 3. **Infrastructure Layer** (`app/domains/*/infrastructure/`, `app/integrations/`)
External systems, databases, and integrations.

- **Repositories**: Data access implementations (`ProductRepository`)
- **External Services**: API clients (`DuxApiClient`, `WhatsAppService`)
- **Vector Stores**: Semantic search (`PgVectorService`, `ChromaDBService`)
- **LLM Integration**: AI models (`OllamaLLM`)

#### 4. **Presentation Layer** (`app/api/`)
User interfaces and API endpoints.

- **REST API**: FastAPI endpoints with dependency injection
- **Webhooks**: WhatsApp Business API integration
- **GraphQL** (planned): Alternative API interface

### Key Architectural Patterns

- **SOLID Principles**: All code follows Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **Dependency Injection**: `DependencyContainer` wires all dependencies
- **Repository Pattern**: Abstracts data access with `IRepository` protocol
- **Use Case Pattern**: Each business operation is a separate Use Case
- **Protocol (Interfaces)**: Runtime-checkable interfaces for loose coupling
- **Multi-Agent System**: LangGraph orchestrates specialized AI agents
- **Event-Driven**: Domain events for cross-domain communication (planned)

### Prompt Management

Aynux uses a YAML-based system for managing prompts, located in `app/prompts/templates`. This approach allows for easy editing and versioning of prompts without changing the application code.

- **Structure**: Prompts are organized by domain and functionality. For example, a prompt for product search intent is located at `app/prompts/templates/product/search.yaml`.
- **Access**: Prompts are accessed via a key-based system using the `PromptRegistry` class. For example, `PromptRegistry.PRODUCT_SEARCH_INTENT`.
- **Loading**: The `PromptManager` class is responsible for loading prompts from YAML files, caching them in memory, and rendering them with variables.

### Directory Structure

```
app/
├── domains/                    # Domain Layer (DDD Bounded Contexts)
│   ├── ecommerce/             # E-commerce domain
│   │   ├── domain/            # Entities, Value Objects, Domain Services
│   │   │   ├── entities/      # Product, Order, Category
│   │   │   ├── value_objects/ # Price, Discount, SKU
│   │   │   └── services/      # Domain business logic
│   │   ├── application/       # Use Cases and DTOs
│   │   │   ├── use_cases/     # SearchProductsUseCase, CreateOrderUseCase
│   │   │   ├── dto/           # Request/Response DTOs
│   │   │   └── ports/         # Interfaces (IProductRepository)
│   │   └── infrastructure/    # Repositories, External Services
│   │       ├── repositories/  # ProductRepository, OrderRepository
│   │       ├── persistence/   # SQLAlchemy, Redis implementations
│   │       └── services/      # DuxSyncService, ScheduledSyncService
│   ├── healthcare/            # Healthcare domain (same structure)
│   ├── credit/                # Credit domain (same structure)
│   └── shared/                # Shared domain (Customer, Knowledge)
│       └── application/use_cases/  # GetOrCreateCustomerUseCase
│
├── integrations/              # Infrastructure - External Systems
│   ├── llm/                   # Ollama LLM, AI Data Pipeline
│   ├── vector_stores/         # PgVector, ChromaDB, Embeddings
│   ├── whatsapp/              # WhatsApp Business API
│   ├── databases/             # Database connectors
│   └── monitoring/            # LangSmith, Sentry
│
├── core/                      # Core shared infrastructure
│   ├── interfaces/            # IRepository, ILLM, IVectorStore (Protocols)
│   ├── container.py           # DependencyContainer (DI)
│   ├── tenancy/               # Multi-tenant context & isolation
│   │   ├── context.py         # TenantContext (contextvars)
│   │   ├── middleware.py      # TenantContextMiddleware
│   │   ├── resolver.py        # TenantResolver (JWT, Header, WhatsApp)
│   │   ├── vector_store.py    # TenantVectorStore (pgvector filtering)
│   │   └── prompt_manager.py  # TenantPromptManager (4-level hierarchy)
│   ├── agents/                # Agent base classes
│   │   └── base_agent.py      # BaseAgent with process() Template Method
│   ├── shared/                # Shared utilities
│   │   ├── deprecation.py     # @deprecated decorator
│   │   ├── prompt_service.py  # Prompt management
│   │   └── utils/             # Phone normalizer, data extraction
│   └── config/                # Settings, environment variables
│
├── orchestration/             # Super Orchestrator (multi-domain routing)
│   └── super_orchestrator.py  # Routes to domain Use Cases
│
├── api/                       # Presentation Layer (FastAPI)
│   ├── routes/                # REST endpoints
│   ├── dependencies.py        # FastAPI dependency injection
│   └── middleware/            # Auth, logging, CORS
│
├── agents/                    # LangGraph multi-agent system
│   ├── subagent/              # Specialized agents (ProductAgent, etc.)
│   ├── routing/               # Agent routing logic
│   └── schemas/               # Agent state schemas
│
└── services/                  # Legacy services (deprecated)
    ├── [9 deprecated services with @deprecated decorator]
    └── langgraph/             # LangGraph infrastructure services
```

### Benefits of This Architecture

✅ **Testability**: Each layer can be tested independently
✅ **Maintainability**: Clear separation of concerns (SOLID principles)
✅ **Scalability**: Easy to add new domains or features
✅ **Flexibility**: Swap implementations without changing business logic
✅ **Domain Focus**: Business logic is framework-independent
✅ **Team Collaboration**: Different teams can work on different domains

---

## 🧪 Testing

### Run the Test Suite

```bash
# All tests
uv run pytest -v

# Specific test categories
uv run pytest tests/test_pgvector_integration.py -v
uv run pytest tests/test_scenarios.py -v

# Interactive chat testing
python tests/test_chat_interactive.py

# Monitoring dashboard
streamlit run tests/monitoring_dashboard.py
```

### LangSmith Integration

All conversations are automatically traced in LangSmith for debugging and optimization:

1. Configure LangSmith in `.env`:
   ```bash
   LANGSMITH_API_KEY=your_api_key
   LANGSMITH_PROJECT=aynux-production
   LANGSMITH_TRACING_ENABLED=true
   ```

2. View traces at: https://smith.langchain.com

---

## 🛠️ Tech Stack

### Core Technologies
- **Python 3.13**: Modern Python with type hints
- **FastAPI**: High-performance async web framework
- **LangGraph**: Multi-agent conversation orchestration
- **LangChain**: LLM framework and integrations

### AI & Vector Search
- **Ollama**: Local LLM inference (deepseek-r1:7b)
- **pgvector**: PostgreSQL vector similarity search
- **ChromaDB**: Legacy semantic search (being phased out)
- **nomic-embed-text**: 1024-dimension embeddings

### Data & Caching
- **PostgreSQL 14+**: Primary database with pgvector extension
- **Redis 7+**: Multi-layer caching and session management
- **SQLAlchemy 2.0**: Async ORM

### Development Tools
- **UV**: Fast Python package manager
- **Black**: Code formatting
- **Ruff**: Fast Python linter
- **Pytest**: Testing framework

### Monitoring & Observability
- **LangSmith**: LLM observability and debugging
- **Sentry**: Error tracking and monitoring
- **Structured Logging**: JSON-formatted logs

---

## 🗺️ Roadmap

### ✅ Completed
- [x] Multi-domain architecture with super orchestrator
- [x] E-commerce domain with full agent support
- [x] Healthcare and finance domain foundations
- [x] pgvector integration for semantic search
- [x] LangSmith tracing and monitoring
- [x] Comprehensive testing suite
- [x] **Multi-tenancy support with organization isolation**
- [x] **Docker deployment (dev/prod/test environments)**
- [x] **Template Method pattern for agents (BaseAgent.process())**
- [x] **Admin APIs for tenant management**
- [x] **Clean Architecture migration with DDD bounded contexts**

### 🚧 In Progress
- [ ] User-configurable RAG data uploads via UI
- [ ] Enhanced healthcare domain agents
- [ ] Finance domain collection workflows
- [ ] Multi-language support (English, Portuguese)
- [ ] Visual admin dashboard for tenant management

### 📋 Planned
- [ ] Visual conversation flow editor
- [ ] Custom domain creation UI
- [ ] Advanced analytics dashboard
- [ ] Voice message support
- [ ] Multi-channel support (Telegram, Facebook Messenger)
- [ ] Kubernetes deployment manifests
- [ ] GraphQL API interface

---

## ⚙️ Configuration Reference

### Core Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Environment mode (`development`, `production`, `test`) |
| `DEBUG` | `false` | Enable debug mode with verbose logging |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Multi-Tenancy
| Variable | Default | Description |
|----------|---------|-------------|
| `MULTI_TENANT_MODE` | `false` | Enable organization-based tenant isolation |
| `TENANT_HEADER` | `X-Tenant-ID` | HTTP header name for tenant resolution |

### Database
| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `aynux` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | - | Database password (required) |
| `DB_POOL_SIZE` | `20` | Connection pool size |

### Redis
| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |

### LLM & AI
| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_API_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_API_MODEL_SIMPLE` | `deepseek-r1:1.5b` | Fast model for intent analysis |
| `OLLAMA_API_MODEL_COMPLEX` | `deepseek-r1:7b` | Powerful model for complex responses |
| `OLLAMA_API_MODEL_REASONING` | `deepseek-r1:7b` | Deep reasoning model |
| `OLLAMA_API_MODEL_SUMMARY` | `llama3.2:latest` | Fast model for conversation summary |
| `OLLAMA_API_MODEL_EMBEDDING` | `nomic-embed-text` | Embedding model |

### Vector Search
| Variable | Default | Description |
|----------|---------|-------------|
| `USE_PGVECTOR` | `true` | Enable pgvector semantic search |
| `PGVECTOR_SIMILARITY_THRESHOLD` | `0.7` | Minimum similarity score (0.0-1.0) |

### WhatsApp
| Variable | Default | Description |
|----------|---------|-------------|
| `WHATSAPP_ACCESS_TOKEN` | - | WhatsApp Business API token |
| `WHATSAPP_PHONE_NUMBER_ID` | - | Phone number ID |
| `WHATSAPP_VERIFY_TOKEN` | - | Webhook verification token |

### Monitoring
| Variable | Default | Description |
|----------|---------|-------------|
| `LANGSMITH_API_KEY` | - | LangSmith API key for tracing |
| `LANGSMITH_PROJECT` | `aynux` | LangSmith project name |
| `LANGSMITH_TRACING_ENABLED` | `true` | Enable LangSmith tracing |
| `SENTRY_DSN` | - | Sentry DSN for error tracking |

See **[.env.example](.env.example)** for complete configuration options.

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Follow the **[SOLID principles](CLAUDE.md#code-quality--design-principles)** (especially SRP)
4. Write tests for new features
5. Ensure all tests pass: `uv run pytest -v`
6. Format code: `uv run black app && uv run isort app`
7. Commit changes: `git commit -m 'feat: Add amazing feature'`
8. Push to branch: `git push origin feature/amazing-feature`
9. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **LangChain/LangGraph**: For the excellent multi-agent framework
- **FastAPI**: For the high-performance web framework
- **Ollama**: For making local LLM inference easy
- **pgvector**: For bringing vector search to PostgreSQL

---

## 📞 Support

- **Documentation**: See the [docs/](docs/) directory
- **Issues**: [GitHub Issues](https://github.com/your-username/aynux/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/aynux/discussions)

---

<div align="center">

**Built with ❤️ using AI-powered development**

[Report Bug](https://github.com/Excelencia-Digital-Soft/aynux/issues) • [Request Feature](https://github.com/Excelencia-Digital-Soft/aynux/issues) • [Documentation](docs/)

</div>
