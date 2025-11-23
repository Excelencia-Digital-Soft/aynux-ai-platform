# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Aynux** is a multi-domain WhatsApp bot platform built with FastAPI and LangGraph multi-agent system. The system uses a sophisticated orchestrator architecture to handle different business domains through specialized, configurable agents. Each domain can be independently configured with its own agents, RAG knowledge base, and business logic.

### Key Characteristics
- **Multi-Domain Architecture**: Support for multiple business domains (e-commerce, healthcare, finance, etc.)
- **Configurable Agents**: Each domain has specialized agents that can be configured per deployment
- **Super Orchestrator**: Intelligent routing system that directs conversations to appropriate domain services
- **RAG-Enabled**: Vector search and semantic understanding for each domain's knowledge base
- **User-Configurable**: Future support for users to upload custom RAG data and configure agent behavior

### Current Implemented Domains
- **E-commerce**: Product catalog, orders, promotions, customer support
- **Healthcare** (Hospital): Patient management, appointments, medical records
- **Finance** (Credit): Account management, collections, payment processing

## Documentation

**IMPORTANT**: Before making any changes, review the comprehensive documentation in the `docs/` directory:

- **docs/LangGraph.md**: Complete LangGraph implementation guide and architecture
- **docs/9_agent_supervisor.md**: Supervisor-agent pattern and orchestration
- **docs/TESTING_GUIDE.md**: Testing strategy and best practices
- **docs/PGVECTOR_MIGRATION.md**: Vector search implementation with pgvector
- **docs/IMPLEMENTATION_SUMMARY.md**: ChromaDB to pgvector migration details
- **docs/PHASE_4_COMPLETION_SUMMARY.md**: Recent system enhancements
- **docs/QUICKSTART_TESTING.md**: Quick testing setup guide

All major architectural decisions, patterns, and implementation details are documented in these files.

## Development Commands

