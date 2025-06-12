"""
Agente especializado en navegación de categorías
"""

import logging
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CategoryAgent(BaseAgent):
    """Agente especializado en navegación y browsing de categorías"""

    def __init__(self, ollama=None, chroma=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("category_agent", config or {}, ollama=ollama, chroma=chroma)

        # Configuración específica del agente
        self.max_categories_shown = config.get("max_categories_shown", 8)
        self.use_vector_search = config.get("use_vector_search", True)

    def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa consultas de categorías."""
        try:
            # Obtener categorías disponibles
            categories = self._get_available_categories()

            # Generar respuesta
            response_text = self._generate_category_response(categories, message)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {"categories": categories},
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in category agent: {str(e)}")

            error_response = "Disculpa, tuve un problema mostrando las categorías. ¿Podrías intentar de nuevo?"

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    def _get_available_categories(self) -> List[Dict[str, Any]]:
        """Obtiene las categorías disponibles (simuladas)."""
        return [
            {
                "id": "smartphones",
                "name": "Smartphones",
                "description": "Teléfonos inteligentes de todas las marcas",
                "product_count": 45,
            },
            {
                "id": "laptops",
                "name": "Laptops",
                "description": "Computadoras portátiles para trabajo y gaming",
                "product_count": 23,
            },
            {
                "id": "tablets",
                "name": "Tablets",
                "description": "Tabletas para entretenimiento y productividad",
                "product_count": 18,
            },
            {
                "id": "audio",
                "name": "Audio",
                "description": "Audífonos, parlantes y equipos de sonido",
                "product_count": 32,
            },
            {
                "id": "accessories",
                "name": "Accesorios",
                "description": "Fundas, cargadores y más accesorios",
                "product_count": 67,
            },
        ]

    def _generate_category_response(self, categories: List[Dict[str, Any]], message: str) -> str:
        """Genera respuesta con categorías disponibles."""
        response = "🏪 **Nuestras Categorías Principales:**\n\n"

        for i, category in enumerate(categories, 1):
            name = category["name"]
            description = category["description"]
            count = category["product_count"]

            response += f"{i}. **{name}** ({count} productos)\n"
            response += f"   {description}\n\n"

        response += "¿Te interesa alguna categoría en particular? Puedo mostrarte productos específicos."

        return response
