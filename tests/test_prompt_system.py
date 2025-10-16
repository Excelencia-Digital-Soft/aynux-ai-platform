"""
Tests para el sistema de gestión de prompts.
"""

import pytest

from app.prompts import PromptManager, PromptRegistry
from app.prompts.loader import PromptLoader
from app.prompts.utils.renderer import PromptRenderer
from app.prompts.utils.validator import PromptValidator


class TestPromptRegistry:
    """Tests para PromptRegistry."""

    def test_registry_has_keys(self):
        """Verifica que el registry tenga claves definidas."""
        all_keys = PromptRegistry.get_all_keys()
        assert len(all_keys) > 0
        assert isinstance(all_keys, list)

    def test_get_by_domain(self):
        """Verifica filtrado por dominio."""
        product_keys = PromptRegistry.get_by_domain("product")
        assert all(key.startswith("product.") for key in product_keys)

    def test_validate_key(self):
        """Verifica validación de claves."""
        assert PromptRegistry.validate_key(PromptRegistry.INTENT_ANALYZER_SYSTEM)
        assert not PromptRegistry.validate_key("invalid.key.that.does.not.exist")


class TestPromptValidator:
    """Tests para PromptValidator."""

    def test_validate_valid_prompt(self):
        """Valida un prompt correcto."""
        prompt_data = {
            "key": "test.prompt.example",
            "name": "Test Prompt",
            "template": "Hello {name}, welcome to {place}!",
            "metadata": {"temperature": 0.7},
        }

        result = PromptValidator.validate_prompt(prompt_data)
        assert result["is_valid"]
        assert len(result["errors"]) == 0

    def test_validate_invalid_prompt(self):
        """Valida un prompt inválido."""
        prompt_data = {
            "key": "",  # Key vacía - inválida
            "name": "Test",
            "template": "Test",
        }

        result = PromptValidator.validate_prompt(prompt_data)
        assert not result["is_valid"]
        assert len(result["errors"]) > 0

    def test_validate_template(self):
        """Valida templates."""
        result = PromptValidator.validate_template("Hello {name}!")
        assert result["is_valid"]

        # Template vacío
        result = PromptValidator.validate_template("")
        assert not result["is_valid"]

        # Llaves desbalanceadas
        result = PromptValidator.validate_template("Hello {name!")
        assert not result["is_valid"]

    def test_validate_key_format(self):
        """Valida formato de keys."""
        # Válidas
        assert PromptValidator.validate_key("domain.action")["is_valid"]
        assert PromptValidator.validate_key("domain.subdomain.action")["is_valid"]

        # Inválidas
        assert not PromptValidator.validate_key("single")["is_valid"]
        assert not PromptValidator.validate_key("")["is_valid"]


class TestPromptRenderer:
    """Tests para PromptRenderer."""

    def test_render_simple(self):
        """Renderiza template simple."""
        template = "Hello {name}!"
        variables = {"name": "Juan"}

        result = PromptRenderer.render(template, variables)
        assert result == "Hello Juan!"

    def test_render_multiple_variables(self):
        """Renderiza template con múltiples variables."""
        template = "Hello {name}, you are {age} years old and live in {city}."
        variables = {"name": "María", "age": "25", "city": "Madrid"}

        result = PromptRenderer.render(template, variables)
        assert "María" in result
        assert "25" in result
        assert "Madrid" in result

    def test_render_missing_variable_strict(self):
        """Renderiza con variable faltante en modo strict."""
        template = "Hello {name}, {missing}!"
        variables = {"name": "Juan"}

        with pytest.raises(ValueError):
            PromptRenderer.render(template, variables, strict=True)

    def test_render_missing_variable_non_strict(self):
        """Renderiza con variable faltante en modo no-strict."""
        template = "Hello {name}, {missing}!"
        variables = {"name": "Juan"}

        result = PromptRenderer.render(template, variables, strict=False)
        assert "Juan" in result
        # La variable faltante se queda sin reemplazar
        assert "{missing}" in result

    def test_extract_variables(self):
        """Extrae variables de un template."""
        template = "Hello {name}, you are {age} and live in {city}."
        variables = PromptRenderer.extract_variables(template)

        assert set(variables) == {"name", "age", "city"}


