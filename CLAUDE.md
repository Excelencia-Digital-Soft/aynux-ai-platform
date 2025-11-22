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

### Core System Architecture
The application follows a multi-layer architecture:
- **API Layer**: FastAPI with route handlers in `app/api/routes/`
- **Service Layer**: Business logic in `app/services/`
- **Agent Layer**: LangGraph multi-agent system in `app/agents/`
- **Data Layer**: SQLAlchemy models, PostgreSQL database, and Redis cache
- **Integration Layer**: External APIs (WhatsApp, DUX ERP, Ollama AI)

### Multi-Agent System (LangGraph)
The core intelligence is built around a multi-domain orchestration pattern:

1. **Super Orchestrator** (`app/services/super_orchestrator_service.py`):
   - Analyzes incoming messages to identify business domain
   - Routes conversations to appropriate domain services
   - Manages cross-domain context and state transitions
   - Supports dynamic domain configuration

2. **Domain Services** (each with specialized agents):
   - **EcommerceDomainService**: Product catalog, orders, promotions, support
   - **HospitalDomainService**: Patient management, appointments, medical records
   - **CreditDomainService**: Account management, collections, payments

3. **Specialized Agents** (examples from `app/agents/subagent/`):
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

5. **Documentation** (docs/*.md):
   - **docs/LangGraph.md**: Complete LangGraph implementation guide
   - **docs/9_agent_supervisor.md**: Supervisor-agent architecture patterns

### State Management
- **LangGraphState** (`app/agents/state_schema.py`): TypedDict for maximum performance
- **Pydantic Models** (`app/agents/schemas/`): Type-safe data validation
- **StateManager**: Bridges between TypedDict and Pydantic models

### Key Integrations
- **AI Models**: Ollama local LLM (typically `deepseek-r1:7b`)
- **Vector Store**: ChromaDB for semantic search with automatic embeddings
- **Database**: PostgreSQL for persistent data, Redis for caching
- **External APIs**: WhatsApp Business API, DUX ERP system
- **Background Sync**: Automated DUX → PostgreSQL → RAG pipeline
- **Monitoring**: LangSmith tracing and Sentry error tracking

## DUX-RAG Integration System (E-commerce Domain)

### Automated Background Synchronization
The e-commerce domain automatically synchronizes data from DUX ERP to PostgreSQL and vector databases:

> **Note**: This integration is specific to the e-commerce domain. Other domains can implement similar RAG integrations with their respective data sources. Future versions will support user-configurable RAG data uploads.

**Pipeline Flow**: `DUX API → PostgreSQL → Vector Embeddings → ChromaDB`

**Key Services**:
- **DuxRagSyncService** (`app/services/dux_rag_sync_service.py`): Integrated sync DB + RAG
- **ScheduledSyncService** (`app/services/scheduled_sync_service.py`): Background automation
- **EmbeddingUpdateService** (`app/services/embedding_update_service.py`): Vector processing

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

**File Structure**:
```
app/
  api/          # API routes (thin controllers)
  services/     # Business logic (SRP: one service per domain)
  repositories/ # Data access (SRP: one repo per model)
  models/       # Database models (SRP: one model per table)
  schemas/      # Pydantic schemas (SRP: one schema per use case)
  agents/       # LangGraph agents (SRP: one agent per intent)
  utils/        # Utility functions (SRP: grouped by purpose)
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

### Agent Development
When creating new agents:
1. Extend `BaseAgent` from `app/agents/subagent/base_agent.py`
2. Implement `_process_internal()` method
3. Add agent to `AgentType` enum in `app/agents/schemas/`
4. Register in `AynuxGraph._init_agents()` or appropriate domain service
5. Add routing logic to supervisor or super orchestrator
6. Configure domain-specific behavior in settings

### Domain Development
When adding new business domains:
1. Create domain service class (e.g., `MyDomainService`) extending base service
2. Define domain-specific agents and their routing logic
3. Register domain in `SuperOrchestratorService`
4. Configure domain settings in `.env` and `settings.py`
5. Add domain-specific RAG data and vector collections
6. Update API routes and webhooks for domain routing

### API Endpoint Development
- Use FastAPI dependency injection via `app/api/dependencies.py`
- Follow existing patterns in `app/api/routes/`
- Pydantic models for request/response validation in `app/models/`
- Repository pattern for data access in `app/repositories/`

### Service Layer Patterns
- Async/await throughout
- Error handling with structured logging
- Redis caching for frequently accessed data
- Database transactions via SQLAlchemy async sessions

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
