"""
Unit tests for search strategy implementations.

Tests:
- PgVectorSearchStrategy
- DatabaseSearchStrategy
- SearchStrategyManager
"""

from unittest.mock import AsyncMock, Mock

import pytest

from app.domains.ecommerce.agents.product.models import SearchResult, SearchStrategyType, UserIntent
from app.domains.ecommerce.agents.product.search_strategy_manager import SearchStrategyManager
from app.domains.ecommerce.agents.product.strategies.database_strategy import DatabaseSearchStrategy
from app.domains.ecommerce.agents.product.strategies.pgvector_strategy import PgVectorSearchStrategy


class TestPgVectorSearchStrategy:
    """Tests for PgVectorSearchStrategy."""

    @pytest.fixture
    def mock_pgvector(self):
        """Create mock PgVectorIntegration."""
        pgvector = Mock()
        pgvector.generate_embedding = AsyncMock(return_value=[0.1] * 384)
        pgvector.search_similar_products = AsyncMock(return_value=[])
        return pgvector

    @pytest.fixture
    def strategy(self, mock_pgvector):
        """Create PgVectorSearchStrategy with mock dependencies."""
        config = {"similarity_threshold": 0.7, "max_results": 10}
        return PgVectorSearchStrategy(pgvector=mock_pgvector, config=config)

    def test_strategy_name(self, strategy):
        """Test strategy name property."""
        assert strategy.strategy_name == "pgvector"

    @pytest.mark.asyncio
    async def test_search_success(self, strategy, mock_pgvector):
        """Test successful search."""
        # Mock search results
        mock_pgvector.search_similar_products.return_value = [
            {"product": {"id": "1", "name": "Laptop"}, "similarity": 0.85},
            {"product": {"id": "2", "name": "Mouse"}, "similarity": 0.75},
        ]

        intent = UserIntent(intent="search_specific_products", search_terms=["laptop"])
        result = await strategy.search("laptop", intent, 10)

        assert result.success is True
        assert len(result.products) == 2
        assert result.source == "pgvector"
        assert result.products[0]["similarity_score"] == 0.85

    @pytest.mark.asyncio
    async def test_search_no_results(self, strategy, mock_pgvector):
        """Test search with no results."""
        mock_pgvector.search_similar_products.return_value = []

        intent = UserIntent(intent="search_specific_products", search_terms=["laptop"])
        result = await strategy.search("laptop", intent, 10)

        assert result.success is True
        assert len(result.products) == 0
        assert result.metadata["total_results"] == 0

    @pytest.mark.asyncio
    async def test_search_error(self, strategy, mock_pgvector):
        """Test search with error."""
        mock_pgvector.generate_embedding.side_effect = Exception("Embedding failed")

        intent = UserIntent(intent="search_specific_products", search_terms=["laptop"])
        result = await strategy.search("laptop", intent, 10)

        assert result.success is False
        assert result.error == "Embedding failed"

    @pytest.mark.asyncio
    async def test_health_check_success(self, strategy, mock_pgvector):
        """Test successful health check."""
        is_healthy = await strategy.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, strategy, mock_pgvector):
        """Test failed health check."""
        mock_pgvector.generate_embedding.side_effect = Exception("Connection failed")

        is_healthy = await strategy.health_check()
        assert is_healthy is False


class TestDatabaseSearchStrategy:
    """Tests for DatabaseSearchStrategy."""

    @pytest.fixture
    def mock_product_tool(self):
        """Create mock ProductTool."""
        tool = AsyncMock()
        tool.return_value = {"success": True, "products": []}
        return tool

    @pytest.fixture
    def strategy(self, mock_product_tool):
        """Create DatabaseSearchStrategy with mock dependencies."""
        config = {"max_results": 10, "require_stock": True}
        return DatabaseSearchStrategy(product_tool=mock_product_tool, config=config)

    def test_strategy_name(self, strategy):
        """Test strategy name property."""
        assert strategy.strategy_name == "database"

    @pytest.mark.asyncio
    async def test_search_featured(self, strategy, mock_product_tool):
        """Test search for featured products."""
        mock_product_tool.return_value = {
            "success": True,
            "products": [{"id": "1", "name": "Featured Laptop"}],
        }

        intent = UserIntent(intent="show_general_catalog", search_terms=[], action_needed="show_featured")
        result = await strategy.search("show products", intent, 10)

        assert result.success is True
        assert len(result.products) == 1
        mock_product_tool.assert_called_with("featured", limit=10)

    @pytest.mark.asyncio
    async def test_search_by_category(self, strategy, mock_product_tool):
        """Test search by category."""
        mock_product_tool.return_value = {
            "success": True,
            "products": [{"id": "1", "name": "Gaming Laptop"}],
        }

        intent = UserIntent(
            intent="search_by_category",
            search_terms=["laptop"],
            category="laptops",
            action_needed="search_category",
        )
        result = await strategy.search("laptops", intent, 10)

        assert result.success is True
        mock_product_tool.assert_called_with("by_category", category="laptops", limit=10)

    @pytest.mark.asyncio
    async def test_search_by_brand(self, strategy, mock_product_tool):
        """Test search by brand."""
        mock_product_tool.return_value = {
            "success": True,
            "products": [{"id": "1", "name": "ASUS Laptop"}],
        }

        intent = UserIntent(
            intent="search_by_brand", search_terms=["asus"], brand="ASUS", action_needed="search_brand"
        )
        result = await strategy.search("ASUS products", intent, 10)

        assert result.success is True
        mock_product_tool.assert_called_with("by_brand", brand="ASUS", limit=10)

    @pytest.mark.asyncio
    async def test_health_check(self, strategy, mock_product_tool):
        """Test health check."""
        mock_product_tool.return_value = {"success": True, "products": []}

        is_healthy = await strategy.health_check()
        assert is_healthy is True


