"""
Agente especializado en navegación de categorías
"""

import logging
from typing import Any, Dict, List

from app.agents.langgraph_system.agents.base_agent import BaseAgent
from app.agents.langgraph_system.models import SharedState

logger = logging.getLogger(__name__)


class CategoryAgent(BaseAgent):
    """Agente especializado en navegación y browsing de categorías"""

    def __init__(self, vector_store, llm, db_connection=None):
        super().__init__("category_agent")
        self.vector_store = vector_store
        self.llm = llm
        self.db = db_connection

        # Inicializar herramientas
        self.tools = [
            CategorySearchTool(vector_store),
            CategoryHierarchyTool(db_connection),
            ProductCountTool(db_connection),
        ]

    async def _process_internal(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa consultas sobre categorías"""
        # Obtener mensaje del usuario
        user_message = self._get_last_user_message(state_dict)

        # Determinar qué está buscando el usuario
        search_intent = await self._analyze_category_intent(user_message)

        # Ejecutar búsqueda según el intent
        if search_intent == "browse_all":
            return await self._handle_browse_all(state_dict)
        elif search_intent == "specific_category":
            return await self._handle_specific_category(state_dict, user_message)
        else:
            return await self._handle_general_browsing(state_dict, user_message)

    def _get_last_user_message(self, state_dict: Dict[str, Any]) -> str:
        """Obtiene el último mensaje del usuario"""
        messages = state_dict.get("messages", [])
        for message in reversed(messages):
            if hasattr(message, "type") and message.type == "human":
                return message.content
        return ""

    async def _analyze_category_intent(self, message: str) -> str:
        """Analiza qué tipo de navegación quiere el usuario"""
        message_lower = message.lower()

        if any(word in message_lower for word in ["todas", "mostrar todo", "catálogo", "opciones"]):
            return "browse_all"
        elif any(word in message_lower for word in ["laptop", "computadora", "mouse", "teclado"]):
            return "specific_category"
        else:
            return "general"

    async def _handle_browse_all(self, state: SharedState) -> Dict[str, Any]:
        """Maneja solicitudes de ver todas las categorías"""
        # Obtener todas las categorías principales
        categories = await self.tools[1].get_main_categories()

        # Obtener conteo de productos por categoría
        category_counts = {}
        for cat in categories:
            count = await self.tools[2].count_products(cat["id"])
            category_counts[cat["id"]] = count

        # Generar respuesta
        response_text = "🛍️ **Categorías disponibles en nuestra tienda:**\n\n"

        for cat in categories:
            count = category_counts.get(cat["id"], 0)
            emoji = self._get_category_emoji(cat["name"])
            response_text += f"{emoji} **{cat['name']}** ({count} productos)\n"

            if cat.get("description"):
                response_text += f"   {cat['description']}\n"

            # Añadir subcategorías si existen
            if cat.get("subcategories"):
                for subcat in cat["subcategories"][:3]:  # Mostrar máx 3
                    response_text += f"   • {subcat['name']}\n"
                if len(cat["subcategories"]) > 3:
                    response_text += f"   • ... y {len(cat['subcategories']) - 3} más\n"

            response_text += "\n"

        response_text += "¿Qué categoría te gustaría explorar? 🔍"

        return {
            "text": response_text,
            "data": {"categories": categories, "product_counts": category_counts},
            "tools_used": ["CategoryHierarchyTool", "ProductCountTool"],
        }

    async def _handle_specific_category(self, state: SharedState, message: str) -> Dict[str, Any]:
        """Maneja búsqueda de categoría específica"""
        # Buscar categoría en vector store
        search_results = await self.tools[0].search_categories(message, limit=3)

        if not search_results:
            return await self._handle_no_results(message)

        # Tomar la mejor coincidencia
        best_match = search_results[0]
        category_data = best_match.metadata

        # Obtener productos destacados de esta categoría
        featured_products = await self._get_featured_products(category_data["id"])

        # Generar respuesta
        emoji = self._get_category_emoji(category_data["name"])
        response_text = f"{emoji} **{category_data['name']}**\n\n"

        if category_data.get("description"):
            response_text += f"{category_data['description']}\n\n"

        # Mostrar subcategorías si existen
        subcategories = await self.tools[1].get_subcategories(category_data["id"])
        if subcategories:
            response_text += "📂 **Subcategorías disponibles:**\n"
            for subcat in subcategories[:5]:
                response_text += f"• {subcat['name']}\n"
            response_text += "\n"

        # Mostrar productos destacados
        if featured_products:
            response_text += "⭐ **Productos destacados:**\n"
            for product in featured_products[:3]:
                response_text += f"• {product['name']} - ${product['price']:,.2f}\n"
            response_text += "\n"

        # Opciones de navegación
        response_text += "¿Te gustaría:\n"
        response_text += "1️⃣ Ver todos los productos de esta categoría\n"
        response_text += "2️⃣ Filtrar por subcategoría\n"
        response_text += "3️⃣ Ver ofertas especiales\n"

        return {
            "text": response_text,
            "data": {"category": category_data, "subcategories": subcategories, "featured_products": featured_products},
            "tools_used": ["CategorySearchTool", "CategoryHierarchyTool"],
        }

    async def _handle_general_browsing(self, state: SharedState, message: str) -> Dict[str, Any]:
        """Maneja navegación general basada en búsqueda semántica"""
        # Buscar categorías relacionadas
        related_categories = await self.tools[0].search_categories(message, limit=5)

        if not related_categories:
            return await self._handle_no_results(message)

        # Agrupar por relevancia
        response_text = "🔍 He encontrado estas categorías que podrían interesarte:\n\n"

        for idx, result in enumerate(related_categories, 1):
            cat = result.metadata
            score = result.score

            # Mostrar con nivel de relevancia
            if score > 0.8:
                relevance = "⭐⭐⭐"
            elif score > 0.6:
                relevance = "⭐⭐"
            else:
                relevance = "⭐"

            emoji = self._get_category_emoji(cat["name"])
            response_text += f"{idx}. {emoji} **{cat['name']}** {relevance}\n"

            if cat.get("description"):
                response_text += f"   {self._truncate_text(cat['description'], 60)}\n"

            response_text += "\n"

        response_text += "Selecciona el número de la categoría que deseas explorar 👆"

        return {
            "text": response_text,
            "data": {"search_results": related_categories},
            "tools_used": ["CategorySearchTool"],
        }

    async def _handle_no_results(self, query: str) -> Dict[str, Any]:
        """Maneja cuando no se encuentran resultados"""
        # Obtener categorías populares como alternativa
        popular_categories = await self.tools[1].get_popular_categories(limit=5)

        response_text = f"🤔 No encontré categorías específicas para '{query}'\n\n"
        response_text += "Pero te puedo mostrar nuestras categorías más populares:\n\n"

        for cat in popular_categories:
            emoji = self._get_category_emoji(cat["name"])
            response_text += f"{emoji} **{cat['name']}**\n"

        response_text += "\n¿Alguna de estas te interesa?"

        return {
            "text": response_text,
            "data": {"popular_categories": popular_categories},
            "tools_used": ["CategoryHierarchyTool"],
        }

    async def _get_featured_products(self, category_id: str) -> List[Dict]:
        """Obtiene productos destacados de una categoría"""
        # Simulación - en producción esto vendría de la BD
        return []

    def _get_category_emoji(self, category_name: str) -> str:
        """Retorna emoji apropiado para la categoría"""
        emoji_map = {
            "laptop": "💻",
            "computadora": "🖥️",
            "mouse": "🖱️",
            "teclado": "⌨️",
            "monitor": "🖥️",
            "impresora": "🖨️",
            "componente": "🔧",
            "gaming": "🎮",
            "oficina": "💼",
            "accesorio": "🎧",
            "almacenamiento": "💾",
            "red": "🌐",
        }

        name_lower = category_name.lower()
        for key, emoji in emoji_map.items():
            if key in name_lower:
                return emoji

        return "📦"  # Default


# Herramientas del CategoryAgent
class CategorySearchTool:
    """Busca categorías usando búsqueda semántica"""

    def __init__(self, vector_store):
        self.vector_store = vector_store

    async def search_categories(self, query: str, limit: int = 5) -> List[Any]:
        """Busca categorías relevantes"""
        try:
            results = await self.vector_store.asimilarity_search_with_score(query, k=limit, filter={"type": "category"})

            # Ordenar por score descendente
            results.sort(key=lambda x: x[1], reverse=True)

            # Convertir a formato estándar
            formatted_results = []
            for doc, score in results:
                formatted_results.append({"content": doc.page_content, "metadata": doc.metadata, "score": score})

            return formatted_results

        except Exception as e:
            logger.error(f"Error searching categories: {e}")
            return []


class CategoryHierarchyTool:
    """Maneja la jerarquía de categorías"""

    def __init__(self, db_connection):
        self.db = db_connection

    async def get_main_categories(self) -> List[Dict]:
        """Obtiene categorías principales"""
        # En producción esto vendría de la BD
        return [
            {
                "id": "cat_1",
                "name": "Laptops y Notebooks",
                "description": "Computadoras portátiles para trabajo y gaming",
                "subcategories": [
                    {"id": "sub_1", "name": "Gaming"},
                    {"id": "sub_2", "name": "Ultrabooks"},
                    {"id": "sub_3", "name": "Empresariales"},
                ],
            },
            {
                "id": "cat_2",
                "name": "Computadoras de Escritorio",
                "description": "PCs y workstations de alto rendimiento",
                "subcategories": [
                    {"id": "sub_4", "name": "Gaming"},
                    {"id": "sub_5", "name": "Oficina"},
                    {"id": "sub_6", "name": "Workstation"},
                ],
            },
            {
                "id": "cat_3",
                "name": "Componentes",
                "description": "Partes y piezas para armar o mejorar tu PC",
                "subcategories": [
                    {"id": "sub_7", "name": "Procesadores"},
                    {"id": "sub_8", "name": "Tarjetas Gráficas"},
                    {"id": "sub_9", "name": "Memorias RAM"},
                ],
            },
        ]

    async def get_subcategories(self, parent_id: str) -> List[Dict]:
        """Obtiene subcategorías de una categoría padre"""
        # En producción esto vendría de la BD
        return []

    async def get_popular_categories(self, limit: int = 5) -> List[Dict]:
        """Obtiene categorías más populares"""
        # En producción basado en ventas/visitas
        categories = await self.get_main_categories()
        return categories[:limit]


class ProductCountTool:
    """Cuenta productos por categoría"""

    def __init__(self, db_connection):
        self.db = db_connection

    async def count_products(self, category_id: str) -> int:
        """Cuenta productos en una categoría"""
        # En producción esto sería una query a la BD
        # Por ahora retornamos números simulados
        counts = {"cat_1": 45, "cat_2": 32, "cat_3": 78}
        return counts.get(category_id, 0)

