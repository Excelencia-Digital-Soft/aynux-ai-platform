from typing import Any, Dict

from app.agents.base_agent import BaseAgent


class PromotionsAgent(BaseAgent):
    """Agente para manejar consultas sobre promociones y descuentos"""
    
    async def process(self, customer: Dict[str, Any], message_text: str, historial: str) -> str:
        """Procesa consultas sobre promociones y genera respuesta con AI"""
        
        # Obtener todas las promociones activas
        promotions = await self.product_service.get_active_promotions()
        
        # Buscar productos en promoción
        products_on_sale = await self._get_products_on_promotion()
        
        # Construir contexto específico
        context_info = {
            "Promociones activas": self._format_promotions(promotions),
            "Productos en oferta": self._format_products_on_sale(products_on_sale),
            "Cliente es VIP": customer.get('vip', False),
            "Historial de compras": customer.get('total_inquiries', 0),
        }
        
        context = self._build_context(customer, context_info)
        
        # Prompt específico para promociones
        prompt = f"""
        Eres un asesor de ventas entusiasta de Conversa Shop presentando las mejores ofertas.
        
        CONTEXTO:
        {context}
        
        HISTORIAL:
        {historial}
        
        MENSAJE DEL CLIENTE:
        {message_text}
        
        INSTRUCCIONES:
        1. Presenta las promociones de manera atractiva y emocionante
        2. Destaca los descuentos más relevantes según el perfil del cliente
        3. Crea sentido de urgencia mencionando vigencia o stock limitado
        4. Calcula y menciona el ahorro específico en productos clave
        5. Si el cliente es VIP o recurrente, menciona beneficios especiales
        6. Sugiere combos o paquetes que maximicen el ahorro
        7. Usa emojis llamativos (🔥, 💰, 🎯, ⚡, 🏷️)
        8. Incluye un llamado a la acción claro para aprovechar las ofertas
        
        TÉCNICAS DE VENTA:
        - Resalta el valor del ahorro ("¡Ahorra hasta $X!")
        - Menciona "Oferta por tiempo limitado" cuando aplique
        - Usa comparaciones ("Antes $X, ahora solo $Y")
        - Sugiere "la mejor oportunidad del mes"
        
        Genera una respuesta persuasiva que motive al cliente a aprovechar las promociones.
        """
        
        response = await self.ai_service._generate_content(prompt=prompt, temperature=0.8)
        return response
    
    async def _get_products_on_promotion(self):
        """Obtiene productos que están en promoción"""
        # Por ahora, obtener productos destacados como proxy de productos en promoción
        # En el futuro, esto debería filtrar por productos con promociones activas
        featured_products = await self.product_service.get_featured_products(limit=6)
        
        # También buscar productos por rango de precio (ofertas)
        budget_products = await self.product_service.get_products_by_price_range(
            min_price=0, max_price=50000, limit=3
        )
        
        return featured_products + budget_products
    
    def _format_promotions(self, promotions: list) -> str:
        """Formatea las promociones activas"""
        if not promotions:
            return "Sin promociones activas en este momento"
        
        formatted = []
        for promo in promotions:
            promo_str = f"🔥 {promo.name}"
            
            if promo.discount_percentage:
                promo_str += f" - {promo.discount_percentage}% OFF"
            elif promo.discount_amount:
                promo_str += f" - ${promo.discount_amount:,.0f} de descuento"
            
            if hasattr(promo, 'valid_until') and promo.valid_until:
                promo_str += f" (válido hasta {promo.valid_until.strftime('%d/%m')})"
            
            if hasattr(promo, 'description') and promo.description:
                promo_str += f" | {promo.description}"
            
            formatted.append(promo_str)
        
        return "\n".join(formatted)
    
    def _format_products_on_sale(self, products: list) -> str:
        """Formatea productos en oferta"""
        if not products:
            return "Consultando productos en oferta..."
        
        formatted = []
        for product in products[:6]:
            # Simular precio anterior (20% más alto) para mostrar descuento
            original_price = product.price * 1.2
            savings = original_price - product.price
            
            prod_str = f"- {product.name}: "
            prod_str += f"Antes ${original_price:,.0f}, ahora ${product.price:,.0f} "
            prod_str += f"(¡Ahorras ${savings:,.0f}!)"
            
            if product.stock < 5:
                prod_str += " ⚠️ Últimas unidades"
            
            formatted.append(prod_str)
        
        return "\n".join(formatted)