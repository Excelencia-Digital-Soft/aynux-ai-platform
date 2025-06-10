from typing import Any, Dict

from app.agents.base_agent import BaseAgent


class DoubtsAgent(BaseAgent):
    """Agente para manejar dudas y objeciones del cliente"""

    async def process(self, customer: Dict[str, Any], message_text: str, historial: str) -> str:
        """Procesa dudas y objeciones generando respuestas persuasivas con AI"""

        # Identificar el tipo de duda/objeción
        doubt_type = self._identify_doubt_type(message_text)

        # Obtener información relevante según el tipo de duda
        relevant_info = await self._get_relevant_info_for_doubt(doubt_type, historial)

        # Construir contexto específico
        context_info = {
            "Tipo de duda": doubt_type,
            "Información relevante": relevant_info,
            "Cliente es recurrente": customer["total_interactions"] > 1,
            "Nivel de interés previo": self._assess_interest_level(historial),
        }

        context = self._build_context(customer, context_info)

        # Prompt específico para manejar dudas
        prompt = f"""
        Eres un asesor experto de Conversa Shop manejando dudas y objeciones del cliente.
        
        CONTEXTO:
        {context}
        
        HISTORIAL:
        {historial}
        
        MENSAJE DEL CLIENTE (DUDA/OBJECIÓN):
        {message_text}
        
        INSTRUCCIONES:
        1. Reconoce y valida la preocupación del cliente ("Entiendo tu inquietud...")
        2. Proporciona información clara y honesta que resuelva la duda
        3. Refuerza los beneficios y valor del producto/servicio
        4. Usa prueba social si es relevante ("Muchos clientes nos eligen por...")
        5. Ofrece garantías o políticas que generen confianza
        6. Si la objeción es sobre precio, enfócate en el valor y ROI
        7. Sugiere alternativas si la objeción es válida
        8. Cierra con una invitación positiva a continuar
        
        TÉCNICAS DE MANEJO DE OBJECIONES:
        - Para precio: Desglosar valor, comparar con competencia, mencionar financiación
        - Para calidad: Destacar garantías, certificaciones, testimonios
        - Para dudas técnicas: Explicar simple, ofrecer soporte post-venta
        - Para urgencia: Crear FOMO sutil, mencionar stock o promociones limitadas
        
        POLÍTICAS DE CONFIANZA:
        - Garantía oficial en todos los productos
        - Soporte técnico post-venta
        - Política de devolución
        - Envíos seguros a todo el país
        - Años de experiencia en el mercado
        
        Genera una respuesta que convierta la objeción en una oportunidad de venta.
        """

        response = await self.ai_service._generate_content(prompt=prompt, temperature=0.7)
        return response

    def _identify_doubt_type(self, message_text: str) -> str:
        """Identifica el tipo de duda u objeción"""
        message_lower = message_text.lower()

        # Patrones de tipos de dudas
        doubt_patterns = {
            "precio": ["caro", "precio", "costoso", "barato", "descuento", "financiación", "cuotas"],
            "calidad": ["calidad", "bueno", "malo", "durabilidad", "garantía", "original"],
            "comparación": ["mejor", "diferencia", "versus", "vs", "comparar", "otro"],
            "técnica": ["funciona", "compatible", "requisitos", "especificaciones", "sirve para"],
            "confianza": ["seguro", "confiable", "estafa", "garantía", "devolución"],
            "tiempo": ["demora", "envío", "cuándo", "tiempo", "llega"],
        }

        for doubt_type, keywords in doubt_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return doubt_type

        return "general"

    async def _get_relevant_info_for_doubt(self, doubt_type: str, historial: str) -> str:
        """Obtiene información relevante según el tipo de duda"""
        print("Historial", historial)
        info_parts = []

        if doubt_type == "precio":
            # Obtener info de financiación y promociones
            promotions = await self.product_service.get_active_promotions()
            if promotions:
                info_parts.append(f"Promociones activas: {len(promotions)}")
            info_parts.append("Financiación disponible en 3, 6 y 12 cuotas")

        elif doubt_type == "calidad":
            info_parts.append("Todos los productos con garantía oficial del fabricante")
            info_parts.append("Soporte técnico especializado post-venta")
            info_parts.append("Productos 100% originales con factura")

        elif doubt_type == "comparación":
            # Buscar productos mencionados en el historial para comparar
            info_parts.append("Asesoramiento personalizado para encontrar la mejor opción")
            info_parts.append("Comparativas técnicas detalladas disponibles")

        elif doubt_type == "tiempo":
            info_parts.append("Envíos en 24-48hs para CABA y GBA")
            info_parts.append("Envíos a todo el país en 3-5 días hábiles")
            info_parts.append("Tracking en tiempo real del pedido")

        elif doubt_type == "confianza":
            info_parts.append("Más de 10 años en el mercado")
            info_parts.append("Miles de clientes satisfechos")
            info_parts.append("Local físico para retiros y consultas")
            info_parts.append("Todas las formas de pago seguras")

        return "; ".join(info_parts)

    def _assess_interest_level(self, historial: str) -> str:
        """Evalúa el nivel de interés del cliente basado en el historial"""
        historial_lower = historial.lower()

        # Contar indicadores de interés
        high_interest_keywords = ["quiero", "necesito", "comprar", "precio", "cuánto"]
        medium_interest_keywords = ["información", "características", "diferencia"]

        high_count = sum(1 for keyword in high_interest_keywords if keyword in historial_lower)
        medium_count = sum(1 for keyword in medium_interest_keywords if keyword in historial_lower)

        if high_count >= 2:
            return "Alto - Cliente listo para comprar, solo necesita resolver dudas"
        elif high_count >= 1 or medium_count >= 2:
            return "Medio - Cliente interesado, evaluando opciones"
        else:
            return "Inicial - Cliente explorando, necesita más información"

