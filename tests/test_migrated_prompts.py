"""
Tests para verificar que los prompts migrados se cargan correctamente.
"""

import pytest

from app.prompts import PromptManager, PromptRegistry


# Todos los prompts migrados agrupados por prioridad
MIGRATED_PROMPTS = {
    "alta_prioridad": [
        PromptRegistry.ORCHESTRATOR_ROUTING_DOMAIN_CLASSIFIER,
        PromptRegistry.ORCHESTRATOR_ROUTING_DOMAIN_CLASSIFIER_WITH_REASONING,
        PromptRegistry.ECOMMERCE_ROUTER_INTENT_CLASSIFIER,
        PromptRegistry.ECOMMERCE_ROUTER_USER_CONTEXT,
        PromptRegistry.ECOMMERCE_PRODUCT_RESPONSE,
        PromptRegistry.ECOMMERCE_PRODUCT_NO_RESULTS,
        PromptRegistry.ECOMMERCE_PRODUCT_STOCK_ALL_AVAILABLE,
        PromptRegistry.ECOMMERCE_PRODUCT_STOCK_MIXED,
        PromptRegistry.ECOMMERCE_PRODUCT_STOCK_NONE_AVAILABLE,
        PromptRegistry.AGENTS_DATA_INSIGHTS_SYSTEM_CLASSIFIER,
        PromptRegistry.AGENTS_DATA_INSIGHTS_SYSTEM_ANALYST,
        PromptRegistry.AGENTS_DATA_INSIGHTS_SYSTEM_NO_RESULTS,
        PromptRegistry.AGENTS_DATA_INSIGHTS_SYSTEM_ERROR_HANDLER,
    ],
    "media_prioridad": [
        PromptRegistry.ECOMMERCE_PRODUCT_SQL_BUILDER_SYSTEM,
        PromptRegistry.ECOMMERCE_PRODUCT_SQL_AGGREGATION_SYSTEM,
        PromptRegistry.ECOMMERCE_PRODUCT_SQL_ANALYZER_SYSTEM,
        PromptRegistry.TOOLS_DYNAMIC_SQL_QUERY_GENERATOR_SYSTEM,
        PromptRegistry.TOOLS_DYNAMIC_SQL_INTENT_ANALYZER_SYSTEM,
        PromptRegistry.TOOLS_DYNAMIC_SQL_CONTEXT_GENERATOR_SYSTEM,
        PromptRegistry.HEALTHCARE_AGENTS_APPOINTMENT_SYSTEM,
        PromptRegistry.HEALTHCARE_AGENTS_PATIENT_RECORDS_SYSTEM,
        PromptRegistry.HEALTHCARE_AGENTS_TRIAGE_SYSTEM,
        PromptRegistry.HEALTHCARE_AGENTS_DOCTOR_SEARCH_SYSTEM,
        PromptRegistry.HEALTHCARE_AGENTS_EMERGENCY_RESPONSE,
    ],
    "baja_prioridad": [
        PromptRegistry.CORE_CIRCUIT_BREAKER_HEALTH_CHECK_SYSTEM,
        PromptRegistry.CORE_CIRCUIT_BREAKER_HEALTH_CHECK_USER,
        PromptRegistry.AGENTS_SUPERVISOR_ENHANCEMENT_FALLBACK,
        PromptRegistry.EXCELENCIA_INCIDENT_ERROR_CREATION,
    ],
}


@pytest.mark.asyncio
class TestMigratedPrompts:
    """Tests para prompts migrados a YAML."""

    async def test_alta_prioridad_prompts_load(self):
        """Verifica que los prompts de alta prioridad se cargan."""
        manager = PromptManager()
        
        for key in MIGRATED_PROMPTS["alta_prioridad"]:
            prompt = await manager.get_prompt(key, prefer_db=False)
            assert prompt is not None, f"Prompt '{key}' no se pudo cargar"
            assert len(prompt) > 0, f"Prompt '{key}' está vacío"

    async def test_media_prioridad_prompts_load(self):
        """Verifica que los prompts de media prioridad se cargan."""
        manager = PromptManager()
        
        for key in MIGRATED_PROMPTS["media_prioridad"]:
            prompt = await manager.get_prompt(key, prefer_db=False)
            assert prompt is not None, f"Prompt '{key}' no se pudo cargar"
            assert len(prompt) > 0, f"Prompt '{key}' está vacío"

    async def test_baja_prioridad_prompts_load(self):
        """Verifica que los prompts de baja prioridad se cargan."""
        manager = PromptManager()
        
        for key in MIGRATED_PROMPTS["baja_prioridad"]:
            prompt = await manager.get_prompt(key, prefer_db=False)
            assert prompt is not None, f"Prompt '{key}' no se pudo cargar"
            assert len(prompt) > 0, f"Prompt '{key}' está vacío"

    async def test_all_migrated_prompts_in_registry(self):
        """Verifica que todos los prompts migrados están en el registry."""
        all_keys = PromptRegistry.get_all_keys()
        
        for priority, keys in MIGRATED_PROMPTS.items():
            for key in keys:
                assert key in all_keys, f"Prompt '{key}' ({priority}) no está en el registry"

    async def test_prompt_variables_render(self):
        """Verifica que los prompts con variables se renderizan correctamente."""
        manager = PromptManager()

        # Test ECOMMERCE_PRODUCT_RESPONSE con variables correctas
        prompt = await manager.get_prompt(
            PromptRegistry.ECOMMERCE_PRODUCT_RESPONSE,
            variables={
                "user_query": "buscar laptops",
                "intent": "product_search",
                "product_count": "5",
                "formatted_products": "[{\"name\": \"Test Laptop\"}]",
                "stock_info": "Disponible",
            },
            prefer_db=False,
        )
        assert "buscar laptops" in prompt
        assert "5" in prompt

        # Test HEALTHCARE_AGENTS_APPOINTMENT_SYSTEM con variables
        prompt = await manager.get_prompt(
            PromptRegistry.HEALTHCARE_AGENTS_APPOINTMENT_SYSTEM,
            variables={"message": "Quiero agendar una cita"},
            prefer_db=False,
        )
        assert "cita" in prompt.lower() or "appointment" in prompt.lower()

    async def test_total_migrated_count(self):
        """Verifica el conteo total de prompts migrados."""
        total = sum(len(keys) for keys in MIGRATED_PROMPTS.values())
        assert total == 28, f"Se esperaban 28 prompts, se encontraron {total}"
