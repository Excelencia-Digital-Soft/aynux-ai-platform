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
        try:
            # Load both prompts from YAML
            system_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.ECOMMERCE_PRODUCT_SQL_ANALYZER_SYSTEM,
            )
            user_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.ECOMMERCE_PRODUCT_SQL_COMPLEXITY_ANALYSIS,
                variables={
                    "user_query": user_query,
                    "intent_json": json.dumps(intent, indent=2),
                },
            )
            response = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
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
