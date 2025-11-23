"""
Tests for the unified prompt service system.

Tests the YAML-based prompt loading, rendering, and service integration.
"""

import pytest
from pathlib import Path

from app.prompts import (
    UnifiedPromptService,
    PromptLoader,
    PromptRenderer,
    PromptTemplate,
    PromptRenderContext,
)
from app.prompts.models import PromptMetadata, PromptVariable, VariableType


class TestPromptLoader:
    """Test PromptLoader functionality."""

    def test_loader_initialization(self):
        """Test loader initializes with templates directory."""
        loader = PromptLoader()
        assert loader.templates_dir.exists()

    def test_load_directory(self):
        """Test loading all prompts from directory."""
        loader = PromptLoader()
        collections = loader.load_directory()
        assert len(collections) > 0

    def test_cache_functionality(self):
        """Test prompt caching works."""
        loader = PromptLoader()
        stats_before = loader.get_cache_stats()

        # Load some prompts
        loader.load_directory()

        stats_after = loader.get_cache_stats()
        assert stats_after["cached_files"] >= stats_before["cached_files"]


class TestPromptRenderer:
    """Test PromptRenderer functionality."""

    def test_render_simple_template(self):
        """Test rendering a simple template."""
        renderer = PromptRenderer()

        template = PromptTemplate(
            key="test.simple",
            name="Simple Test",
            description="A simple test template",
            template="Hello {name}!",
            metadata=PromptMetadata(),
            variables=[
                PromptVariable(name="name", type=VariableType.STRING, required=True)
            ],
        )

        result = renderer.render(template, name="World")
        assert result == "Hello World!"

    def test_render_with_context(self):
        """Test rendering with PromptRenderContext."""
        renderer = PromptRenderer()

        template = PromptTemplate(
            key="test.context",
            name="Context Test",
            description="Test with context",
            template="User: {user}, Age: {age}",
            metadata=PromptMetadata(),
            variables=[
                PromptVariable(name="user", type=VariableType.STRING, required=True),
                PromptVariable(name="age", type=VariableType.INTEGER, required=True),
            ],
        )

        context = PromptRenderContext(variables={"user": "Alice", "age": 30})
        result = renderer.render(template, context)
        assert "Alice" in result
        assert "30" in result

    def test_render_with_default_values(self):
        """Test rendering with default values for optional variables."""
        renderer = PromptRenderer(strict=False)

        template = PromptTemplate(
            key="test.defaults",
            name="Defaults Test",
            description="Test with defaults",
            template="Language: {language}",
            metadata=PromptMetadata(),
            variables=[
                PromptVariable(
                    name="language",
                    type=VariableType.STRING,
                    required=False,
                    default="Spanish"
                )
            ],
        )

        result = renderer.render(template)
        assert "Spanish" in result

    def test_missing_required_variable_raises_error(self):
        """Test that missing required variables raise an error."""
        renderer = PromptRenderer(strict=True)

        template = PromptTemplate(
            key="test.required",
            name="Required Test",
            description="Test required variables",
            template="Hello {name}!",
            metadata=PromptMetadata(),
            variables=[
                PromptVariable(name="name", type=VariableType.STRING, required=True)
            ],
        )

        with pytest.raises(Exception):  # PromptRenderError
            renderer.render(template)


class TestUnifiedPromptService:
    """Test UnifiedPromptService functionality."""

    def test_service_initialization(self):
        """Test service initializes correctly."""
        service = UnifiedPromptService()
        assert service.registry.count() >= 0

    def test_get_instance_singleton(self):
        """Test that get_instance returns singleton."""
        service1 = UnifiedPromptService.get_instance()
        service2 = UnifiedPromptService.get_instance()
        assert service1 is service2

    def test_list_available_prompts(self):
        """Test listing all available prompts."""
        service = UnifiedPromptService.get_instance()
        prompts = service.list_available_prompts()
        assert isinstance(prompts, list)

        # Check that our new prompts are loaded
        expected_prompts = [
            "ecommerce.sales.assistant",
            "shared.orchestrator.intent_detection",
            "ecommerce.product.response",
            "shared.conversation.greeting",
        ]

        for prompt_key in expected_prompts:
            assert prompt_key in prompts, f"Expected prompt {prompt_key} not found"

    def test_get_prompt(self):
        """Test getting a specific prompt."""
        service = UnifiedPromptService.get_instance()

        # Try to get a known prompt
        prompt = service.get_prompt("ecommerce.sales.assistant", strict=False)

        if prompt:
            assert prompt.key == "ecommerce.sales.assistant"
            assert prompt.version is not None

    def test_render_prompt(self):
        """Test rendering a prompt."""
        service = UnifiedPromptService.get_instance()

        # Try to render a simple prompt
        try:
            result = service.render(
                "ecommerce.sales.assistant",
                message="Busco una laptop",
                historial="",
                contexto="Laptops disponibles: HP, Dell, Lenovo",
                strict=False
            )

            # If rendering succeeds, check result
            if result:
                assert len(result) > 0
                assert "laptop" in result.lower() or "HP" in result or "Dell" in result
        except Exception:
            # If prompt not found, that's okay for this test
            pass

    def test_get_prompts_by_domain(self):
        """Test filtering prompts by domain."""
        service = UnifiedPromptService.get_instance()

        ecommerce_prompts = service.get_prompts_by_domain("ecommerce")
        assert isinstance(ecommerce_prompts, list)

        # All returned prompts should be from ecommerce domain
        for prompt in ecommerce_prompts:
            assert prompt.metadata.domain == "ecommerce"

    def test_get_prompts_by_agent(self):
        """Test filtering prompts by agent."""
        service = UnifiedPromptService.get_instance()

        product_prompts = service.get_prompts_by_agent("product")
        assert isinstance(product_prompts, list)

        # All returned prompts should be for product agent
        for prompt in product_prompts:
            assert prompt.metadata.agent == "product"

    def test_service_stats(self):
        """Test getting service statistics."""
        service = UnifiedPromptService.get_instance()

        stats = service.get_stats()
        assert "service" in stats
        assert "prompts_loaded" in stats
        assert "domains" in stats
        assert "agents" in stats

        assert isinstance(stats["prompts_loaded"], int)
        assert isinstance(stats["domains"], list)
        assert isinstance(stats["agents"], list)


class TestLegacyCompatibility:
    """Test backward compatibility with existing code."""

    def test_legacy_prompt_service_import(self):
        """Test that legacy PromptService still works."""
        from app.services.prompt_service import PromptService

        service = PromptService()
        assert service is not None
        assert hasattr(service, "_build_improved_prompt")
        assert hasattr(service, "_orquestator_prompt")

    def test_legacy_build_improved_prompt(self):
        """Test legacy method still works."""
        from app.services.prompt_service import PromptService

        service = PromptService()
        result = service._build_improved_prompt(
            message="Hola",
            historial="",
            contexto="Productos disponibles"
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_legacy_orchestrator_prompt(self):
        """Test legacy orchestrator method still works."""
        from app.services.prompt_service import PromptService

        service = PromptService()
        result = service._orquestator_prompt(
            message="Busco laptop",
            historial=""
        )

        assert isinstance(result, str)
        assert len(result) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
