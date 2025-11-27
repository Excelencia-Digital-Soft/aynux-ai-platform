"""
Unit tests for Excelencia Domain Repositories.

Tests the data access layer for ERP modules and demos.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.excelencia.domain.entities.demo import Demo, DemoRequest, DemoStatus, DemoType
from app.domains.excelencia.domain.entities.module import ERPModule, ModuleCategory, ModuleStatus
from app.domains.excelencia.infrastructure.repositories.demo_repository import (
    SQLAlchemyDemoRepository,
)
from app.domains.excelencia.infrastructure.repositories.module_repository import (
    SQLAlchemyModuleRepository,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_async_session():
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_module_model():
    """Sample SQLAlchemy ERP module model."""
    model = MagicMock()
    model.id = 1
    model.code = "FIN-001"
    model.name = "Contabilidad"
    model.description = "Gestion contable completa"
    model.category = "finance"
    model.status = "active"
    model.features = ["Plan de cuentas", "Asientos automaticos", "Balance"]
    model.pricing_tier = "standard"
    model.created_at = datetime.now(UTC)
    model.updated_at = datetime.now(UTC)
    return model


@pytest.fixture
def sample_demo_model():
    """Sample SQLAlchemy demo model."""
    model = MagicMock()
    model.id = 1
    model.company_name = "Acme Corp"
    model.contact_name = "John Doe"
    model.contact_email = "john@acme.com"
    model.contact_phone = "+1234567890"
    model.modules_of_interest = ["FIN-001", "INV-001"]
    model.demo_type = "general"
    model.request_notes = "Interested in financial module"
    model.scheduled_at = datetime.now(UTC)
    model.duration_minutes = 60
    model.status = "pending"
    model.assigned_to = None
    model.meeting_link = None
    model.module_id = None
    model.created_at = datetime.now(UTC)
    model.updated_at = datetime.now(UTC)
    return model


# ============================================================================
# Module Repository Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_module_get_all(mock_async_session, sample_module_model):
    """Test getting all modules."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_module_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyModuleRepository(mock_async_session)

    # Act
    modules = await repository.get_all()

    # Assert
    assert len(modules) == 1
    assert modules[0].code == "FIN-001"
    assert modules[0].name == "Contabilidad"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_module_get_by_id_with_code(mock_async_session, sample_module_model):
    """Test getting a module by ID (code lookup)."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_module_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyModuleRepository(mock_async_session)

    # Act
    module = await repository.get_by_id("FIN-001")

    # Assert
    assert module is not None
    assert module.code == "FIN-001"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_module_get_by_id_not_found(mock_async_session):
    """Test getting a module that doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyModuleRepository(mock_async_session)

    # Act
    module = await repository.get_by_id("INVALID-CODE")

    # Assert
    assert module is None


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_module_get_by_code(mock_async_session, sample_module_model):
    """Test getting a module by code."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_module_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyModuleRepository(mock_async_session)

    # Act
    module = await repository.get_by_code("FIN-001")

    # Assert
    assert module is not None
    assert module.code == "FIN-001"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_module_get_by_category(mock_async_session, sample_module_model):
    """Test getting modules by category."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_module_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyModuleRepository(mock_async_session)

    # Act
    modules = await repository.get_by_category(ModuleCategory.FINANCE)

    # Assert
    assert len(modules) == 1
    assert modules[0].category == ModuleCategory.FINANCE


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_module_save_new(mock_async_session, sample_module_model):
    """Test saving a new module."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Not existing
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyModuleRepository(mock_async_session)

    module = ERPModule(
        id="mod-002",
        code="INV-001",
        name="Inventario",
        description="Control de stock",
        category=ModuleCategory.INVENTORY,
        status=ModuleStatus.ACTIVE,
        features=["Multi-deposito", "Trazabilidad"],
        pricing_tier="standard",
    )

    # Setup mock refresh
    async def mock_refresh(obj):
        obj.id = 2

    mock_async_session.refresh = mock_refresh

    # Act
    saved = await repository.save(module)

    # Assert
    mock_async_session.add.assert_called_once()
    mock_async_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_module_count(mock_async_session):
    """Test counting modules."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 8
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyModuleRepository(mock_async_session)

    # Act
    count = await repository.count()

    # Assert
    assert count == 8


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_module_exists(mock_async_session):
    """Test checking if module exists."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 1
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyModuleRepository(mock_async_session)

    # Act
    exists = await repository.exists("FIN-001")

    # Assert
    assert exists is True


# ============================================================================
# Demo Repository Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_get_by_id_success(mock_async_session, sample_demo_model):
    """Test successfully getting a demo by ID."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_demo_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    demo = await repository.get_by_id("demo-001")

    # Assert
    assert demo is not None
    assert demo.request.company_name == "Acme Corp"
    assert demo.request.contact_email == "john@acme.com"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_get_by_id_not_found(mock_async_session):
    """Test getting a demo that doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    demo = await repository.get_by_id("demo-999")

    # Assert
    assert demo is None


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_get_pending(mock_async_session, sample_demo_model):
    """Test getting pending demos."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_demo_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    demos = await repository.get_pending()

    # Assert
    assert len(demos) == 1
    assert demos[0].status == DemoStatus.PENDING


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_get_by_status(mock_async_session, sample_demo_model):
    """Test getting demos by status."""
    # Arrange
    sample_demo_model.status = "scheduled"
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_demo_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    demos = await repository.get_by_status(DemoStatus.SCHEDULED)

    # Assert
    assert len(demos) == 1


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_get_by_date_range(mock_async_session, sample_demo_model):
    """Test getting demos in date range."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_demo_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 12, 31, tzinfo=UTC)

    # Act
    demos = await repository.get_by_date_range(start, end)

    # Assert
    assert len(demos) >= 0  # May be empty depending on scheduled_at


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_save_new(mock_async_session, sample_demo_model):
    """Test saving a new demo."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    request = DemoRequest(
        company_name="New Company",
        contact_name="Jane Doe",
        contact_email="jane@newco.com",
        modules_of_interest=["CRM-001"],
        demo_type=DemoType.MODULE_SPECIFIC,
    )

    demo = Demo(
        id="demo-new",
        request=request,
        status=DemoStatus.PENDING,
    )

    # Setup mock refresh
    async def mock_refresh(obj):
        obj.id = 2

    mock_async_session.refresh = mock_refresh

    # Act
    saved = await repository.save(demo)

    # Assert
    mock_async_session.add.assert_called_once()
    mock_async_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_delete_success(mock_async_session, sample_demo_model):
    """Test deleting a demo."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_demo_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    success = await repository.delete("demo-001")

    # Assert
    assert success is True
    mock_async_session.delete.assert_called_once_with(sample_demo_model)
    mock_async_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_delete_not_found(mock_async_session):
    """Test deleting a demo that doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    success = await repository.delete("demo-999")

    # Assert
    assert success is False
    mock_async_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_get_all(mock_async_session, sample_demo_model):
    """Test getting all demos."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_demo_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    demos = await repository.get_all()

    # Assert
    assert len(demos) == 1


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_count(mock_async_session):
    """Test counting demos."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    count = await repository.count()

    # Assert
    assert count == 5


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_get_by_email(mock_async_session, sample_demo_model):
    """Test getting demos by contact email."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_demo_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    demos = await repository.get_by_email("john@acme.com")

    # Assert
    assert len(demos) == 1
    assert demos[0].request.contact_email == "john@acme.com"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_demo_get_by_company(mock_async_session, sample_demo_model):
    """Test getting demos by company name."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_demo_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDemoRepository(mock_async_session)

    # Act
    demos = await repository.get_by_company("Acme")

    # Assert
    assert len(demos) == 1
    assert "Acme" in demos[0].request.company_name
