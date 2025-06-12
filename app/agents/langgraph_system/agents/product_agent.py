"""
Agente especializado en consultas de productos
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ProductAgent(BaseAgent):
    """Agente especializado en consultas específicas de productos y stock"""

    def __init__(self, ollama=None, postgres=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("product_agent", config or {}, ollama=ollama, postgres=postgres)

        # Configuración específica del agente
        self.max_products_shown = self.config.get("max_products_shown", 10)
        self.show_stock = self.config.get("show_stock", True)
        self.show_prices = self.config.get("show_prices", True)
        self.enable_recommendations = self.config.get("enable_recommendations", True)

        # Inicializar herramientas
        self.tools = []

    def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa consultas de productos.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # Extraer información de productos del mensaje
            query_info = self._extract_product_query(message)

            # Buscar productos
            products = self._search_products_sync(query_info)

            # Generar respuesta
            if not products:
                response_text = self._generate_no_results_response(query_info.get("query", message))
            else:
                response_text = self._generate_product_response(products)

            # Crear respuesta estructurada
            response = self._create_response(
                response_text=response_text,
                success=True,
                data_retrieved={"products": products, "query": query_info},
                tools_used=["product_search"],
            )

            # Retornar actualizaciones para el estado
            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "agent_responses": [response.to_dict()],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {"products": products},
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in product agent: {str(e)}")

            error_response = "Disculpa, tuve un problema consultando los productos. ¿Podrías reformular tu pregunta?"

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    def _extract_product_query(self, message: str) -> Dict[str, Any]:
        """Extrae información de consulta de productos del mensaje."""
        query_info = {"query": message, "product_name": None, "category": None, "price_range": None, "brand": None}

        # Patrones simples para extraer información
        message_lower = message.lower()

        # Buscar categorías comunes
        categories = ["teléfono", "celular", "smartphone", "laptop", "computadora", "tablet", "audífonos"]
        for category in categories:
            if category in message_lower:
                query_info["category"] = category
                break

        # Buscar marcas comunes
        brands = ["iphone", "samsung", "huawei", "xiaomi", "sony", "lg", "apple"]
        for brand in brands:
            if brand in message_lower:
                query_info["brand"] = brand
                break

        # Buscar rangos de precio
        price_pattern = r"\$?(\d{1,3}(?:,?\d{3})*)\s*(?:a|hasta|-)?\s*\$?(\d{1,3}(?:,?\d{3})*)?"
        price_match = re.search(price_pattern, message)
        if price_match:
            min_price = int(price_match.group(1).replace(",", ""))
            max_price = int(price_match.group(2).replace(",", "")) if price_match.group(2) else None
            query_info["price_range"] = {"min": min_price, "max": max_price}

        return query_info

    def _search_products_sync(self, query_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Búsqueda síncrona de productos (simulada)."""
        # Datos de productos simulados para demostración
        mock_products = [
            {
                "id": "1",
                "name": "iPhone 15 Pro",
                "category": "smartphone",
                "brand": "apple",
                "price": 999.99,
                "stock": 15,
                "available": True,
                "description": "El último iPhone con chip A17 Pro",
            },
            {
                "id": "2",
                "name": "Samsung Galaxy S24",
                "category": "smartphone",
                "brand": "samsung",
                "price": 849.99,
                "stock": 8,
                "available": True,
                "description": "Smartphone Android de alta gama",
            },
            {
                "id": "3",
                "name": "MacBook Air M3",
                "category": "laptop",
                "brand": "apple",
                "price": 1299.99,
                "stock": 5,
                "available": True,
                "description": "Laptop ultraligera con chip M3",
            },
        ]

        # Filtrar productos basado en la consulta
        filtered_products = []
        query_lower = query_info.get("query", "").lower()

        for product in mock_products:
            # Filtrar por categoría
            if query_info.get("category") and query_info["category"] not in product["category"]:
                continue

            # Filtrar por marca
            if query_info.get("brand") and query_info["brand"] not in product["brand"]:
                continue

            # Filtrar por rango de precio
            price_range = query_info.get("price_range")
            if price_range:
                product_price = product["price"]
                if price_range.get("min") and product_price < price_range["min"]:
                    continue
                if price_range.get("max") and product_price > price_range["max"]:
                    continue

            # Filtrar por nombre del producto
            if any(word in product["name"].lower() for word in query_lower.split()):
                filtered_products.append(product)

        return filtered_products[: self.max_products_shown]

    def _generate_no_results_response(self, query: str) -> str:
        """Genera respuesta cuando no se encuentran productos."""
        return f"""
No encontré productos que coincidan con "{query}". 

¿Te gustaría que:
• Busque en una categoría específica
• Te muestre productos similares  
• Te ayude con otra consulta

¿Qué prefieres?
        """.strip()

    def _generate_product_response(self, products: List[Dict[str, Any]]) -> str:
        """Genera respuesta con productos encontrados."""
        if len(products) == 1:
            return self._format_single_product(products[0])
        else:
            return self._format_multiple_products(products)

    def _format_single_product(self, product: Dict[str, Any]) -> str:
        """Formatea respuesta para un solo producto."""
        name = product.get("name", "Producto")
        price = product.get("price", 0)
        stock = product.get("stock", 0) if self.show_stock else None
        description = product.get("description", "")

        response = f"📱 **{name}**\n"

        if self.show_prices and price:
            response += f"💰 Precio: ${price:,.2f}\n"

        if stock is not None:
            if stock > 0:
                response += f"✅ En stock ({stock} disponibles)\n"
            else:
                response += "❌ Sin stock\n"

        if description:
            response += f"\n{description}\n"

        response += "\n¿Te interesa este producto? ¿Necesitas más información?"

        return response

    def _format_multiple_products(self, products: List[Dict[str, Any]]) -> str:
        """Formatea respuesta para múltiples productos."""
        response = f"Encontré {len(products)} productos que podrían interesarte:\n\n"

        for i, product in enumerate(products, 1):
            name = product.get("name", f"Producto {i}")
            price = product.get("price", 0)
            stock = product.get("stock", 0) if self.show_stock else None

            response += f"{i}. **{name}**"

            if self.show_prices and price:
                response += f" - ${price:,.2f}"

            if stock is not None:
                if stock > 0:
                    response += " ✅"
                else:
                    response += " ❌"

            response += "\n"

        response += "\n¿Te interesa alguno en particular? Puedo darte más detalles."

        return response
