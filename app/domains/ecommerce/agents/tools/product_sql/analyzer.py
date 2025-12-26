"""
Query Complexity Analyzer.

Single Responsibility: Analyze query complexity to optimize SQL generation.
"""

import json
import logging
from typing import Any

from app.integrations.llm import OllamaLLM
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class QueryComplexityAnalyzer:
    """Analyzes query complexity for SQL optimization."""

    def __init__(self, ollama: OllamaLLM):
        self.ollama = ollama
        self.prompt_manager = PromptManager()

    async def analyze(self, user_query: str, intent: dict[str, Any]) -> dict[str, Any]:
        """
        Analiza la complejidad de la consulta para optimizar la generación de SQL.
        """
        complexity_prompt = f"""# ANÁLISIS DE COMPLEJIDAD DE CONSULTA

CONSULTA: "{user_query}"

INTENCIÓN DETECTADA:
{json.dumps(intent, indent=2)}

Analiza la complejidad y responde en JSON:

{{
  "complexity_level": "simple|medium|complex|very_complex",
  "requires_joins": bool,
  "requires_aggregation": bool,
  "requires_subqueries": bool,
  "requires_full_text_search": bool,
  "tables_needed": ["products", "categories", "brands"],
  "estimated_query_type": "simple_select|filtered_search|aggregated_report|complex_analysis",
  "optimization_hints": ["índice_sugerido", "join_order"]
}}

CRITERIOS:
- simple: búsqueda básica por nombre/categoría
- medium: filtros múltiples, joins básicos
- complex: agregaciones, subqueries, full-text search
- very_complex: múltiples joins, queries anidadas, análisis estadístico"""

        try:
            # Load system prompt from YAML
            system_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.ECOMMERCE_PRODUCT_SQL_ANALYZER_SYSTEM,
            )
            response = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=complexity_prompt,
                temperature=0.2,
            )

            return json.loads(response)

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Could not parse complexity analysis: {e}")
            return self._create_fallback_analysis(user_query, intent)

    def _create_fallback_analysis(
        self, user_query: str, intent: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Crea análisis de complejidad básico como fallback.
        """
        query_lower = user_query.lower()

        # Detectar patrones básicos
        requires_joins = any(
            word in query_lower for word in ["marca", "categoría", "brand", "category"]
        )
        requires_aggregation = any(
            word in query_lower
            for word in ["total", "promedio", "suma", "count", "cuántos"]
        )

        if requires_aggregation:
            complexity = "complex"
        elif requires_joins and len(intent.get("filters", {})) > 2:
            complexity = "medium"
        else:
            complexity = "simple"

        return {
            "complexity_level": complexity,
            "requires_joins": requires_joins,
            "requires_aggregation": requires_aggregation,
            "requires_subqueries": False,
            "requires_full_text_search": True,
            "tables_needed": ["products", "categories", "brands"],
            "estimated_query_type": "filtered_search",
            "optimization_hints": ["index_on_name", "join_categories_brands"],
        }
