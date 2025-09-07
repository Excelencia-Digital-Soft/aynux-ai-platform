"""
Agente especializado en navegación de categorías
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..integrations.ollama_integration import OllamaIntegration
from ..tools.category_tool import CategoryTool
from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CategoryAgent(BaseAgent):
    """Agente especializado en navegación y browsing de categorías"""

    def __init__(self, ollama=None, chroma=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("category_agent", config or {}, ollama=ollama, chroma=chroma)

        # Configuración específica del agente
        self.max_categories_shown = config.get("max_categories_shown", 8)
        self.use_vector_search = config.get("use_vector_search", True)

        # Initialize tools
        self.category_tool = CategoryTool()
        self.ollama = ollama or OllamaIntegration()

    @trace_async_method(
        name="category_agent_process",
        run_type="agent",
        metadata={"agent_type": "category", "use_vector_search": "enabled"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa consultas de categorías usando AI y base de datos."""
        try:
            # First, analyze the user intent using AI
            intent_analysis = await self._analyze_user_intent(message)

            # Query database based on intent
            categories_data = await self._get_categories_from_db(intent_analysis)

            if not categories_data["success"]:
                raise Exception(f"Error fetching categories: {categories_data.get('error', 'Unknown error')}")

            categories = categories_data.get("categories", [])

            # Generate AI-powered response
            response_text = await self._generate_ai_response(categories, message, intent_analysis)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {"categories": categories, "intent": intent_analysis},
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in category agent: {str(e)}")

            error_response = "Disculpa, tuve un problema al buscar las categorías. ¿Podrías intentar de nuevo?"

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _analyze_user_intent(self, message: str) -> Dict[str, Any]:
        prompt = f"""
Analiza el siguiente mensaje del usuario y determina su intención:

"{message}"

Opciones de intención:
- "browse_all": si el usuario quiere ver todas las categorías o explorar sin algo específico.
- "search_specific": si menciona una categoría concreta (ej: celulares, televisores, notebooks).

Devuelve un JSON con esta estructura:
{{
  "intent": "browse_all" | "search_specific",
  "category_mentioned": "nombre_de_categoria" | null
}}

Responde solo con el JSON, sin texto adicional.
"""

        try:
            llm = self.ollama.get_llm(temperature=0.3)
            response = await llm.ainvoke(prompt)
            # Try to parse as JSON, fallback to basic intent if fails
            try:
                return json.loads(response.content)
            except Exception:
                return {"intent": "browse_all", "category_mentioned": None, "search_terms": [], "needs_details": False}
        except Exception as e:
            logger.error(f"Error analyzing intent: {str(e)}")
            return {"intent": "browse_all", "category_mentioned": None, "search_terms": [], "needs_details": False}

    async def _get_categories_from_db(self, intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch categories from database based on intent."""
        intent = intent_analysis.get("intent", "browse_all")
        category_mentioned = intent_analysis.get("category_mentioned")
        search_terms = intent_analysis.get("search_terms", [])

        if intent == "search_specific" and category_mentioned:
            # Search for specific category
            result = await self.category_tool("get_by_name", category_name=category_mentioned)
            if result["success"] and result.get("category"):
                return {"success": True, "categories": [result["category"]]}

        if search_terms:
            # Search with terms
            all_results = []
            for term in search_terms[:3]:  # Limit search terms
                result = await self.category_tool("search", search_term=term)
                if result["success"]:
                    all_results.extend(result.get("categories", []))

            # Remove duplicates
            seen = set()
            unique_categories = []
            for cat in all_results:
                if cat["id"] not in seen:
                    seen.add(cat["id"])
                    unique_categories.append(cat)

            if unique_categories:
                return {"success": True, "categories": unique_categories}

        # Default: get all categories with products
        return await self.category_tool("with_products")

    async def _generate_ai_response(
        self, categories: List[Dict[str, Any]], message: str, intent_analysis: Dict[str, Any]
    ) -> str:
        """Generate AI-powered response based on categories and user intent."""
        if not categories:
            return (
                "Lo siento, no encontré categorías que coincidan con tu búsqueda."
                "¿Te gustaría ver todas nuestras categorías disponibles?"
            )

        # Prepare category information for AI
        category_info = []
        for cat in categories[: self.max_categories_shown]:
            info = f"- {cat['name']}: {cat['description']}"
            if cat["product_count"] > 0:
                info += f" ({cat['product_count']} productos"
                if cat["min_price"] and cat["max_price"]:
                    info += f", ${cat['min_price']:.2f} - ${cat['max_price']:.2f}"
                info += ")"
            category_info.append(info)

        prompt = f"""Usuario: "{message}"

Categorías:
{chr(10).join(category_info[:5])}

Responde breve, menciona 3-4 categorías principales. Usa emojis. Máximo 3 líneas."""

        try:
            llm = self.ollama.get_llm(temperature=0.7)
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}, {intent_analysis}")
            # Fallback to formatted response
            return self._generate_fallback_response(categories)

    def _generate_fallback_response(self, categories: List[Dict[str, Any]]) -> str:
        """Generate fallback response without AI."""
        if not categories:
            return "No encontré categorías disponibles en este momento."

        response = "🏪 **Categorías Disponibles:**\n\n"

        for i, category in enumerate(categories[: self.max_categories_shown], 1):
            name = category["name"]
            description = category["description"]
            count = category["product_count"]

            response += f"{i}. **{name}**"
            if count > 0:
                response += f" ({count} productos"
                if category.get("min_price") and category.get("max_price"):
                    response += f", ${category['min_price']:.2f} - ${category['max_price']:.2f}"
                response += ")"
            response += f"\n   {description}\n\n"

        response += "¿Te interesa alguna categoría en particular? Puedo mostrarte productos específicos."

        return response
