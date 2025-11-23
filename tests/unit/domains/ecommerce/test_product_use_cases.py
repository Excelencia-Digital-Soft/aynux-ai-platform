"""
Unit Tests for Product Use Cases

Demonstrates testing with mocks following the new architecture.
Shows the benefits of dependency injection and interfaces.
"""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
from typing import List, Dict, Any

from app.domains.ecommerce.application.use_cases import (
    SearchProductsUseCase,
    SearchProductsRequest,
    GetFeaturedProductsUseCase,
    GetFeaturedProductsRequest,
)


@pytest.fixture
def mock_product_repository():
    """Mock product repository"""
    mock_repo = AsyncMock()

    # Mock product data
    mock_product = Mock()
    mock_product.id = 1
    mock_product.name = "Test Laptop"
    mock_product.price = 899.99
    mock_product.stock = 10
    mock_product.active = True
    mock_product.featured = True
    mock_product.on_sale = False
    mock_product.description = "High performance laptop"
    mock_product.specs = "Intel i7, 16GB RAM"

    # Mock category
    mock_category = Mock()
    mock_category.display_name = "Notebooks"
    mock_product.category = mock_category

    # Mock brand
    mock_brand = Mock()
    mock_brand.name = "HP"
    mock_product.brand = mock_brand

    mock_product.subcategory = None

    # Setup return values
    mock_repo.search.return_value = [mock_product]
    mock_repo.find_all.return_value = [mock_product]

    return mock_repo


@pytest.fixture
def mock_vector_store():
    """Mock vector store"""
    from app.core.interfaces.vector_store import VectorSearchResult, Document

    mock_store = AsyncMock()

    # Mock search results
    mock_doc = Document(
        id="1",
        content="Test Laptop - High performance laptop",
        metadata={
            "id": 1,
            "name": "Test Laptop",
            "price": 899.99,
            "stock": 10,
            "category": "Notebooks",
            "brand": "HP",
        },
    )

    mock_result = VectorSearchResult(
        document=mock_doc,
        score=0.95,
        metadata={"source": "pgvector"},
    )

    mock_store.search.return_value = [mock_result]

    return mock_store


@pytest.fixture
def mock_llm():
    """Mock LLM"""
    mock = AsyncMock()
    mock.generate.return_value = "laptop gaming high performance"
    return mock


class TestSearchProductsUseCase:
    """Test cases for SearchProductsUseCase"""

    @pytest.mark.asyncio
    async def test_search_with_semantic_search_success(
        self, mock_product_repository, mock_vector_store, mock_llm
    ):
        """Test successful semantic search"""
        # Arrange
        use_case = SearchProductsUseCase(
            product_repository=mock_product_repository,
            vector_store=mock_vector_store,
            llm=mock_llm,
        )

        request = SearchProductsRequest(
            query="laptop gaming",
            limit=10,
            use_semantic_search=True,
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.success is True
        assert len(response.products) > 0
        assert response.search_method == "semantic"
        assert response.products[0]["name"] == "Test Laptop"

        # Verify vector store was called
        mock_vector_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_fallback_to_database(
        self, mock_product_repository, mock_vector_store, mock_llm
    ):
        """Test fallback to database search when semantic search fails"""
        # Arrange
        mock_vector_store.search.return_value = []  # Semantic search returns empty

        use_case = SearchProductsUseCase(
            product_repository=mock_product_repository,
            vector_store=mock_vector_store,
            llm=mock_llm,
        )

        request = SearchProductsRequest(
            query="laptop",
            limit=10,
            use_semantic_search=True,
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.success is True
        assert response.search_method == "database"

        # Verify both were called
        mock_vector_store.search.assert_called_once()
        mock_product_repository.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self, mock_product_repository, mock_vector_store, mock_llm
    ):
        """Test search with filters"""
        # Arrange
        use_case = SearchProductsUseCase(
            product_repository=mock_product_repository,
            vector_store=mock_vector_store,
            llm=mock_llm,
        )

        request = SearchProductsRequest(
            query="laptop",
            category="notebooks",
            brand="HP",
            min_price=500.0,
            max_price=1000.0,
            limit=10,
            use_semantic_search=True,
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.success is True

        # Verify filters were passed to vector store
        call_args = mock_vector_store.search.call_args
        assert call_args is not None
        filter_metadata = call_args[1].get("filter_metadata")
        assert filter_metadata is not None
        assert "category" in filter_metadata
        assert "brand" in filter_metadata
        assert "price_range" in filter_metadata


class TestGetFeaturedProductsUseCase:
    """Test cases for GetFeaturedProductsUseCase"""

    @pytest.mark.asyncio
    async def test_get_featured_products_success(self, mock_product_repository):
        """Test successful retrieval of featured products"""
        # Arrange
        use_case = GetFeaturedProductsUseCase(
            product_repository=mock_product_repository
        )

        request = GetFeaturedProductsRequest(limit=10)

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.success is True
        assert len(response.products) > 0
        assert response.products[0]["name"] == "Test Laptop"
        assert response.products[0]["featured"] is True

        # Verify repository was called
        mock_product_repository.find_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_featured_products_with_category_filter(
        self, mock_product_repository
    ):
        """Test featured products with category filter"""
        # Arrange
        use_case = GetFeaturedProductsUseCase(
            product_repository=mock_product_repository
        )

        request = GetFeaturedProductsRequest(
            limit=10,
            category="notebooks",
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.success is True
        # Only products in "notebooks" category should be returned
        for product in response.products:
            assert product["category"].lower() == "notebooks"


# Benefits of this architecture:

# 1. **Easy to Mock**: All dependencies are interfaces, easy to mock
# 2. **Fast Tests**: No database or external services needed
# 3. **Isolated**: Each use case can be tested independently
# 4. **Maintainable**: Changes to implementation don't break tests
# 5. **Clear**: Test focuses on business logic, not infrastructure
