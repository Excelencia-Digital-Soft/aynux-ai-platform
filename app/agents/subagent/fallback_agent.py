"""
Agente de fallback para consultas no reconocidas
"""

import logging
from typing import Any, Dict, Optional

from ..integrations.ollama_integration import OllamaIntegration
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class FallbackAgent(BaseAgent):
    """Agente para manejar consultas no reconocidas y guiar al usuario"""

    def __init__(self, ollama=None, postgres=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("fallback_agent", config or {}, ollama=ollama, postgres=postgres)
        self.ollama = ollama or OllamaIntegration()

    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa mensajes no reconocidos y guía al usuario.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # Generate helpful response
            response_text = await self._generate_helpful_response(message)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in fallback agent: {str(e)}")

            error_response = """No entendí tu consulta, pero puedo ayudarte con:
• 🛍️ Ver productos y categorías
• 💻 Buscar equipos específicos
• 📦 Seguimiento de pedidos
• 🎯 Ofertas y promociones
• 💬 Soporte técnico

¿Con qué te gustaría empezar?"""

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _generate_helpful_response(self, message: str) -> str:
        """Generate a helpful response for unrecognized queries."""
        prompt = f"""
El usuario escribió: "{message}"

Parece que su consulta no fue clara o no es reconocida.

Responde de forma amable y útil:
• Sugiere 3 o 4 cosas comunes que podemos ayudar (ej: precios, soporte, pedidos).
• Sé breve (máximo 4 líneas).
• Usa emojis para hacerlo más cálido.
• No repitas el mensaje del usuario.
"""

        try:
            llm = self.ollama.get_llm(temperature=0.7)
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating fallback response: {str(e)}")
            return self._get_default_response()

    def _get_default_response(self) -> str:
        """Get default fallback response."""
        return """No entendí tu consulta, pero estoy aquí para ayudarte 😊

Puedo asistirte con:
• 🛒 Ver productos disponibles
• 💰 Consultar precios y ofertas
• 📦 Rastrear tu pedido
• 🔧 Soporte técnico

¿Qué te gustaría hacer?"""

