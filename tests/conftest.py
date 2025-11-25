"""
Shared pytest fixtures for all tests.

This module provides common fixtures for database sessions, mock services,
test data, and other shared testing utilities.
"""

import asyncio
import os
from datetime import datetime
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["TESTING"] = "true"


# ============================================================================
# ASYNC EVENT LOOP CONFIGURATION
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# DATABASE FIXTURES
# ============================================================================


@pytest.fixture
def db_url() -> str:
    """Return test database URL."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://enzo:@localhost/aynux_test",
    )


@pytest_asyncio.fixture
async def async_engine(db_url: str):
    """Create async database engine for testing."""
    engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session_factory(async_engine) -> async_sessionmaker:
    """Create async session factory."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def db_session(async_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh database session for each test.

    Each test gets its own session that is rolled back after the test completes.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


# ============================================================================
# REDIS FIXTURES
# ============================================================================


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Create Redis client for testing."""
    redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")
    client = Redis.from_url(redis_url, decode_responses=True)

    yield client

    # Cleanup: flush test database
    await client.flushdb()
    await client.close()


@pytest.fixture
def mock_redis() -> Mock:
    """Create a mock Redis client."""
    mock = Mock(spec=Redis)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=False)
    mock.expire = AsyncMock(return_value=True)
    return mock


# ============================================================================
# LLM / AI FIXTURES
# ============================================================================


@pytest.fixture
def mock_llm():
    """Create a mock LLM service."""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock(return_value="Mocked LLM response")
    mock.invoke = Mock(return_value="Mocked LLM response")
    mock.astream = AsyncMock()
    return mock


@pytest.fixture
def mock_ollama_llm():
    """Create a mock Ollama LLM service."""
    from app.integrations.llm.ollama import OllamaLLM

    mock = AsyncMock(spec=OllamaLLM)
    mock.generate = AsyncMock(return_value="Mocked Ollama response")
    mock.chat = AsyncMock(return_value={"message": {"content": "Mocked chat response"}})
    mock.embed = AsyncMock(return_value=[0.1] * 1024)  # Mock embedding vector
    return mock


# ============================================================================
# VECTOR STORE FIXTURES
# ============================================================================


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    mock = AsyncMock()
    mock.search = AsyncMock(return_value=[])
    mock.add_documents = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=True)
    mock.similarity_search = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_pgvector_service():
    """Create a mock pgvector service."""
    from app.integrations.vector_stores.pgvector import PgVectorService

    mock = AsyncMock(spec=PgVectorService)
    mock.search_products = AsyncMock(return_value=[])
    mock.upsert_product_embedding = AsyncMock(return_value=True)
    mock.delete_product_embedding = AsyncMock(return_value=True)
    return mock




# ============================================================================
# REPOSITORY FIXTURES
# ============================================================================


@pytest.fixture
def mock_product_repository():
    """Create a mock product repository."""
    mock = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=None)
    mock.search = AsyncMock(return_value=[])
    mock.get_all = AsyncMock(return_value=[])
    mock.save = AsyncMock()
    mock.delete = AsyncMock()
    return mock


@pytest.fixture
def mock_customer_repository():
    """Create a mock customer repository."""
    mock = AsyncMock()
    mock.get_by_phone = AsyncMock(return_value=None)
    mock.create = AsyncMock()
    mock.update = AsyncMock()
    return mock


@pytest.fixture
def mock_conversation_repository():
    """Create a mock conversation repository."""
    mock = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=None)
    mock.get_by_phone = AsyncMock(return_value=None)
    mock.create = AsyncMock()
    mock.update = AsyncMock()
    return mock


# ============================================================================
# API CLIENT FIXTURES
# ============================================================================


@pytest.fixture
def fastapi_app():
    """Create FastAPI application instance for testing."""
    from app.main import app
    return app


@pytest.fixture
def api_client(fastapi_app) -> TestClient:
    """Create FastAPI test client."""
    return TestClient(fastapi_app)


# ============================================================================
# WHATSAPP FIXTURES
# ============================================================================


@pytest.fixture
def mock_whatsapp_service():
    """Create a mock WhatsApp service."""
    mock = AsyncMock()
    mock.send_message = AsyncMock(return_value={"success": True})
    mock.send_template = AsyncMock(return_value={"success": True})
    mock.mark_as_read = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_whatsapp_client():
    """Create a mock WhatsApp HTTP client."""
    mock = AsyncMock()
    mock.post = AsyncMock()
    mock.get = AsyncMock()
    return mock


@pytest.fixture
def whatsapp_webhook_payload():
    """Sample WhatsApp webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "123456789",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test User"},
                                    "wa_id": "5491234567890",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "5491234567890",
                                    "id": "wamid.test123",
                                    "timestamp": "1234567890",
                                    "text": {"body": "Hello"},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


