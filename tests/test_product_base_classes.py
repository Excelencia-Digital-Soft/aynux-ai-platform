"""
Unit tests for product agent base classes.

Tests:
- BaseSearchStrategy abstract class
- BaseResponseGenerator abstract class
"""

import pytest

from app.agents.integrations.ollama_integration import OllamaIntegration
from app.agents.product.generators.base_generator import BaseResponseGenerator
from app.agents.product.models import SearchResult, UserIntent
from app.agents.product.strategies.base_strategy import BaseSearchStrategy


class ConcreteSearchStrategy(BaseSearchStrategy):
    """Concrete implementation for testing."""

    async def search(self, query: str, intent: UserIntent, max_results: int) -> SearchResult:
        return SearchResult(success=True, products=[], source="test")

    @property
    def strategy_name(self) -> str:
        return "test_strategy"

    async def health_check(self) -> bool:
        return True


class ConcreteResponseGenerator(BaseResponseGenerator):
    """Concrete implementation for testing."""

    async def generate_response(self, products, user_message, intent, search_metadata) -> str:
        return "Test response"

    def get_fallback_response(self, products, metadata) -> str:
        return "Fallback response"


class TestBaseSearchStrategy:
    """Tests for BaseSearchStrategy abstract class."""

    def test_create_strategy(self):
        """Test creating strategy with config."""
        config = {"similarity_threshold": 0.7}
        strategy = ConcreteSearchStrategy(config)

        assert strategy.config == config
        assert strategy.strategy_name == "test_strategy"

    @pytest.mark.asyncio
    async def test_search_method(self):
        """Test search method is implemented."""
        strategy = ConcreteSearchStrategy({})
        intent = UserIntent(intent="test", search_terms=["laptop"])

        result = await strategy.search("laptop", intent, 10)

        assert isinstance(result, SearchResult)
        assert result.success is True
        assert result.source == "test"

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check method."""
        strategy = ConcreteSearchStrategy({})

        is_healthy = await strategy.health_check()

        assert is_healthy is True

    def test_get_config(self):
        """Test getting configuration."""
        config = {"threshold": 0.7, "max_results": 10}
        strategy = ConcreteSearchStrategy(config)

        retrieved_config = strategy.get_config()

        assert retrieved_config == config
        # Ensure it's a copy
        retrieved_config["new_key"] = "new_value"
        assert "new_key" not in strategy.config

    def test_update_config(self):
        """Test updating configuration."""
        strategy = ConcreteSearchStrategy({"threshold": 0.5})

        strategy.update_config({"threshold": 0.7, "new_param": "value"})

        assert strategy.config["threshold"] == 0.7
        assert strategy.config["new_param"] == "value"

    def test_get_trace_metadata(self):
        """Test getting trace metadata."""
        config = {"threshold": 0.7}
        strategy = ConcreteSearchStrategy(config)

        metadata = strategy.get_trace_metadata()

        assert metadata["strategy_name"] == "test_strategy"
        assert metadata["strategy_class"] == "ConcreteSearchStrategy"
        assert metadata["config"] == config

    def test_log_search_start(self):
        """Test logging helper method."""
        strategy = ConcreteSearchStrategy({})
        intent = UserIntent(intent="test", search_terms=["laptop"])

        # Should not raise exception
        strategy._log_search_start("test query", intent, 10)

    def test_log_search_result(self):
        """Test result logging helper method."""
        strategy = ConcreteSearchStrategy({})
        result = SearchResult(success=True, products=[{"id": "1"}], source="test", metadata={})

        # Should not raise exception
        strategy._log_search_result(result)


class TestBaseResponseGenerator:
    """Tests for BaseResponseGenerator abstract class."""

    def test_create_generator(self):
        """Test creating generator with dependencies."""
        ollama = OllamaIntegration()
        config = {"temperature": 0.7}

        generator = ConcreteResponseGenerator(ollama, config)

        assert generator.ollama is ollama
        assert generator.config == config

    @pytest.mark.asyncio
    async def test_generate_response(self):
        """Test response generation method."""
        generator = ConcreteResponseGenerator(OllamaIntegration(), {})
        products = [{"id": "1", "name": "Laptop"}]
        intent = UserIntent(intent="test", search_terms=["laptop"])

        response = await generator.generate_response(products, "test message", intent, {})

        assert isinstance(response, str)
        assert response == "Test response"

    def test_get_fallback_response(self):
        """Test fallback response method."""
        generator = ConcreteResponseGenerator(OllamaIntegration(), {})
        products = [{"id": "1", "name": "Laptop"}]

        response = generator.get_fallback_response(products, {})

        assert isinstance(response, str)
        assert response == "Fallback response"

    def test_format_products_for_prompt(self):
        """Test formatting products."""
        generator = ConcreteResponseGenerator(OllamaIntegration(), {})
        products = [
            {"name": "Laptop ASUS", "brand": {"name": "ASUS"}, "price": 1000, "stock": 10, "similarity_score": 0.95}
        ]

        formatted = generator._format_products_for_prompt(products)

        assert "Laptop ASUS" in formatted
        assert "ASUS" in formatted
        assert "1,000.00" in formatted
        assert "✅ In stock" in formatted
        assert "0.95" in formatted

    def test_format_empty_products(self):
        """Test formatting empty product list."""
        generator = ConcreteResponseGenerator(OllamaIntegration(), {})

        formatted = generator._format_products_for_prompt([])

        assert formatted == "No products found."

    def test_format_metadata_for_prompt(self):
        """Test formatting metadata."""
        generator = ConcreteResponseGenerator(OllamaIntegration(), {})
        metadata = {"total_results": 10, "avg_similarity": 0.85, "query": "laptop gaming"}

        formatted = generator._format_metadata_for_prompt(metadata)

        assert "total_results: 10" in formatted
        assert "avg_similarity: 0.85" in formatted
        assert "query: laptop gaming" in formatted

    def test_format_empty_metadata(self):
        """Test formatting empty metadata."""
        generator = ConcreteResponseGenerator(OllamaIntegration(), {})

        formatted = generator._format_metadata_for_prompt({})

        assert formatted == "No additional metadata"

    def test_get_config(self):
        """Test getting configuration."""
        config = {"temperature": 0.7}
        generator = ConcreteResponseGenerator(OllamaIntegration(), config)

        retrieved_config = generator.get_config()

        assert retrieved_config == config

    def test_update_config(self):
        """Test updating configuration."""
        generator = ConcreteResponseGenerator(OllamaIntegration(), {"temperature": 0.5})

        generator.update_config({"temperature": 0.8, "max_tokens": 500})

        assert generator.config["temperature"] == 0.8
        assert generator.config["max_tokens"] == 500

    def test_get_trace_metadata(self):
        """Test getting trace metadata."""
        config = {"temperature": 0.7}
        generator = ConcreteResponseGenerator(OllamaIntegration(), config)

        metadata = generator.get_trace_metadata()

        assert metadata["generator_class"] == "ConcreteResponseGenerator"
        assert metadata["config"] == config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])