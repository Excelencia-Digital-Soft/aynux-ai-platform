"""
Unit tests for product agent data models and protocols.

Tests:
- UserIntent data class
- SearchResult data class
- SearchStrategyType enum
"""

import pytest

from app.domains.ecommerce.agents.product.models import SearchResult, SearchStrategyType, UserIntent


class TestUserIntent:
    """Tests for UserIntent data class."""

    def test_create_default_intent(self):
        """Test creating intent with minimal fields."""
        intent = UserIntent(intent="search_general", search_terms=["laptop"])

        assert intent.intent == "search_general"
        assert intent.search_terms == ["laptop"]
        assert intent.category is None
        assert intent.wants_stock_info is False
        assert intent.action_needed == "search_products"

    def test_create_full_intent(self):
        """Test creating intent with all fields."""
        intent = UserIntent(
            intent="search_specific_products",
            search_terms=["laptop", "gaming"],
            category="laptops",
            brand="ASUS",
            price_min=500.0,
            price_max=1500.0,
            specific_product="ASUS ROG",
            wants_stock_info=True,
            wants_featured=False,
            wants_sale=True,
            action_needed="search_products",
        )

        assert intent.intent == "search_specific_products"
        assert intent.search_terms == ["laptop", "gaming"]
        assert intent.category == "laptops"
        assert intent.brand == "ASUS"
        assert intent.price_min == 500.0
        assert intent.price_max == 1500.0
        assert intent.specific_product == "ASUS ROG"
        assert intent.wants_stock_info is True
        assert intent.wants_sale is True

    def test_to_dict(self):
        """Test converting intent to dictionary."""
        intent = UserIntent(
            intent="search_general", search_terms=["laptop"], category="laptops", price_min=500.0, wants_stock_info=True
        )

        intent_dict = intent.to_dict()

        assert isinstance(intent_dict, dict)
        assert intent_dict["intent"] == "search_general"
        assert intent_dict["search_terms"] == ["laptop"]
        assert intent_dict["category"] == "laptops"
        assert intent_dict["price_min"] == 500.0
        assert intent_dict["wants_stock_info"] is True

    def test_from_dict(self):
        """Test creating intent from dictionary."""
        data = {
            "intent": "search_by_category",
            "search_terms": ["laptop", "gaming"],
            "category": "gaming-laptops",
            "brand": "ASUS",
            "price_max": 2000.0,
            "wants_stock_info": True,
        }

        intent = UserIntent.from_dict(data)

        assert intent.intent == "search_by_category"
        assert intent.search_terms == ["laptop", "gaming"]
        assert intent.category == "gaming-laptops"
        assert intent.brand == "ASUS"
        assert intent.price_max == 2000.0
        assert intent.price_min is None
        assert intent.wants_stock_info is True

    def test_from_dict_with_defaults(self):
        """Test creating intent from minimal dictionary."""
        data = {"search_terms": ["laptop"]}

        intent = UserIntent.from_dict(data)

        assert intent.intent == "search_general"  # Default
        assert intent.search_terms == ["laptop"]  # Provided value
        assert intent.action_needed == "search_products"  # Default

    def test_round_trip_conversion(self):
        """Test converting to dict and back."""
        original = UserIntent(
            intent="search_specific",
            search_terms=["laptop", "gaming"],
            category="laptops",
            price_min=1000.0,
            wants_featured=True,
        )

        intent_dict = original.to_dict()
        restored = UserIntent.from_dict(intent_dict)

        assert restored.intent == original.intent
        assert restored.search_terms == original.search_terms
        assert restored.category == original.category
        assert restored.price_min == original.price_min
        assert restored.wants_featured == original.wants_featured


class TestSearchResult:
    """Tests for SearchResult data class."""

    def test_create_successful_result(self):
        """Test creating successful search result."""
        products = [{"id": "1", "name": "Laptop", "price": 1000}]
        metadata = {"total_results": 1, "avg_similarity": 0.85}

        result = SearchResult(success=True, products=products, source="pgvector", metadata=metadata)

        assert result.success is True
        assert len(result.products) == 1
        assert result.source == "pgvector"
        assert result.metadata["total_results"] == 1
        assert result.error is None

    def test_create_failed_result(self):
        """Test creating failed search result."""
        result = SearchResult(success=False, products=[], source="pgvector", error="Connection timeout")

        assert result.success is False
        assert len(result.products) == 0
        assert result.source == "pgvector"
        assert result.error == "Connection timeout"

    def test_empty_metadata(self):
        """Test creating result with no metadata."""
        result = SearchResult(success=True, products=[], source="database")

        assert result.metadata == {}

    def test_invalid_products_type(self):
        """Test validation of products field."""
        with pytest.raises(ValueError, match="products must be a list"):
            SearchResult(success=True, products="not a list", source="pgvector")  # type: ignore

    def test_invalid_metadata_type(self):
        """Test validation of metadata field."""
        with pytest.raises(ValueError, match="metadata must be a dict"):
            SearchResult(success=True, products=[], source="pgvector", metadata="not a dict")  # type: ignore


class TestSearchStrategyType:
    """Tests for SearchStrategyType enum."""

    def test_enum_values(self):
        """Test enum has expected values."""
        assert SearchStrategyType.PGVECTOR.value == "pgvector"
        assert SearchStrategyType.DATABASE.value == "database"

    def test_enum_string_conversion(self):
        """Test enum converts to string properly."""
        assert str(SearchStrategyType.PGVECTOR) == "pgvector"
        assert str(SearchStrategyType.DATABASE) == "database"

    def test_enum_iteration(self):
        """Test iterating over enum members."""
        strategy_names = [strategy.value for strategy in SearchStrategyType]

        assert "pgvector" in strategy_names
        assert "database" in strategy_names
        assert len(strategy_names) == 2

    def test_enum_comparison(self):
        """Test enum member comparison."""
        assert SearchStrategyType.PGVECTOR == SearchStrategyType.PGVECTOR
        assert SearchStrategyType.PGVECTOR != SearchStrategyType.DATABASE
        assert SearchStrategyType("pgvector") == SearchStrategyType.PGVECTOR