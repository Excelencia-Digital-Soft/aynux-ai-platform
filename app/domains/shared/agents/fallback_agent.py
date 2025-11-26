"""
Agente de fallback para consultas no reconocidas
"""

import logging
from typing import Any

from app.core.agents import BaseAgent
from app.integrations.llm import OllamaLLM
from app.core.utils.tracing import trace_async_method

logger = logging.getLogger(__name__)


class FallbackAgent(BaseAgent):
    """Agente para manejar consultas no reconocidas y guiar al usuario"""

    def __init__(self, ollama=None, postgres=None, config: dict[str, Any] | None = None):
        super().__init__("fallback_agent", config or {}, ollama=ollama, postgres=postgres)
        self.ollama = ollama or OllamaLLM()

    @trace_async_method(
        name="fallback_agent_process",
        run_type="chain",
        metadata={"agent_type": "fallback", "recovery_mode": "active"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Procesa mensajes no reconocidos y guia al usuario.

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

            error_response = """No entendi tu consulta, pero puedo ayudarte con:
- Ver productos y categorias
- Buscar equipos especificos
- Seguimiento de pedidos
- Ofertas y promociones
- Soporte tecnico

Con que te gustaria empezar?"""

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _generate_helpful_response(self, message: str) -> str:
        """Generate a helpful response for unrecognized queries."""
        prompt = f"""
El usuario escribio: "{message}"

Parece que su consulta no fue clara o no es reconocida.

Responde de forma amable y util:
- Sugiere 3 o 4 cosas comunes que podemos ayudar (ej: precios, soporte, pedidos).
- Se breve (maximo 4 lineas).
- Usa emojis para hacerlo mas calido.
- No repitas el mensaje del usuario.
"""

        try:
            # Use fast model for user-facing responses
            llm = self.ollama.get_llm(temperature=0.7, model="llama3.1")
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating fallback response: {str(e)}")
            return self._get_default_response()

    def _get_default_response(self) -> str:
        """Get default fallback response."""
        return """No entendi tu consulta, pero estoy aqui para ayudarte

Puedo asistirte con:
- Ver productos disponibles
- Consultar precios y ofertas
- Rastrear tu pedido
- Soporte tecnico

Que te gustaria hacer?"""
