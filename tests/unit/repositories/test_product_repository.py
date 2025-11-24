"""
Unit tests for ProductRepository.

Tests the data access layer for products following Repository pattern.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ecommerce.infrastructure.repositories.product_repository import (
    ProductRepository,
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
    return session


@pytest.fixture
def sample_product_model():
    """Sample SQLAlchemy product model."""
    product = MagicMock()
    product.id = 1
    product.name = "Test Product"
    product.description = "A test product"
    product.price = 99.99
    product.stock = 10
    product.category_id = 1
    product.sku = "TEST-001"
    product.active = True
    return product


# ============================================================================
# ProductRepository Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_get_by_id_success(mock_async_session, sample_product_model):
    """Test successfully getting a product by ID."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_product_model
    mock_async_session.execute.return_value = mock_result

    repository = ProductRepository(mock_async_session)

    # Act
    product = await repository.get_by_id(1)

    # Assert
    assert product is not None
    assert product.id == 1
    assert product.name == "Test Product"
    mock_async_session.execute.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_get_by_id_not_found(mock_async_session):
    """Test getting a product that doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = ProductRepository(mock_async_session)

    # Act
    product = await repository.get_by_id(999)

    # Assert
    assert product is None


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_search_products(mock_async_session, sample_product_model):
    """Test searching products by query."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_product_model]
    mock_async_session.execute.return_value = mock_result

    repository = ProductRepository(mock_async_session)

    # Act
    products = await repository.search("test")

    # Assert
    assert len(products) == 1
    assert products[0].name == "Test Product"
    mock_async_session.execute.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_get_all_active_products(mock_async_session, sample_product_model):
    """Test getting all active products."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_product_model]
    mock_async_session.execute.return_value = mock_result

    repository = ProductRepository(mock_async_session)

    # Act
    products = await repository.get_all(active_only=True)

    # Assert
    assert len(products) == 1
    assert products[0].active is True


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_save_new_product(mock_async_session, sample_product_model):
    """Test saving a new product."""
    # Arrange
    repository = ProductRepository(mock_async_session)

    # Act
    result = await repository.save(sample_product_model)

    # Assert
    assert result == sample_product_model
    mock_async_session.commit.assert_called_once()
    mock_async_session.refresh.assert_called_once_with(sample_product_model)


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_save_product_database_error(mock_async_session, sample_product_model):
    """Test handling database error when saving."""
    # Arrange
    mock_async_session.commit.side_effect = Exception("Database error")
    repository = ProductRepository(mock_async_session)

    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await repository.save(sample_product_model)

    assert "Database error" in str(exc_info.value)
    mock_async_session.rollback.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_delete_product(mock_async_session, sample_product_model):
    """Test deleting a product."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_product_model
    mock_async_session.execute.return_value = mock_result

    repository = ProductRepository(mock_async_session)

    # Act
    success = await repository.delete(1)

    # Assert
    assert success is True
    mock_async_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_delete_product_not_found(mock_async_session):
    """Test deleting a product that doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = ProductRepository(mock_async_session)

    # Act
    success = await repository.delete(999)

    # Assert
    assert success is False
    # Commit should not be called
    mock_async_session.commit.assert_not_called()