# ============================================================================
# AGENT FIXTURES
# ============================================================================


@pytest.fixture
def mock_agent_state():
    """Create a mock agent state."""
    return {
        "messages": [],
        "phone": "+5491234567890",
        "customer_name": "Test User",
        "intent": None,
        "routing": {},
        "data": {},
        "flow_control": {"next_node": None, "should_end": False},
        "metadata": {"timestamp": datetime.now().isoformat()},
    }


@pytest.fixture
def mock_base_agent():
    """Create a mock base agent."""
    from app.agents.subagent.base_agent import BaseAgent

    mock = AsyncMock(spec=BaseAgent)
    mock.process = AsyncMock(return_value={})
    mock.can_handle = Mock(return_value=True)
    return mock


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator agent."""
    mock = AsyncMock()
    mock.analyze_intent = AsyncMock(return_value={"intent": "product_search"})
    mock.process = AsyncMock(return_value={"intent": "product_search"})
    return mock


@pytest.fixture
def mock_supervisor():
    """Create a mock supervisor agent."""
    mock = AsyncMock()
    mock.evaluate = AsyncMock(return_value={"should_continue": False})
    mock.process = AsyncMock(return_value={"should_continue": False})
    return mock


# ============================================================================
# DEPENDENCY CONTAINER FIXTURES
# ============================================================================


@pytest.fixture
def mock_container():
    """Create a mock DependencyContainer."""
    from app.core.container import DependencyContainer

    container = DependencyContainer()

    # Mock expensive resources
    container.get_llm = MagicMock()
    container.get_vector_store = MagicMock()

    return container


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_product():
    """Create a sample product for testing."""
    return {
        "id": 1,
        "name": "Test Product",
        "description": "A test product for unit testing",
        "price": 99.99,
        "stock": 10,
        "category_id": 1,
        "sku": "TEST-001",
        "active": True,
    }


@pytest.fixture
def sample_customer():
    """Create a sample customer for testing."""
    return {
        "id": 1,
        "phone": "+5491234567890",
        "name": "Test Customer",
        "email": "test@example.com",
        "created_at": datetime.now(),
    }


@pytest.fixture
def sample_conversation():
    """Create a sample conversation for testing."""
    return {
        "id": "conv-123",
        "phone": "+5491234567890",
        "customer_id": 1,
        "messages": [],
        "status": "active",
        "created_at": datetime.now(),
    }


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    return {
        "id": 1,
        "customer_id": 1,
        "total": 199.98,
        "status": "pending",
        "items": [
            {"product_id": 1, "quantity": 2, "price": 99.99}
        ],
        "created_at": datetime.now(),
    }


# ============================================================================
# ENVIRONMENT FIXTURES
# ============================================================================


@pytest.fixture
def test_env_vars(monkeypatch):
    """Set test environment variables."""
    env_vars = {
        "ENVIRONMENT": "test",
        "TESTING": "true",
        "DB_NAME": "aynux_test",
        "REDIS_DB": "1",
        "OLLAMA_API_URL": "http://localhost:11434",
        "LANGSMITH_TRACING": "false",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Add any global cleanup logic here
    pass
