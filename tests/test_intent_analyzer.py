"""
Unit tests for IntentAnalyzer.

Tests:
- Intent analysis with mocked vLLM integration
- Default intent fallback behavior
- Temperature configuration
- Error handling and recovery
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.domains.ecommerce.agents.product.intent_analyzer import IntentAnalyzer
from app.domains.ecommerce.agents.product.models import UserIntent
from app.integrations.llm.model_provider import ModelComplexity


class TestIntentAnalyzer:
    """Tests for IntentAnalyzer class."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock VllmLLM."""
        llm = Mock()
        return llm

    @pytest.fixture
    def analyzer(self, mock_llm):
        """Create IntentAnalyzer with mock dependencies."""
        return IntentAnalyzer(llm=mock_llm, temperature=0.3)

    @pytest.mark.asyncio
    async def test_analyze_intent_success(self, analyzer, mock_llm):
        """Test successful intent analysis."""
        # Mock LLM response
        mock_llm_instance = AsyncMock()
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "intent": "search_specific_products",
                "search_terms": ["laptop", "gaming"],
                "category": "laptops",
                "brand": "ASUS",
                "price_min": 500.0,
                "price_max": 1500.0,
                "wants_stock_info": True,
                "action_needed": "search_products",
            }
        )
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_llm.get_llm.return_value = mock_llm_instance

        with patch.object(analyzer.prompt_manager, "get_prompt", new_callable=AsyncMock) as mock_get_prompt:
            mock_get_prompt.return_value = "Mocked prompt"
            # Execute
            intent = await analyzer.analyze_intent("Show me ASUS gaming laptops")

            # Verify
            assert isinstance(intent, UserIntent)
            assert intent.intent == "search_specific_products"
            assert intent.search_terms == ["laptop", "gaming"]
            assert intent.category == "laptops"
            assert intent.brand == "ASUS"
            assert intent.price_min == 500.0
            assert intent.price_max == 1500.0
            assert intent.wants_stock_info is True
            mock_llm.get_llm.assert_called_once_with(
                complexity=ModelComplexity.SIMPLE, temperature=0.3, model=None
            )

    @pytest.mark.asyncio
    async def test_analyze_intent_partial_json(self, analyzer, mock_llm):
        """Test intent analysis with partial JSON response."""
        # Mock LLM response with only required fields
        mock_llm_instance = AsyncMock()
        mock_response = Mock()
        mock_response.content = json.dumps({"intent": "search_by_category", "search_terms": ["laptop"], "category": "laptops"})
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_llm.get_llm.return_value = mock_llm_instance

        # Execute
        intent = await analyzer.analyze_intent("Show me laptops")

        # Verify - missing fields should have defaults
        assert intent.intent == "search_by_category"
        assert intent.search_terms == ["laptop"]
        assert intent.category == "laptops"
        assert intent.brand is None  # Default
        assert intent.price_min is None  # Default
        assert intent.wants_stock_info is False  # Default

    @pytest.mark.asyncio
    async def test_analyze_intent_malformed_json(self, analyzer, mock_llm):
        """Test intent analysis with malformed JSON response."""
        # Mock LLM response with invalid JSON
        mock_llm_instance = AsyncMock()
        mock_response = Mock()
        mock_response.content = "This is not valid JSON"
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_llm.get_llm.return_value = mock_llm_instance

        # Execute
        intent = await analyzer.analyze_intent("Show me products")

        # Verify - should return default intent
        assert intent.intent == "search_general"
        assert intent.search_terms == ["Show", "me", "products"]
        assert intent.action_needed == "search_products"

    @pytest.mark.asyncio
    async def test_analyze_intent_llm_error(self, analyzer, mock_llm):
        """Test intent analysis when LLM raises exception."""
        # Mock LLM to raise exception
        mock_llm_instance = AsyncMock()
        mock_llm_instance.ainvoke.side_effect = Exception("LLM connection error")
        mock_llm.get_llm.return_value = mock_llm_instance

        # Execute
        intent = await analyzer.analyze_intent("Show me products")

        # Verify - should return default intent
        assert intent.intent == "search_general"
        assert intent.search_terms == ["Show", "me", "products"]
        assert intent.action_needed == "search_products"

    @pytest.mark.asyncio
    async def test_analyze_intent_empty_message(self, analyzer, mock_llm):
        """Test intent analysis with empty message."""
        # Mock LLM response
        mock_llm_instance = AsyncMock()
        mock_response = Mock()
        mock_response.content = json.dumps({"intent": "search_general", "search_terms": []})
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_llm.get_llm.return_value = mock_llm_instance

        # Execute
        intent = await analyzer.analyze_intent("")

        # Verify
        assert isinstance(intent, UserIntent)
        assert intent.intent == "search_general"

    @pytest.mark.asyncio
    async def test_analyze_intent_custom_temperature(self, mock_llm):
        """Test intent analysis with custom temperature."""
        # Create analyzer with custom temperature
        analyzer = IntentAnalyzer(llm=mock_llm, temperature=0.7)

        # Mock LLM response
        mock_llm_instance = AsyncMock()
        mock_response = Mock()
        mock_response.content = json.dumps({"intent": "search_general", "search_terms": ["test"]})
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_llm.get_llm.return_value = mock_llm_instance

        with patch.object(analyzer.prompt_manager, "get_prompt", new_callable=AsyncMock) as mock_get_prompt:
            mock_get_prompt.return_value = "Mocked prompt"
            # Execute
            await analyzer.analyze_intent("test message")

            # Verify temperature was used
            mock_llm.get_llm.assert_called_once_with(
                complexity=ModelComplexity.SIMPLE, temperature=0.7, model=None
            )

    @pytest.mark.asyncio
    async def test_analyze_intent_custom_model(self, mock_llm):
        """Test intent analysis with custom model."""
        # Create analyzer with custom model
        analyzer = IntentAnalyzer(llm=mock_llm, model="custom-model:latest")

        # Mock LLM response
        mock_llm_instance = AsyncMock()
        mock_response = Mock()
        mock_response.content = json.dumps({"intent": "search_general", "search_terms": ["test"]})
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_llm.get_llm.return_value = mock_llm_instance

        with patch.object(analyzer.prompt_manager, "get_prompt", new_callable=AsyncMock) as mock_get_prompt:
            mock_get_prompt.return_value = "Mocked prompt"
            # Execute
            await analyzer.analyze_intent("test message")

            # Verify model was used
            mock_llm.get_llm.assert_called_once_with(
                complexity=ModelComplexity.SIMPLE, temperature=0.3, model="custom-model:latest"
            )

    def test_get_default_intent(self, analyzer):
        """Test getting default intent for a message."""
        # Execute
        intent = analyzer.get_default_intent("laptop gaming ASUS")

        # Verify
        assert isinstance(intent, UserIntent)
        assert intent.intent == "search_general"
        assert intent.search_terms == ["laptop", "gaming", "ASUS"]
        assert intent.category is None
        assert intent.brand is None
        assert intent.action_needed == "search_products"

    def test_get_default_intent_empty_message(self, analyzer):
        """Test getting default intent for empty message."""
        # Execute
        intent = analyzer.get_default_intent("")

        # Verify - empty string split() returns empty list
        assert intent.search_terms == []

    def test_update_temperature_valid(self, analyzer):
        """Test updating temperature with valid value."""
        # Execute
        analyzer.update_temperature(0.5)

        # Verify
        assert analyzer.temperature == 0.5

    def test_update_temperature_invalid_high(self, analyzer):
        """Test updating temperature with value too high."""
        with pytest.raises(ValueError, match="Temperature must be between 0.0 and 1.0"):
            analyzer.update_temperature(1.5)

    def test_update_temperature_invalid_low(self, analyzer):
        """Test updating temperature with value too low."""
        with pytest.raises(ValueError, match="Temperature must be between 0.0 and 1.0"):
            analyzer.update_temperature(-0.1)

    def test_update_temperature_boundary_values(self, analyzer):
        """Test updating temperature with boundary values."""
        # Test lower boundary
        analyzer.update_temperature(0.0)
        assert analyzer.temperature == 0.0

        # Test upper boundary
        analyzer.update_temperature(1.0)
        assert analyzer.temperature == 1.0

    @pytest.mark.asyncio
    async def test_intent_analysis_with_json_in_text(self, analyzer, mock_llm):
        """Test intent analysis when JSON is embedded in text."""
        # Mock LLM response with JSON embedded in markdown
        mock_llm_instance = AsyncMock()
        mock_response = Mock()
        mock_response.content = """Here's the analysis:

```json
{
  "intent": "search_by_brand",
  "search_terms": ["phone"],
  "brand": "Samsung"
}
```

Hope this helps!"""
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_llm.get_llm.return_value = mock_llm_instance

        # Execute
        intent = await analyzer.analyze_intent("Show me Samsung phones")

        # Verify - extract_json_from_text should handle embedded JSON
        assert intent.intent == "search_by_brand"
        assert intent.search_terms == ["phone"]
        assert intent.brand == "Samsung"

    @pytest.mark.asyncio
    async def test_intent_analyzer_initialization_defaults(self, mock_llm):
        """Test IntentAnalyzer initialization with default values."""
        analyzer = IntentAnalyzer(llm=mock_llm)

        assert analyzer.temperature == 0.3

    @pytest.mark.asyncio
    async def test_analyze_intent_preserves_all_fields(self, analyzer, mock_llm):
        """Test that all intent fields are properly preserved."""
        # Mock LLM response with all fields
        mock_llm_instance = AsyncMock()
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "intent": "get_product_details",
                "search_terms": ["ASUS", "ROG", "Strix"],
                "category": "gaming-laptops",
                "brand": "ASUS",
                "price_min": 1000.0,
                "price_max": 2000.0,
                "specific_product": "ASUS ROG Strix G15",
                "wants_stock_info": True,
                "wants_featured": False,
                "wants_sale": True,
                "action_needed": "search_products",
            }
        )
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_llm.get_llm.return_value = mock_llm_instance

        # Execute
        intent = await analyzer.analyze_intent("Tell me about ASUS ROG Strix G15")

        # Verify all fields
        assert intent.intent == "get_product_details"
        assert intent.search_terms == ["ASUS", "ROG", "Strix"]
        assert intent.category == "gaming-laptops"
        assert intent.brand == "ASUS"
        assert intent.price_min == 1000.0
        assert intent.price_max == 2000.0
        assert intent.specific_product == "ASUS ROG Strix G15"
        assert intent.wants_stock_info is True
        assert intent.wants_featured is False
        assert intent.wants_sale is True
        assert intent.action_needed == "search_products"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])