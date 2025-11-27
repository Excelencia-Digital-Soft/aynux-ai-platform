"""
Unit tests for ProductRepository.

Tests the data access layer for products following Repository pattern.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.domains.ecommerce.infrastructure.repositories.product_repository import (
    ProductRepository,
)


# ============================================================================
# FIXTURES
# ============================================================================


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
    product.subcategory_id = None
    product.brand_id = 1
    product.sku = "TEST-001"
    product.active = True
    product.featured = False
    product.category = MagicMock(name="Electronics")
    product.subcategory = None
    product.brand = MagicMock(name="TestBrand")
    return product


@pytest.fixture
def mock_db_context(sample_product_model):
    """Mock database context manager."""
    mock_db = MagicMock()
    # Configure query chain for find_by_id
    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = sample_product_model
    mock_db.query.return_value = mock_query
    return mock_db


# ============================================================================
# ProductRepository Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_find_by_id_success(sample_product_model, mock_db_context):
    """Test successfully finding a product by ID."""
    with patch("app.domains.ecommerce.infrastructure.repositories.product_repository.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_context
        mock_context.return_value.__exit__.return_value = False

        repository = ProductRepository()

        # Act
        product = await repository.find_by_id(1)

        # Assert
        assert product is not None
        assert product.id == 1
        assert product.name == "Test Product"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_find_by_id_not_found(mock_db_context):
    """Test finding a product that doesn't exist."""
    # Configure mock to return None
    mock_db_context.query.return_value.options.return_value.filter.return_value.first.return_value = None

    with patch("app.domains.ecommerce.infrastructure.repositories.product_repository.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_context
        mock_context.return_value.__exit__.return_value = False

        repository = ProductRepository()

        # Act
        product = await repository.find_by_id(999)

        # Assert
        assert product is None


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_search_products(sample_product_model, mock_db_context):
    """Test searching products by query."""
    # Configure mock for search
    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = [sample_product_model]
    mock_db_context.query.return_value = mock_query

    with patch("app.domains.ecommerce.infrastructure.repositories.product_repository.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_context
        mock_context.return_value.__exit__.return_value = False

        repository = ProductRepository()

        # Act
        products = await repository.search("test")

        # Assert
        assert len(products) == 1
        assert products[0].name == "Test Product"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_find_all_products(sample_product_model, mock_db_context):
    """Test getting all products with pagination."""
    # Configure mock for find_all
    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = [sample_product_model]
    mock_db_context.query.return_value = mock_query

    with patch("app.domains.ecommerce.infrastructure.repositories.product_repository.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_context
        mock_context.return_value.__exit__.return_value = False

        repository = ProductRepository()

        # Act
        products = await repository.find_all(skip=0, limit=10)

        # Assert
        assert len(products) == 1
        assert products[0].active is True


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_save_product(sample_product_model, mock_db_context):
    """Test saving a product."""
    with patch("app.domains.ecommerce.infrastructure.repositories.product_repository.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_context
        mock_context.return_value.__exit__.return_value = False

        repository = ProductRepository()

        # Act
        result = await repository.save(sample_product_model)

        # Assert
        assert result == sample_product_model
        mock_db_context.add.assert_called_once_with(sample_product_model)
        mock_db_context.commit.assert_called_once()
        mock_db_context.refresh.assert_called_once_with(sample_product_model)


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_save_product_database_error(sample_product_model, mock_db_context):
    """Test handling database error when saving."""
    mock_db_context.commit.side_effect = Exception("Database error")

    with patch("app.domains.ecommerce.infrastructure.repositories.product_repository.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_context
        mock_context.return_value.__exit__.return_value = False

        repository = ProductRepository()

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await repository.save(sample_product_model)

        assert "Database error" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_delete_product(sample_product_model, mock_db_context):
    """Test deleting a product (soft delete - sets active=False)."""
    # Configure mock for delete - query returns product
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = sample_product_model
    mock_db_context.query.return_value = mock_query

    with patch("app.domains.ecommerce.infrastructure.repositories.product_repository.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_context
        mock_context.return_value.__exit__.return_value = False

        repository = ProductRepository()

        # Act
        success = await repository.delete(1)

        # Assert - ProductRepository does soft delete (sets active=False), not hard delete
        assert success is True
        assert sample_product_model.active is False  # Verify soft delete
        mock_db_context.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_delete_product_not_found(mock_db_context):
    """Test deleting a product that doesn't exist."""
    # Configure mock to return None for find
    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_db_context.query.return_value = mock_query

    with patch("app.domains.ecommerce.infrastructure.repositories.product_repository.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_context
        mock_context.return_value.__exit__.return_value = False

        repository = ProductRepository()

        # Act
        success = await repository.delete(999)

        # Assert
        assert success is False
        mock_db_context.commit.assert_not_called()
