"""
SQL Intent Analyzer.

Single Responsibility: Analyze user queries to understand intent and extract components.
"""

import json
import logging
import re
from typing import Any, Dict

from app.integrations.llm import OllamaLLM
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class SQLIntentAnalyzer:
    """
    Analyzes user queries to understand SQL intent.

    Single Responsibility: Extract structured intent data from natural language queries.
    """

    # Table mappings for keyword-based fallback analysis
    TABLE_MAPPINGS = {
        "orders": ["orders", "pedidos", "compras"],
        "products": ["products", "productos", "items"],
        "customers": ["customers", "usuarios", "users", "clientes"],
        "categories": ["categories", "categorias"],
        "brands": ["brands", "marcas"],
        "inventory": ["inventory", "stock", "inventario"],
        "conversations": ["conversations", "conversaciones", "messages"],
        "payments": ["payments", "pagos", "transactions"],
    }

    def __init__(self, ollama: OllamaLLM | None = None):
        """
        Initialize intent analyzer.

        Args:
            ollama: OllamaLLM instance for AI-powered analysis
        """
        self.ollama = ollama or OllamaLLM()
        self.prompt_manager = PromptManager()

    async def analyze(self, user_query: str) -> Dict[str, Any]:
        """
        Analyze user query to understand intent and extract components.

        Args:
            user_query: Natural language query from user

        Returns:
            Dictionary with intent analysis results
        """
        intent_prompt = f"""# ANALISIS DE INTENCION PARA CONSULTA SQL

CONSULTA DEL USUARIO: "{user_query}"

Analiza la consulta y extrae los siguientes componentes en formato JSON:

{{
  "intent_type": "search|count|aggregate|list|comparison|trend",
  "target_entities": ["tabla1", "tabla2"],
  "filters": {{
    "time_range": "last_week|last_month|yesterday|today|specific_date",
    "locations": ["Brasil", "Argentina"],
    "status": ["completed", "pending"],
    "amounts": {{"min": 100, "max": 1000}},
    "user_specific": true
  }},
  "aggregations": ["COUNT", "SUM", "AVG", "MAX", "MIN"],
  "time_columns": ["created_at", "order_date", "updated_at"],
  "grouping": ["country", "category", "month"],
  "sorting": {{"column": "created_at", "direction": "DESC"}},
  "limit": 100,
  "keywords": ["ordenes", "Brasil", "semana pasada"],
  "confidence": 0.9
}}

Responde SOLO el JSON valido:"""

        try:
            # Load system prompt from YAML
            system_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.TOOLS_DYNAMIC_SQL_INTENT_ANALYZER_SYSTEM,
            )
            response = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=intent_prompt,
                temperature=0.1,
            )

            # Clean and parse JSON response
            clean_response = self._clean_json_response(response)
            intent_data = json.loads(clean_response)

            # Validate and provide defaults
            return self._validate_intent_analysis(intent_data)

        except Exception as e:
            logger.warning(f"Error analyzing intent: {e}. Using fallback.")
            return self._get_fallback_intent_analysis(user_query)

    def _clean_json_response(self, response: str) -> str:
        """Clean AI response to extract valid JSON."""
        # Remove markdown code blocks
        response = re.sub(r"```json\s*", "", response)
        response = re.sub(r"```\s*", "", response)

        # Find JSON object
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            return json_match.group(0)

        return response.strip()

    def _validate_intent_analysis(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and provide defaults for intent analysis."""
        defaults = {
            "intent_type": "search",
            "target_entities": [],
            "filters": {},
            "aggregations": [],
            "time_columns": ["created_at"],
            "grouping": [],
            "sorting": {"column": "created_at", "direction": "DESC"},
            "limit": 100,
            "keywords": [],
            "confidence": 0.5,
        }

        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in intent_data:
                intent_data[key] = default_value

        return intent_data

    def _get_fallback_intent_analysis(self, user_query: str) -> Dict[str, Any]:
        """Provide fallback intent analysis when AI fails."""
        # Simple keyword-based analysis
        keywords = user_query.lower().split()

        target_entities = []
        for table, aliases in self.TABLE_MAPPINGS.items():
            if any(alias in keywords for alias in aliases):
                target_entities.append(table)

        return {
            "intent_type": "search",
            "target_entities": target_entities or ["orders"],
            "filters": {"user_specific": True},
            "aggregations": [],
            "time_columns": ["created_at"],
            "grouping": [],
            "sorting": {"column": "created_at", "direction": "DESC"},
            "limit": 100,
            "keywords": keywords,
            "confidence": 0.3,
        }
