"""
Agente de despedida para cerrar conversaciones
"""

import logging
from datetime import datetime
from typing import Any

from app.core.agents import BaseAgent
from app.integrations.llm import OllamaLLM
from app.core.utils.tracing import trace_async_method

logger = logging.getLogger(__name__)


class FarewellAgent(BaseAgent):
    """Agente especializado en despedidas y cierre de conversaciones"""

    def __init__(self, ollama=None, postgres=None, config: dict[str, Any] | None = None):
        super().__init__("farewell_agent", config or {}, ollama=ollama, postgres=postgres)
        self.ollama = ollama or OllamaLLM()

    @trace_async_method(
        name="farewell_agent_process",
        run_type="chain",
        metadata={"agent_type": "farewell", "conversation_end": True},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Procesa despedidas y agradecimientos finales.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # Get conversation context
            agent_history = state_dict.get("agent_history", [])
            has_interacted = len(agent_history) > 1

            # Generate contextual farewell
            response_text = await self._generate_farewell_response(message, has_interacted)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "is_complete": True,
                "requires_human": False,
            }

        except Exception as e:
            logger.error(f"Error in farewell agent: {str(e)}")

            # Default farewell
            default_response = self._get_default_farewell()

            return {
                "messages": [{"role": "assistant", "content": default_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
                "is_complete": True,
            }

    async def _generate_farewell_response(self, message: str, has_interacted: bool) -> str:
        """Generate a contextual farewell response."""
        context = "El usuario ha interactuado con varios servicios." if has_interacted else "Es una conversacion breve."

        prompt = f"""
El usuario escribio: "{message}"

{context}

Tu tarea es generar una despedida cordial, profesional y empatica.
Si ayudamos, agradece su confianza. Invita a volver en el futuro.

- Usa maximo 3 lineas.
- Usa 1 o 2 emojis relevantes (no mas).
- No repitas el mensaje del usuario.
"""

        try:
            # Use fast model for user-facing responses
            llm = self.ollama.get_llm(temperature=0.8, model="llama3.1")
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating farewell: {str(e)}")
            return self._get_default_farewell(has_interacted)

    def _get_default_farewell(self, has_interacted: bool = False) -> str:
        """Get default farewell based on interaction level."""
        hour = datetime.now().hour

        # Time-based greeting
        if hour < 12:
            time_greeting = "Que tengas un excelente dia!"
        elif hour < 19:
            time_greeting = "Que tengas una linda tarde!"
        else:
            time_greeting = "Que tengas una excelente noche!"

        if has_interacted:
            return f"""Gracias por confiar en nosotros!
{time_greeting}
Estamos aqui cuando nos necesites. Hasta pronto!"""
        else:
            return f"""Hasta luego!
{time_greeting}
No dudes en contactarnos si necesitas algo."""
