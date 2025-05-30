from typing import Any, Dict

from app.agents.base_agent import BaseAgent


class UnknownAgent(BaseAgent):
    """Agente para manejar mensajes no relacionados o confusos"""
    
    async def process(self, customer: Dict[str, Any], message_text: str, historial: str) -> str:
        """Procesa mensajes no claros y redirige la conversación con AI"""
        
        # Analizar si hay un contexto previo para continuar
        previous_context = self._analyze_previous_context(historial)
        
        # Intentar detectar posible intención mal expresada
        possible_intent = self._guess_possible_intent(message_text)
        
        # Construir contexto específico
        context_info = {
            "Contexto previo": previous_context,
            "Posible intención": possible_intent,
            "Mensaje confuso": message_text[:100],  # Limitar longitud
            "Cliente recurrente": customer['total_interactions'] > 1,
        }
        
        context = self._build_context(customer, context_info)
        
        # Prompt específico para mensajes confusos
        prompt = f"""
        Eres un asesor amable de Conversa Shop manejando un mensaje poco claro del cliente.
        
        CONTEXTO:
        {context}
        
        HISTORIAL:
        {historial}
        
        MENSAJE DEL CLIENTE (CONFUSO/NO RELACIONADO):
        {message_text}
        
        INSTRUCCIONES:
        1. Mantén un tono amable y profesional
        2. Si el mensaje parece un error de tipeo, no lo menciones directamente
        3. Si hay contexto previo, intenta continuar esa conversación
        4. Si no hay contexto, redirige amablemente hacia los productos/servicios
        5. Haz preguntas abiertas para entender qué necesita el cliente
        6. Ofrece opciones de temas principales (productos, precios, promociones)
        7. Evita que el cliente se sienta mal por el mensaje confuso
        8. Mantén el foco en ayudar y vender
        
        ESTRATEGIAS:
        - Si parece que escribió mal: Interpreta la intención más probable
        - Si es totalmente random: Redirige con "¡Hola! ¿En qué puedo ayudarte hoy?"
        - Si es una pregunta no relacionada: Responde brevemente y vuelve al negocio
        - Si es un saludo mal escrito: Responde con un saludo normal
        
        OPCIONES PARA OFRECER:
        - 💻 Ver nuestros productos de tecnología
        - 💰 Conocer promociones actuales  
        - 📦 Consultar disponibilidad
        - 🎯 Recibir recomendaciones personalizadas
        - ❓ Resolver dudas específicas
        
        Genera una respuesta que reconvierta la conversación hacia una venta potencial.
        """
        
        response = await self.ai_service._generate_content(prompt=prompt, temperature=0.7)
        return response
    
    def _analyze_previous_context(self, historial: str) -> str:
        """Analiza el contexto previo de la conversación"""
        if not historial or len(historial) < 50:
            return "Sin contexto previo significativo"
        
        # Buscar temas mencionados anteriormente
        topics = []
        
        keywords_topics = {
            "productos": ["laptop", "computadora", "gaming", "componente"],
            "precios": ["precio", "costo", "cuánto", "vale"],
            "compra": ["comprar", "quiero", "necesito", "interesa"],
        }
        
        historial_lower = historial.lower()
        for topic, keywords in keywords_topics.items():
            if any(keyword in historial_lower for keyword in keywords):
                topics.append(topic)
        
        if topics:
            return f"El cliente estaba consultando sobre: {', '.join(topics)}"
        else:
            return "Conversación general sin tema específico"
    
    def _guess_possible_intent(self, message_text: str) -> str:
        """Intenta adivinar una posible intención del mensaje confuso"""
        message_lower = message_text.lower().strip()
        
        # Verificar si es muy corto
        if len(message_lower) < 3:
            return "Mensaje muy corto, posible error de envío"
        
        # Verificar si tiene números (posible consulta de precio)
        import re
        if re.search(r'\d+', message_lower):
            return "Posible consulta sobre precios o cantidades"
        
        # Verificar caracteres repetidos (posible error de tipeo)
        if any(char * 3 in message_lower for char in message_lower):
            return "Posible error de tipeo o teclado"
        
        # Verificar palabras comunes mal escritas
        common_typos = {
            "hol": "saludo",
            "preci": "consulta de precio",
            "compr": "intención de compra",
            "info": "solicitud de información",
        }
        
        for typo, intent in common_typos.items():
            if typo in message_lower:
                return f"Posible {intent}"
        
        # Verificar si son solo símbolos o caracteres especiales
        if not any(c.isalnum() for c in message_lower):
            return "Solo símbolos, probable mensaje accidental"
        
        return "Intención no identificable"