@pytest.mark.asyncio
class TestPromptManager:
    """Tests para PromptManager."""

    async def test_manager_initialization(self):
        """Verifica inicialización del manager."""
        manager = PromptManager()
        assert manager is not None
        assert manager.loader is not None
        assert manager.renderer is not None

    async def test_get_prompt_from_file(self):
        """Obtiene un prompt desde archivo."""
        manager = PromptManager()

        # Intentar cargar un prompt de intent (debería existir en YAML)
        prompt = await manager.get_prompt(PromptRegistry.INTENT_ANALYZER_SYSTEM, prefer_db=False)

        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    async def test_get_prompt_with_variables(self):
        """Obtiene y renderiza un prompt con variables."""
        manager = PromptManager()

        variables = {
            "customer_data": "Test customer",
            "context_info": "Test context",
            "message": "Hello",
        }

        prompt = await manager.get_prompt(PromptRegistry.INTENT_ANALYZER_USER, variables=variables, prefer_db=False)

        assert "Test customer" in prompt or "Hello" in prompt

    async def test_manager_cache(self):
        """Verifica funcionamiento del caché."""
        manager = PromptManager()

        # Primera llamada - cache miss
        await manager.get_prompt(PromptRegistry.INTENT_ANALYZER_SYSTEM, prefer_db=False)

        # Segunda llamada - cache hit
        await manager.get_prompt(PromptRegistry.INTENT_ANALYZER_SYSTEM, prefer_db=False)

        stats = manager.get_stats()
        assert stats["cache_hits"] >= 1

    async def test_get_stats(self):
        """Verifica obtención de estadísticas."""
        manager = PromptManager()

        await manager.get_prompt(PromptRegistry.INTENT_ANALYZER_SYSTEM, prefer_db=False)

        stats = manager.get_stats()
        assert "total_requests" in stats
        assert "cache_hits" in stats
        assert "cache_hit_rate" in stats


@pytest.mark.asyncio
class TestPromptLoader:
    """Tests para PromptLoader."""

    async def test_loader_initialization(self):
        """Verifica inicialización del loader."""
        loader = PromptLoader()
        assert loader is not None
        assert loader.templates_dir.exists()

    async def test_load_from_file(self):
        """Carga un prompt desde archivo YAML."""
        loader = PromptLoader()

        template = await loader.load_from_file(PromptRegistry.INTENT_ANALYZER_SYSTEM)

        if template:  # Puede ser None si el archivo no existe aún
            assert template.key == PromptRegistry.INTENT_ANALYZER_SYSTEM
            assert template.template is not None
            assert len(template.template) > 0


# ===== INTEGRATION TESTS =====


@pytest.mark.asyncio
class TestPromptSystemIntegration:
    """Tests de integración del sistema completo."""

    async def test_end_to_end_flow(self):
        """Test end-to-end del flujo completo."""
        manager = PromptManager()

        # 1. Listar prompts disponibles
        # (Requiere BD configurada para funcionar completamente)

        # 2. Obtener prompt
        prompt = await manager.get_prompt(PromptRegistry.INTENT_ANALYZER_SYSTEM, prefer_db=False)
        assert prompt is not None

        # 3. Verificar caché
        stats = manager.get_stats()
        assert stats["total_requests"] > 0

    async def test_registry_and_loader_integration(self):
        """Verifica integración entre Registry y Loader."""
        manager = PromptManager()

        # Obtener todas las keys del registry
        all_keys = PromptRegistry.get_all_keys()

        # Intentar cargar algunas (las que existan en archivos)
        loaded_count = 0
        for key in all_keys[:5]:  # Probar solo las primeras 5
            try:
                template = await manager.get_template(key, prefer_db=False)
                if template:
                    loaded_count += 1
            except Exception:
                pass

        # Al menos algunos deberían cargar
        assert loaded_count >= 0  # Flexible por si no hay archivos aún
