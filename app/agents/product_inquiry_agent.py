from typing import Any, Dict, Optional

from app.agents.base_agent import BaseAgent


class ProductInquiryAgent(BaseAgent):
    """Agente para manejar consultas sobre productos específicos"""

    async def process(self, customer: Dict[str, Any], message_text: str, historial: str) -> str:
        """Procesa consultas sobre productos y genera respuesta con AI"""

        message_lower = message_text.lower()

        # Detectar tipo de producto consultado
        product_type = self._detect_product_type(message_lower)

        # Buscar productos relevantes
        products = await self._search_relevant_products(message_lower, product_type)

        # Construir contexto específico
        context_info = {
            "Tipo de producto consultado": product_type or "general",
            "Productos relevantes": self._format_products(products),
            "Presupuesto del cliente": customer.get("budget_range", "No especificado"),
        }

        context = self._build_context(customer, context_info)

        # Prompt específico para consultas de productos
        prompt = f"""
        Eres un asesor experto en productos tecnológicos de Conversa Shop.
        
        CONTEXTO:
        {context}
        
        HISTORIAL:
        {historial}
        
        MENSAJE DEL CLIENTE:
        {message_text}
        
        INSTRUCCIONES:
        1. Responde específicamente sobre los productos consultados
        2. Proporciona información clara sobre características, beneficios y precios
        3. Si hay varios productos, compáralos brevemente
        4. Destaca las ventajas competitivas
        5. Si el producto no está disponible, sugiere alternativas similares
        6. Incluye información sobre stock y garantías
        7. Invita a una acción (preguntar más detalles, ver en persona, comprar)
        8. Usa formato con **negritas** para destacar información importante
        9. Usa emojis relevantes (💻, 🖥️, ⌨️, etc.)
        
        IMPORTANTE: Basa tu respuesta ÚNICAMENTE en los productos del contexto. No inventes productos.
        
        Genera una respuesta informativa y persuasiva sobre los productos.
        """

        response = await self.ai_service._generate_content(prompt=prompt, temperature=0.6)
        return response

    def _detect_product_type(self, message_lower: str) -> Optional[str]:
        """Detecta el tipo de producto mencionado"""
        product_patterns = {
            "laptop": ["laptop", "notebook", "portátil", "portatil"],
            "desktop": ["pc", "desktop", "escritorio", "computadora de mesa"],
            "gaming": ["gaming", "gamer", "juegos", "videojuegos"],
            "componentes": ["procesador", "cpu", "gpu", "ram", "memoria", "disco", "ssd"],
            "perifericos": ["mouse", "teclado", "monitor", "auriculares", "headset"],
        }

        for product_type, keywords in product_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return product_type

        return None

    async def _search_relevant_products(self, message_lower: str, product_type: str):
        """Busca productos relevantes según el tipo detectado"""

        # Mapear tipo de producto a categoría
        category_map = {
            "laptop": "laptops",
            "desktop": "desktops",
            "gaming": None,  # Gaming puede ser laptop o desktop
            "componentes": "components",
            "perifericos": "peripherals",
        }

        category = category_map.get(product_type)

        if product_type == "gaming":
            # Para gaming, buscar en ambas categorías
            gaming_laptops = await self.product_service.get_products_by_category("laptops", "gaming", limit=3)
            gaming_desktops = await self.product_service.get_products_by_category("desktops", "gaming", limit=3)
            return gaming_laptops + gaming_desktops
        elif category:
            return await self.product_service.get_products_by_category(category, limit=5)
        else:
            # Búsqueda general por término
            return await self.product_service.search_products(search_term=message_lower, limit=5)

    def _format_products(self, products: list) -> str:
        """Formatea los productos para el contexto"""
        if not products:
            return "No se encontraron productos específicos"

        formatted = []
        for product in products[:5]:
            prod_str = f"- {product.name}: ${product.price:,.0f}"
            prod_str += f" | Specs: {product.specs[:100]}..."
            prod_str += f" | Stock: {product.stock} unidades"
            if product.brand:
                prod_str += f" | Marca: {product.brand.display_name}"
            formatted.append(prod_str)

        return "\n".join(formatted)

