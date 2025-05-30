from typing import Any, Dict

from app.agents.base_agent import BaseAgent


class GreetingAgent(BaseAgent):
    """Agente para manejar saludos y necesidades iniciales"""
    
    async def process(self, customer: Dict[str, Any], message_text: str, historial: str) -> str:
        """Procesa saludos y genera respuesta de bienvenida con AI"""
        
        # Obtener información relevante de la tienda
        categories = await self.product_service.get_categories_with_counts()
        promotions = await self.product_service.get_active_promotions()
        
        # Construir contexto específico
        context_info = {
            "Categorías disponibles": self._format_categories(categories),
            "Promociones activas": self._format_promotions(promotions),
            "Es cliente recurrente": customer['total_interactions'] > 1,
        }
        
        context = self._build_context(customer, context_info)
        
        # Prompt específico para saludos
        prompt = f"""
        Eres un asesor de ventas amigable de Conversa Shop, una tienda de tecnología.
        
        CONTEXTO:
        {context}
        
        HISTORIAL:
        {historial}
        
        MENSAJE DEL CLIENTE:
        {message_text}
        
        INSTRUCCIONES:
        1. Saluda cordialmente al cliente (si es recurrente, hazlo notar sutilmente)
        2. Menciona brevemente las categorías principales disponibles
        3. Si hay promociones activas, menciónalas de forma atractiva
        4. Haz una pregunta abierta para entender qué busca el cliente
        5. Usa emojis moderadamente para hacer la conversación más amigable
        6. Mantén un tono profesional pero cercano
        
        Genera una respuesta de bienvenida personalizada y efectiva.
        """
        
        response = await self.ai_service._generate_content(prompt=prompt, temperature=0.7)
        return response
    
    def _format_categories(self, categories: list) -> str:
        """Formatea las categorías para el contexto"""
        if not categories:
            return "Sin categorías disponibles"
        
        formatted = []
        for cat in categories[:4]:  # Top 4 categorías
            formatted.append(
                f"{cat['display_name']} ({cat['product_count']} productos, "
                f"desde ${cat['min_price']:,.0f})"
            )
        return "; ".join(formatted)
    
    def _format_promotions(self, promotions: list) -> str:
        """Formatea las promociones para el contexto"""
        if not promotions:
            return "Sin promociones activas"
        
        formatted = []
        for promo in promotions[:3]:  # Top 3 promociones
            discount = promo.discount_percentage or promo.discount_amount or 0
            formatted.append(f"{promo.name} - {discount}% OFF")
        return "; ".join(formatted)