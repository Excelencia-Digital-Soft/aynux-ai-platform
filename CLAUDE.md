# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Server
```bash
# Start the development server
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the development script
./dev.sh  # Select option 2
```

### Code Quality
```bash
# Format code with Black
poetry run black app

# Sort imports
poetry run isort app

# Run linter
poetry run ruff check app --fix

# Run all checks at once
./dev.sh  # Select option 3
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=app

# Run specific test file
poetry run pytest tests/test_phone_normalizer_pydantic.py
```

### Database Operations
```bash
# Initialize database
poetry run python app/scripts/init_database.py

# Initialize LangGraph system
poetry run python app/scripts/init_langgraph_system.py
```

### Dependency Management
```bash
# Install dependencies
poetry install

# Add a new dependency
poetry add package-name

# Add a dev dependency
poetry add --group dev package-name

# Update dependencies
poetry update
```

## Architecture Overview

This is a WhatsApp-based conversational commerce bot with two parallel architectures:

### 1. Traditional Architecture (ChatbotService)
- Linear message processing through individual agents
- Redis/DB for state management
- Single agent per message approach
- Located in `app/services/chatbot_service.py`

### 2. LangGraph Multi-Agent System (Recommended)
- Graph-based multi-agent orchestration
- PostgreSQL checkpointing for conversation persistence
- Intelligent routing with pattern matching + LLM
- Located in `app/agents/langgraph_system/`

### Key Components

**API Layer** (`app/api/`)
- FastAPI application with WhatsApp webhook integration
- JWT authentication middleware
- Routes for webhook, auth, products, and embeddings

**Services** (`app/services/`)
- `langgraph_chatbot_service.py`: Main LangGraph orchestrator
- `chatbot_service.py`: Traditional service (fallback)
- `whatsapp_service.py`: WhatsApp API integration
- `ai_service.py`: Gemini AI integration
- `product_service.py` & `enhanced_product_service.py`: Product management
- `vector_service.py`: ChromaDB vector search

**LangGraph System** (`app/agents/langgraph_system/`)
- `supervisor.py`: Main orchestration logic
- `router.py`: Intent routing system
- `agents/`: Specialized agents (category, product, promotions, tracking, support, invoice)
- `integrations/`: External service integrations (Ollama, ChromaDB, PostgreSQL)
- `monitoring/`: Security and monitoring components

**Database** (`app/database/`)
- Async PostgreSQL integration with SQLAlchemy
- Models for users, conversations, messages, products

## Configuration

### Environment Variables
The system uses `app/config/settings.py` for configuration. Key variables:
- `USE_LANGGRAPH`: Enable/disable LangGraph system (default: true)
- `DATABASE_URL`: PostgreSQL connection string
- `WHATSAPP_ACCESS_TOKEN` & `WHATSAPP_VERIFY_TOKEN`: WhatsApp API credentials
- `GEMINI_API_KEY`: Google Gemini AI key
- `OLLAMA_API_URL` & `OLLAMA_MODEL`: Local LLM configuration
- `REDIS_URL`: Redis connection (optional)

### LangGraph Configuration
See `app/config/langgraph_config.py` for detailed agent configuration options.

## Important Implementation Details

### WhatsApp Integration
- Webhook endpoint: `/api/v1/webhook/`
- Handles both message reception and status updates
- Automatic service selection based on `USE_LANGGRAPH` setting
- Fallback mechanism if LangGraph initialization fails

### State Management
- LangGraph uses `SharedState` with PostgreSQL checkpointing
- Traditional system uses Redis for session management
- Both systems maintain compatibility with the same database schema

### Intent Routing
The LangGraph system uses a hybrid approach:
1. Fast pattern matching for common intents
2. LLM-based analysis for complex queries
3. Entity extraction for order numbers, prices, brands, etc.
4. Confidence scoring for routing decisions

### Agent Capabilities
- **Category Agent**: Product category navigation and filtering
- **Product Agent**: Detailed product queries, stock checking, comparisons
- **Promotions Agent**: Current offers and discount information
- **Tracking Agent**: Order status and delivery updates
- **Support Agent**: FAQ and technical assistance
- **Invoice Agent**: Billing and payment queries

### Error Handling
- Comprehensive try-catch blocks with specific error types
- Automatic fallback from LangGraph to traditional service
- Human handoff detection for complex scenarios
- Rate limiting and security measures built-in

## Testing Approach

### Direct Testing
```bash
# Test chatbot functionality
poetry run python app/scripts/test_chatbot_direct.py

# Run comprehensive test suite
poetry run python app/scripts/comprehensive_test_suite.py

# Run diagnostic script
poetry run python app/scripts/diagnostic_script.py
```

### API Testing
- Swagger UI available at: `http://localhost:8000/api/v1/docs`
- Health check endpoint: `GET /api/v1/webhook/health`
- Conversation history: `GET /api/v1/webhook/conversation/{phone_number}`

## Monitoring and Debugging

### Logs
- Application logs: `logs/app.log`
- LangGraph logs: `logs/langgraph.log`
- Use structured logging with appropriate log levels

### Health Checks
The system provides comprehensive health checks for all components:
- Database connectivity
- LangGraph system status
- External service availability (Ollama, ChromaDB)
- Security and monitoring components

### Performance Metrics
- Response time tracking per agent
- Intent recognition accuracy
- Session management efficiency
- Error rates and recovery patterns