class TestSearchStrategyManager:
    """Tests for SearchStrategyManager."""

    @pytest.fixture
    def mock_strategies(self):
        """Create mock strategies."""
        pgvector = Mock()
        pgvector.search = AsyncMock(
            return_value=SearchResult(success=True, products=[], source="pgvector")
        )
        pgvector.health_check = AsyncMock(return_value=True)

        database = Mock()
        database.search = AsyncMock(
            return_value=SearchResult(success=True, products=[{"id": "1"}], source="database")
        )
        database.health_check = AsyncMock(return_value=True)

        return {
            SearchStrategyType.PGVECTOR: pgvector,
            SearchStrategyType.DATABASE: database,
        }

    @pytest.fixture
    def manager(self, mock_strategies):
        """Create SearchStrategyManager with mock strategies."""
        return SearchStrategyManager(
            strategies=mock_strategies,
            primary_strategy=SearchStrategyType.PGVECTOR,
            min_results_threshold=2,
        )

    def test_initialization(self, manager):
        """Test manager initialization."""
        assert manager.primary_strategy == SearchStrategyType.PGVECTOR
        assert manager.min_results_threshold == 2

    def test_validation_no_strategies(self):
        """Test validation fails with no strategies."""
        with pytest.raises(ValueError, match="At least one search strategy"):
            SearchStrategyManager(strategies={}, primary_strategy=SearchStrategyType.PGVECTOR)

    def test_validation_invalid_primary(self, mock_strategies):
        """Test validation fails with invalid primary strategy."""
        with pytest.raises(ValueError, match="Primary strategy.*not in available"):
            SearchStrategyManager(
                strategies={SearchStrategyType.PGVECTOR: mock_strategies[SearchStrategyType.PGVECTOR]},
                primary_strategy=SearchStrategyType.DATABASE,
            )

    @pytest.mark.asyncio
    async def test_search_primary_success(self, manager, mock_strategies):
        """Test successful search with primary strategy."""
        # Primary strategy returns sufficient results
        mock_strategies[SearchStrategyType.PGVECTOR].search.return_value = SearchResult(
            success=True, products=[{"id": "1"}, {"id": "2"}], source="pgvector"
        )

        intent = UserIntent(intent="search_specific_products", search_terms=["laptop"])
        result = await manager.search("laptop", intent, 10)

        assert result.success is True
        assert result.source == "pgvector"
        assert len(result.products) == 2

    @pytest.mark.asyncio
    async def test_search_fallback_chain(self, manager, mock_strategies):
        """Test fallback to other strategies."""
        # Primary fails, fallback succeeds
        mock_strategies[SearchStrategyType.PGVECTOR].search.return_value = SearchResult(
            success=True, products=[], source="pgvector"  # Insufficient results
        )
        mock_strategies[SearchStrategyType.DATABASE].search.return_value = SearchResult(
            success=True, products=[{"id": "1"}, {"id": "2"}], source="database"
        )

        intent = UserIntent(intent="search_specific_products", search_terms=["laptop"])
        result = await manager.search("laptop", intent, 10)

        assert result.source == "database"
        assert len(result.products) == 2

    @pytest.mark.asyncio
    async def test_search_all_fail(self, manager, mock_strategies):
        """Test when all strategies fail."""
        # All strategies return insufficient results
        for strategy in mock_strategies.values():
            strategy.search.return_value = SearchResult(success=True, products=[], source="test")

        intent = UserIntent(intent="search_specific_products", search_terms=["laptop"])
        result = await manager.search("laptop", intent, 10)

        assert result.success is False
        assert result.source == "fallback_exhausted"

    @pytest.mark.asyncio
    async def test_search_with_override(self, manager, mock_strategies):
        """Test search with strategy override."""
        intent = UserIntent(intent="search_specific_products", search_terms=["laptop"])
        await manager.search("laptop", intent, 10, strategy_override=SearchStrategyType.DATABASE)

        # Should call database strategy directly
        mock_strategies[SearchStrategyType.DATABASE].search.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_all(self, manager):
        """Test health check for all strategies."""
        health_status = await manager.health_check_all()

        assert health_status["pgvector"] is True
        assert health_status["database"] is True

    def test_get_available_strategies(self, manager):
        """Test getting available strategies."""
        strategies = manager.get_available_strategies()

        assert SearchStrategyType.PGVECTOR in strategies
        assert SearchStrategyType.DATABASE in strategies

    def test_update_primary_strategy(self, manager):
        """Test updating primary strategy."""
        manager.update_primary_strategy(SearchStrategyType.DATABASE)
        assert manager.primary_strategy == SearchStrategyType.DATABASE

    def test_update_primary_strategy_invalid(self, manager):
        """Test updating with invalid strategy."""
        # Remove database strategy
        del manager.strategies[SearchStrategyType.DATABASE]

        with pytest.raises(ValueError, match="not available"):
            manager.update_primary_strategy(SearchStrategyType.DATABASE)

    def test_update_min_results_threshold(self, manager):
        """Test updating threshold."""
        manager.update_min_results_threshold(5)
        assert manager.min_results_threshold == 5

    def test_update_min_results_threshold_invalid(self, manager):
        """Test updating with invalid threshold."""
        with pytest.raises(ValueError, match="must be >= 0"):
            manager.update_min_results_threshold(-1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
