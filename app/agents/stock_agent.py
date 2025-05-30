from typing import Any, Dict

from app.agents.base_agent import BaseAgent


class StockAgent(BaseAgent):
    """Agente para manejar consultas sobre disponibilidad de stock"""
    
    async def process(self, customer: Dict[str, Any], message_text: str, historial: str) -> str:
        """Procesa consultas sobre stock y genera respuesta con AI"""
        
        # Obtener reporte de stock general
        stock_report = await self.product_service.get_stock_report()
        
        # Buscar productos específicos mencionados
        specific_products = await self._search_mentioned_products(message_text)
        
        # Productos con stock bajo
        low_stock_products = await self.product_service.get_low_stock_products()
        
        # Construir contexto específico
        context_info = {
            "Reporte de stock": self._format_stock_report(stock_report),
            "Productos específicos consultados": self._format_products_stock(specific_products),
            "Productos con stock bajo": self._format_low_stock(low_stock_products),
        }
        
        context = self._build_context(customer, context_info)
        
        # Prompt específico para consultas de stock
        prompt = f"""
        Eres un asesor de ventas de Conversa Shop respondiendo sobre disponibilidad de productos.
        
        CONTEXTO:
        {context}
        
        HISTORIAL:
        {historial}
        
        MENSAJE DEL CLIENTE:
        {message_text}
        
        INSTRUCCIONES:
        1. Responde específicamente sobre la disponibilidad consultada
        2. Si pregunta por un producto específico, da información precisa de stock
        3. Si el stock es bajo, crea urgencia mencionando las pocas unidades disponibles
        4. Si no hay stock, ofrece alternativas similares disponibles
        5. Menciona opciones de reserva o pedido especial si aplica
        6. Incluye tiempos de reposición si es relevante
        7. Usa emojis para indicar disponibilidad (✅ disponible, ⚠️ pocas unidades, ❌ agotado)
        8. Invita a concretar la compra si hay stock disponible
        
        POLÍTICAS DE LA TIENDA:
        - Reservas con 20% de seña
        - Reposición en 24-48hs para productos agotados
        - Envío a todo el país
        
        Genera una respuesta clara sobre la disponibilidad y motiva la acción.
        """
        
        response = await self.ai_service._generate_content(prompt=prompt, temperature=0.6)
        return response
    
    async def _search_mentioned_products(self, message_text: str):
        """Busca productos específicos mencionados en el mensaje"""
        # Buscar términos de productos en el mensaje
        search_terms = []
        
        # Patrones comunes de consulta de stock
        patterns = [
            r"tienen\s+(.+?)\?",
            r"hay\s+(.+?)\?",
            r"stock\s+de\s+(.+)",
            r"disponible\s+(.+)",
            r"(.+?)\s+disponible",
        ]
        
        import re
        for pattern in patterns:
            matches = re.findall(pattern, message_text.lower())
            search_terms.extend(matches)
        
        # Si no se encontraron patrones, usar el mensaje completo
        if not search_terms:
            search_terms = [message_text]
        
        # Buscar productos para cada término
        all_products = []
        for term in search_terms[:2]:  # Limitar a 2 búsquedas
            products = await self.product_service.search_products(
                search_term=term.strip(), limit=3
            )
            all_products.extend(products)
        
        return all_products
    
    def _format_stock_report(self, stock_report: dict) -> str:
        """Formatea el reporte de stock general"""
        if not stock_report or "category_breakdown" not in stock_report:
            return "Sin información de stock general"
        
        formatted = []
        for category in stock_report["category_breakdown"]:
            total = category.get("total_stock", 0)
            status = "Buena disponibilidad" if total > 50 else "Stock limitado" if total > 0 else "Agotado"
            formatted.append(f"{category['category']}: {total} unidades ({status})")
        
        return "; ".join(formatted)
    
    def _format_products_stock(self, products: list) -> str:
        """Formatea información de stock de productos específicos"""
        if not products:
            return "No se encontraron productos específicos"
        
        formatted = []
        for product in products:
            stock_status = "✅ Disponible" if product.stock > 5 else "⚠️ Últimas unidades" if product.stock > 0 else "❌ Agotado"
            formatted.append(f"{product.name}: {product.stock} unidades ({stock_status})")
        
        return "; ".join(formatted)
    
    def _format_low_stock(self, products: list) -> str:
        """Formatea productos con stock bajo"""
        if not products:
            return "Sin productos con stock crítico"
        
        formatted = []
        for product in products[:3]:
            formatted.append(f"{product.name}: Solo {product.stock} unidades")
        
        return "; ".join(formatted)