### Using UV (Preferred)
- **Start development server**: `./dev-uv.sh` → option 2, or `uv run --with uvicorn uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- **Install dependencies**: `uv sync`
- **Run code formatting**: `uv run black app && uv run isort app && uv run ruff check app --fix`
- **Run tests**: `uv run pytest -v`
- **Update dependencies**: `uv lock --upgrade && uv sync`

### Testing Individual Components
- **Chat endpoint test**: `python test_chat_endpoint.py`
- **Graph system test**: `python test_graph_simple.py`
- **Language detection test**: `python test_language_detector.py`

### Database Operations
- **View product statistics**: `PGPASSWORD="" psql -h localhost -U enzo -d aynux -c "SELECT c.display_name as categoria, COUNT(p.id) as total_productos FROM categories c LEFT JOIN products p ON c.id = p.category_id GROUP BY c.display_name;"`
- **Run database migrations**: Check `app/scripts/` directory for SQL migration files

## Architecture Overview

### Clean Architecture with Domain-Driven Design (DDD)

**Aynux** follows **Clean Architecture** principles with **Domain-Driven Design** (DDD), ensuring SOLID compliance, testability, and scalability.

### Core System Architecture (Clean Architecture Layers)

The application is organized into **4 main layers** following the Dependency Rule (dependencies point inward):

#### 1. **Domain Layer** (`app/domains/*/domain/`)
The innermost layer containing core business logic, completely independent of frameworks and external systems.

- **Bounded Contexts**: `ecommerce/`, `healthcare/`, `credit/`, `shared/`
- **Entities**: Business objects with identity and lifecycle (`Product`, `Customer`, `Order`, `Patient`)
- **Value Objects**: Immutable objects without identity (`Price`, `Email`, `PhoneNumber`)
- **Domain Services**: Complex business logic that doesn't belong to entities
- **Domain Events**: Business events for cross-domain communication (planned)

#### 2. **Application Layer** (`app/domains/*/application/`)
Orchestrates domain logic through **Use Cases** and defines interfaces for external dependencies.

- **Use Cases**: Single-responsibility business operations (`SearchProductsUseCase`, `CreateOrderUseCase`, `GetOrCreateCustomerUseCase`)
- **DTOs (Data Transfer Objects)**: Input/output data structures for Use Cases
- **Ports (Interfaces)**: Abstract interfaces using Python `Protocol` (`IProductRepository`, `ILLM`, `IVectorStore`)
- **Dependency Injection**: All dependencies injected via `DependencyContainer`

#### 3. **Infrastructure Layer** (`app/domains/*/infrastructure/`, `app/integrations/`, `app/core/`)
Concrete implementations of interfaces, external systems integration, and persistence.

**Domain-Specific Infrastructure** (`app/domains/*/infrastructure/`):
- **Repositories**: Data access implementations (`ProductRepository`, `CustomerRepository`)
- **Persistence**: SQLAlchemy models, Redis cache
- **External Services**: Domain-specific external integrations (`DuxSyncService`, `ScheduledSyncService`)
- **Vector Stores**: Domain-specific semantic search collections

**Shared Infrastructure** (`app/integrations/`, `app/core/`):
- **LLM Integration** (`app/integrations/llm/`): `OllamaLLM`, `AiDataPipelineService`
- **Vector Stores** (`app/integrations/vector_stores/`): `PgVectorService`, `KnowledgeEmbeddingService`, `EmbeddingUpdateService`
- **WhatsApp Integration** (`app/integrations/whatsapp/`): `WhatsAppService`, `WhatsAppFlowsService`, `WhatsAppCatalogService`
- **Databases** (`app/integrations/databases/`): Database connectors
- **Monitoring** (`app/integrations/monitoring/`): LangSmith, Sentry
- **Core Shared** (`app/core/`): `DependencyContainer`, interfaces (`IRepository`, `ILLM`), utilities

#### 4. **Presentation Layer** (`app/api/`)
User interfaces, API endpoints, and webhooks.

- **REST API**: FastAPI endpoints with dependency injection
- **Webhooks**: WhatsApp Business API webhook handlers
- **Middleware**: Authentication, logging, CORS
- **Dependencies**: FastAPI dependency injection integration with `DependencyContainer`

### Multi-Agent System (LangGraph)
The core intelligence is built around a **multi-domain orchestration pattern**:

1. **Super Orchestrator** (`app/orchestration/super_orchestrator.py`):
   - Analyzes incoming messages to identify business domain
   - Routes conversations to appropriate domain Use Cases
   - Manages cross-domain context and state transitions
   - Supports dynamic domain configuration

2. **Domain Services** (each with specialized agents):
   - **EcommerceDomainService**: Product catalog, orders, promotions, support
   - **HospitalDomainService**: Patient management, appointments, medical records
   - **CreditDomainService**: Account management, collections, payments

3. **Specialized Agents** (`app/agents/subagent/`):
   - `product_agent.py`: Product queries and catalog search (e-commerce)
   - `category_agent.py`: Product category management (e-commerce)
   - `promotions_agent.py`: Deals and offers (e-commerce)
   - `tracking_agent.py`: Order tracking (e-commerce)
   - `support_agent.py`: Customer support (multi-domain)
   - `invoice_agent.py`: Billing and payments (multi-domain)
   - `fallback_agent.py`: Default responses when intent unclear
   - `farewell_agent.py`: Conversation closing

4. **Graph Orchestration** (`app/agents/graph.py`):
   - `AynuxGraph`: Main graph coordinator (simplified multi-domain)
   - Uses LangGraph StateGraph with TypedDict state schema
   - PostgreSQL checkpointing for conversation persistence
   - Conditional routing between agents and domains

5. **Documentation** (`docs/*.md`):
   - **docs/LangGraph.md**: Complete LangGraph implementation guide
   - **docs/9_agent_supervisor.md**: Supervisor-agent architecture patterns
   - **docs/FINAL_MIGRATION_SUMMARY.md**: Clean Architecture migration summary

### Dependency Injection (DI)

**DependencyContainer** (`app/core/container.py`) is the central DI container that wires all dependencies:

```python
from app.core.container import DependencyContainer

container = DependencyContainer()

# Create Use Cases with all dependencies injected
search_products_uc = container.create_search_products_use_case()
get_customer_uc = container.create_get_or_create_customer_use_case()

# Use Cases automatically receive repositories, services, and integrations
result = await search_products_uc.execute(query="laptop gaming")
```

**FastAPI Integration** (`app/api/dependencies.py`):

```python
from fastapi import Depends
from app.api.dependencies import get_search_products_use_case

@router.get("/products/search")
async def search_products(
    query: str,
    use_case: SearchProductsUseCase = Depends(get_search_products_use_case)
):
    """Dependencies automatically injected via DependencyContainer"""
    result = await use_case.execute(query=query)
    return result
```

### State Management
- **LangGraphState** (`app/agents/state_schema.py`): TypedDict for maximum performance
- **Pydantic Models** (`app/agents/schemas/`): Type-safe data validation
- **StateManager**: Bridges between TypedDict and Pydantic models

### Key Integrations
- **AI Models**: Ollama local LLM (typically `deepseek-r1:7b`)
- **Vector Store**: pgvector (primary) + ChromaDB (legacy) for semantic search
- **Database**: PostgreSQL for persistent data, Redis for caching
- **External APIs**: WhatsApp Business API, DUX ERP system
- **Background Sync**: Automated DUX → PostgreSQL → RAG pipeline
- **Monitoring**: LangSmith tracing and Sentry error tracking

## DUX-RAG Integration System (E-commerce Domain)

### Automated Background Synchronization
The e-commerce domain automatically synchronizes data from DUX ERP to PostgreSQL and vector databases:

> **Note**: This integration is specific to the e-commerce domain. Other domains can implement similar RAG integrations with their respective data sources. Future versions will support user-configurable RAG data uploads.

**Pipeline Flow**: `DUX API → PostgreSQL → Vector Embeddings → pgvector/ChromaDB`

**Key Services** (New Architecture Locations):
- **DuxRagSyncService** (`app/domains/ecommerce/infrastructure/services/dux_rag_sync_service.py`): Integrated sync DB + RAG
- **ScheduledSyncService** (`app/domains/ecommerce/infrastructure/services/scheduled_sync_service.py`): Background automation
- **EmbeddingUpdateService** (`app/integrations/vector_stores/embedding_update_service.py`): Vector processing
- **KnowledgeEmbeddingService** (`app/integrations/vector_stores/knowledge_embedding_service.py`): Knowledge base embeddings

**Synchronization Schedule**:
- **Automatic**: Every 12 hours (2:00 AM, 2:00 PM)
- **Force Threshold**: 24 hours (forces sync if data older than 24h)
- **Manual**: Available via API endpoints

### Admin API Endpoints
Monitor and control synchronization via REST API:

- **GET** `/api/v1/admin/dux/sync/status` - Complete sync status
- **POST** `/api/v1/admin/dux/sync/force` - Force immediate sync
- **GET** `/api/v1/admin/dux/sync/health` - System health check
- **GET** `/api/v1/admin/dux/sync/metrics` - Performance metrics

### Configuration
Essential DUX sync settings in `.env`:
```bash
# DUX API Configuration
DUX_API_BASE_URL=https://erp.duxsoftware.com.ar/WSERP/rest/services
DUX_API_KEY=your_dux_api_key
DUX_API_TIMEOUT=30

# Sync Configuration
DUX_SYNC_ENABLED=true
DUX_SYNC_HOURS=2,14  # 2:00 AM, 2:00 PM
DUX_SYNC_BATCH_SIZE=50
DUX_FORCE_SYNC_THRESHOLD_HOURS=24
```

### Testing the Integration
Create all test into folder test
Run the integration test:
```bash
python tests/test_dux_rag_integration.py
```

### Data Flow Architecture
1. **DUX API**: Products, invoices, categories fetched via HTTP clients
2. **PostgreSQL Storage**: Structured data with relationships and indexes
3. **Vector Processing**: Products converted to embeddings using Ollama (`nomic-embed-text`)
4. **ChromaDB Storage**: Semantic search capabilities for AI agents
5. **Agent Access**: Real-time semantic search during conversations

## Key Configuration Files

### Environment Variables (.env)
Essential settings include:
- **Database**: `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- **Redis**: `REDIS_HOST`, `REDIS_PORT`
- **AI**: `OLLAMA_API_MODEL`, `OLLAMA_API_URL`
- **WhatsApp**: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`
- **DUX ERP**: `DUX_API_BASE_URL`, `DUX_API_KEY`
- **LangSmith**: `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`

### Python Configuration (pyproject.toml)
- Uses Python 3.13+ with uv as primary package manager
- Code formatting: Black (line length 120), isort, Ruff
- Main dependencies: FastAPI, LangGraph, LangChain, SQLAlchemy, Redis

## Code Quality & Design Principles

**CRITICAL**: All new code MUST follow these principles. They are non-negotiable standards for this project.

### SOLID Principles

#### 1. **Single Responsibility Principle (SRP)** ⭐ MANDATORY
**Definition**: A class should have one, and only one, reason to change. Each class/function should do ONE thing well.

**Requirements**:
- ✅ **One responsibility per class**: Each class should handle ONE aspect of functionality
- ✅ **Clear naming**: Class names should clearly indicate their single responsibility
- ✅ **Small functions**: Functions should do ONE thing (typically <20 lines)
- ✅ **Separation of concerns**: Separate data access, business logic, and presentation
- ❌ **God classes**: Never create classes that do everything
- ❌ **Mixed responsibilities**: Don't mix data validation with business logic with data access

**Examples in this project**:
```python
# ✅ GOOD: Single responsibility
class ProductRepository:
    """Handles ONLY data access for products"""
    async def get_by_id(self, product_id: int) -> Product: ...
    async def save(self, product: Product) -> Product: ...

class ProductValidator:
    """Handles ONLY validation logic for products"""
    def validate_price(self, price: float) -> bool: ...
    def validate_stock(self, stock: int) -> bool: ...

class ProductService:
    """Handles ONLY business logic for products"""
    def __init__(self, repo: ProductRepository, validator: ProductValidator):
        self.repo = repo
        self.validator = validator

    async def create_product(self, data: dict) -> Product:
        if not self.validator.validate_price(data['price']):
            raise ValueError("Invalid price")
        return await self.repo.save(Product(**data))

# ❌ BAD: Multiple responsibilities
class ProductManager:
    """Does everything - violates SRP"""
    async def get_product(self, id: int): ...  # Data access
    def validate_price(self, price: float): ...  # Validation
    async def send_email(self, product: Product): ...  # Email logic
    def calculate_discount(self, price: float): ...  # Business logic
```

**When to split a class**:
- If you use "and" to describe what it does → Split it
- If it has more than one reason to change → Split it
- If it's difficult to name clearly → Split it
- If it exceeds 200 lines → Likely needs splitting

#### 2. **Open/Closed Principle (OCP)**
**Definition**: Software entities should be open for extension, but closed for modification.

**Implementation**:
- Use abstract base classes for extensibility
- Use composition over inheritance
- Design for plugin-like architecture (e.g., domain services)

**Example**:
```python
# ✅ GOOD: Open for extension via inheritance
class BaseAgent(ABC):
    @abstractmethod
    async def _process_internal(self, state: dict) -> dict:
        """Subclasses extend behavior without modifying base"""
        pass

# New agent types extend without modifying BaseAgent
class ProductAgent(BaseAgent):
    async def _process_internal(self, state: dict) -> dict:
        # Custom implementation
        pass
```

#### 3. **Liskov Substitution Principle (LSP)**
**Definition**: Objects of a superclass should be replaceable with objects of a subclass without breaking the application.

**Implementation**:
- Subclasses must honor parent class contracts
- Don't strengthen preconditions or weaken postconditions
- All agents inherit from `BaseAgent` and can be used interchangeably

#### 4. **Interface Segregation Principle (ISP)**
**Definition**: Clients should not be forced to depend on interfaces they don't use.

**Implementation**:
- Use Protocol classes for small, focused interfaces
- Don't create fat interfaces with many methods
- Prefer many small interfaces over one large interface

#### 5. **Dependency Inversion Principle (DIP)**
**Definition**: High-level modules should not depend on low-level modules. Both should depend on abstractions.

**Implementation**:
- Use dependency injection (FastAPI's `Depends`)
- Depend on abstract base classes, not concrete implementations
- Use repository pattern for data access

**Example**:
```python
# ✅ GOOD: Depends on abstraction
class ProductService:
    def __init__(self, repo: ProductRepository):  # Abstract interface
        self.repo = repo

# ❌ BAD: Depends on concrete implementation
class ProductService:
    def __init__(self):
        self.db = PostgreSQL()  # Concrete implementation
```

### Additional Code Quality Rules

#### DRY (Don't Repeat Yourself)
- Extract common logic into reusable functions/classes
- Use base classes for shared behavior (e.g., `BaseAgent`)
- Create utility modules for common operations

#### KISS (Keep It Simple, Stupid)
- Prefer simple solutions over complex ones
- Avoid premature optimization
- Write code for humans first, computers second

#### YAGNI (You Aren't Gonna Need It)
- Don't add functionality until it's needed
- Avoid speculative generality
- Focus on current requirements

### Code Organization Standards

**File Structure** (Clean Architecture with DDD):
```
app/
  domains/                    # Domain Layer - Bounded Contexts (DDD)
    ecommerce/               # E-commerce bounded context
      domain/                # Core business logic (framework-independent)
        entities/            # Business objects with identity (Product, Order)
        value_objects/       # Immutable objects (Price, SKU, Discount)
        services/            # Domain services (business logic)
        events/              # Domain events (future)
      application/           # Application Layer - Use Cases
        use_cases/           # Single-responsibility operations (SearchProductsUseCase)
        dto/                 # Data Transfer Objects (input/output)
        ports/               # Interfaces using Protocol (IProductRepository)
      infrastructure/        # Infrastructure implementations
        repositories/        # Data access (ProductRepository)
        persistence/         # SQLAlchemy models, Redis
        services/            # External services (DuxSyncService)
        vector/              # Vector store implementations
      agents/                # LangGraph agents for this domain
      api/                   # Domain-specific API routes (optional)

    healthcare/              # Healthcare bounded context (same structure)
    credit/                  # Credit bounded context (same structure)
    shared/                  # Shared domain (Customer, Knowledge)
      application/use_cases/ # GetOrCreateCustomerUseCase, SearchKnowledgeUseCase

  integrations/              # Infrastructure - External Systems
    llm/                     # Ollama LLM, AI Data Pipeline
    vector_stores/           # PgVector, ChromaDB, Embeddings
    whatsapp/                # WhatsApp Business API
    databases/               # Database connectors
    monitoring/              # LangSmith, Sentry

  core/                      # Core shared infrastructure
    interfaces/              # Abstract interfaces (IRepository, ILLM, IVectorStore)
    container.py             # DependencyContainer (DI)
    shared/                  # Shared utilities
      deprecation.py         # @deprecated decorator
      prompt_service.py      # Prompt management
      utils/                 # Phone normalizer, data extraction
    config/                  # Settings, environment variables

  orchestration/             # Super Orchestrator (multi-domain routing)
    super_orchestrator.py    # Routes to domain Use Cases

  api/                       # Presentation Layer (FastAPI)
    routes/                  # REST endpoints (thin controllers)
    dependencies.py          # FastAPI DI → DependencyContainer
    middleware/              # Auth, logging, CORS

  agents/                    # LangGraph multi-agent system
    subagent/                # Specialized agents (ProductAgent, SupportAgent)
    routing/                 # Agent routing logic
    schemas/                 # Agent state schemas (TypedDict)

  services/                  # Legacy services (deprecated)
    [9 deprecated services]  # Marked with @deprecated decorator
    langgraph/               # LangGraph infrastructure services (kept)
```

**Key Principles**:
- **Dependency Rule**: Dependencies point inward (Presentation → Application → Domain)
- **One Responsibility**: Each file/class has a single, clear responsibility (SRP)
- **Domain Independence**: Domain layer has NO dependencies on infrastructure or frameworks
- **Explicit Interfaces**: Use `Protocol` for all abstractions (ports)
- **Dependency Injection**: All dependencies injected via `DependencyContainer`
```

**Naming Conventions**:
- Classes: `PascalCase` and noun-based (`ProductService`, `UserRepository`)
- Functions: `snake_case` and verb-based (`get_product`, `validate_email`)
- Constants: `UPPER_SNAKE_CASE` (`MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- Private methods: `_leading_underscore` (`_process_internal`)

**Function Size**:
- Target: <20 lines per function
- Maximum: 50 lines (if exceeded, must justify or refactor)
- One level of abstraction per function

**Class Size**:
- Target: <200 lines per class
- Maximum: 500 lines (if exceeded, must split into multiple classes)

### Code Review Checklist

Before committing new code, verify:
- [ ] **SRP**: Does each class have a single, clear responsibility?
- [ ] **Naming**: Are names clear and describe the single purpose?
- [ ] **Function size**: Are functions small (<20 lines) and focused?
- [ ] **Dependencies**: Are dependencies injected, not hardcoded?
- [ ] **Testing**: Can each component be tested independently?
- [ ] **Documentation**: Is the single responsibility documented in docstring?
- [ ] **Error handling**: Are errors handled at the appropriate level?
- [ ] **Type hints**: Are all function signatures typed?

## Development Patterns

### Use Case Development (Clean Architecture)

When adding new business operations:

1. **Create Use Case** in `app/domains/{domain}/application/use_cases/`:
```python
from app.domains.ecommerce.application.ports import IProductRepository

class CreateOrderUseCase:
    """
    Use Case: Create a new order

    Follows SRP - single responsibility for order creation logic.
    """

    def __init__(self, repository: IProductRepository):
        """Dependencies injected via DependencyContainer"""
        self.repository = repository

    async def execute(self, user_id: str, items: List[OrderItem]) -> OrderResult:
        """Business logic for creating an order"""
        # Validation
        # Domain logic
        # Persistence via repository
        return OrderResult(...)
```

2. **Define Interface (Port)** in `app/domains/{domain}/application/ports/`:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class IProductRepository(Protocol):
    """Interface for product data access"""
    async def get_by_id(self, product_id: int) -> Optional[Product]: ...
    async def search(self, query: str) -> List[Product]: ...
```

3. **Implement Repository** in `app/domains/{domain}/infrastructure/repositories/`:
```python
from app.domains.ecommerce.application.ports import IProductRepository

class ProductRepository(IProductRepository):
    """SQLAlchemy implementation of IProductRepository"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        # SQLAlchemy implementation
        pass
```

4. **Register in DependencyContainer** (`app/core/container.py`):
```python
def create_create_order_use_case(self) -> CreateOrderUseCase:
    """Factory method for CreateOrderUseCase"""
    repository = self.create_product_repository()
    return CreateOrderUseCase(repository=repository)
```

5. **Add FastAPI Dependency** (`app/api/dependencies.py`):
```python
def get_create_order_use_case() -> CreateOrderUseCase:
    """FastAPI dependency for CreateOrderUseCase"""
    container = DependencyContainer()
    return container.create_create_order_use_case()
```

6. **Use in API Endpoint** (`app/api/routes/`):
```python
@router.post("/orders")
async def create_order(
    request: CreateOrderRequest,
    use_case: CreateOrderUseCase = Depends(get_create_order_use_case)
):
    """Endpoint uses Use Case via dependency injection"""
    result = await use_case.execute(
        user_id=request.user_id,
        items=request.items
    )
    return result
```

### Domain Development (DDD)

When adding new business domains:

1. **Create Domain Structure**:
```bash
app/domains/my_domain/
├── domain/
│   ├── entities/          # Business objects (MyEntity)
│   ├── value_objects/     # Immutable values
│   ├── services/          # Domain services
│   └── events/            # Domain events
├── application/
│   ├── use_cases/         # Business operations
│   ├── dto/               # Data Transfer Objects
│   └── ports/             # Interfaces (IMyRepository)
├── infrastructure/
│   ├── repositories/      # Data access implementations
│   ├── persistence/       # SQLAlchemy models
│   └── services/          # External services
└── agents/                # LangGraph agents
```

2. **Define Entities** (`domain/entities/`):
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MyEntity:
    """Domain entity with business logic"""
    id: int
    name: str
    created_at: datetime

    def business_method(self) -> bool:
        """Business logic lives in entity"""
        return True
```

3. **Create Use Cases** for each operation
4. **Register in SuperOrchestrator** for multi-domain routing
5. **Configure domain settings** in `.env` and `settings.py`

### Agent Development (LangGraph)

When creating new agents:

1. Extend `BaseAgent` from `app/agents/subagent/base_agent.py`
2. Implement `_process_internal()` method
3. Add agent to `AgentType` enum in `app/agents/schemas/`
4. Register in `AynuxGraph._init_agents()` or appropriate domain service
5. Add routing logic to supervisor or super orchestrator
6. Configure domain-specific behavior in settings

### API Endpoint Development

**Use Dependency Injection** (not direct instantiation):

```python
# ✅ GOOD: Dependency Injection
from fastapi import Depends
from app.api.dependencies import get_search_products_use_case

@router.get("/products/search")
async def search_products(
    query: str,
    use_case: SearchProductsUseCase = Depends(get_search_products_use_case)
):
    result = await use_case.execute(query=query)
    return result

# ❌ BAD: Direct instantiation
@router.get("/products/search")
async def search_products(query: str):
    use_case = SearchProductsUseCase()  # Don't do this!
    result = await use_case.execute(query=query)
    return result
```

**Follow Clean Architecture Layers**:
- **Controller (API)**: Thin layer, delegates to Use Cases
- **Use Case**: Business logic orchestration
- **Repository**: Data access only
- **Entity**: Domain business rules

### Migration from Legacy Services

When migrating from deprecated services to new architecture:

1. **Identify the deprecated service** (has `@deprecated` decorator)
2. **Read migration guide** in deprecation message
3. **Find/Create corresponding Use Case**
4. **Update imports**:
   ```python
   # Before (deprecated):
   from app.services.product_service import ProductService
   service = ProductService()
   result = await service.search_products(query)

   # After (new architecture):
   from app.domains.ecommerce.application.use_cases import SearchProductsUseCase
   from app.core.container import DependencyContainer

   container = DependencyContainer()
   use_case = container.create_search_products_use_case()
   result = await use_case.execute(query=query)
   ```
5. **Use dependency injection** in FastAPI endpoints
6. **Remove deprecated service** imports once migration complete

## Testing Strategy

### Test Categories
- **Unit tests**: Individual component testing (pytest)
- **Integration tests**: Multi-component interaction tests
- **E2E tests**: Full conversation flow tests (`test_chat_endpoint.py`)
- **Performance tests**: Agent response time and throughput

## Database Schema

### Core Tables (Multi-Domain)
- **products**: Product catalog with embeddings for semantic search (e-commerce domain)
- **categories**: Product categorization (e-commerce domain)
- **conversations**: Chat history and context (all domains)
- **orders**: Transaction records (e-commerce domain)
- **promotions**: Marketing offers and discounts (e-commerce domain)
- **patients**: Patient records (healthcare domain)
- **appointments**: Medical appointments (healthcare domain)
- **accounts**: Financial accounts (credit domain)
- **collections**: Collection records (credit domain)

### Vector Search (pgvector + ChromaDB)
- **pgvector**: PostgreSQL extension for vector similarity search
  - Native SQL integration with HNSW indexing
  - Product embeddings stored directly in database
  - See **docs/PGVECTOR_MIGRATION.md** for implementation details
- **ChromaDB**: Legacy semantic search (being phased out)
  - Collections for domain-specific semantic search
  - Automatic embedding updates via `embedding_update_service.py`
- **Embedding models**: `nomic-embed-text` (1024 dimensions) via Ollama
- **Migration**: Ongoing transition from ChromaDB to pgvector for better performance

## Error Handling & Monitoring

### Logging Strategy
- Structured logging throughout application
- Agent-specific log levels and formatting
- Performance metrics collection
- LangSmith tracing for conversation analysis

### Error Recovery
- Circuit breaker patterns for external API calls
- Graceful degradation when AI models unavailable
- Fallback agents for unhandled intents
- Rate limiting and request validation

## Deployment Notes

### Required Services
- PostgreSQL database
- Redis server
- Ollama with required models
- ChromaDB (embedded mode)

### Production Considerations
- Set `ENVIRONMENT=production` in .env
- Configure proper database connection pooling
- Enable Sentry for error tracking
- Set up LangSmith for conversation monitoring
- Configure rate limiting for WhatsApp webhook
