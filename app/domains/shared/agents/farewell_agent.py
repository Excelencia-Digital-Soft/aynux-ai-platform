"""
Agente de despedida para cerrar conversaciones
"""

import logging
from datetime import datetime
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.integrations.llm import OllamaLLM
from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class FarewellAgent(BaseAgent):
    """Agente especializado en despedidas y cierre de conversaciones"""

    def __init__(self, ollama=None, postgres=None, config: dict[str, Any] | None = None):
        super().__init__("farewell_agent", config or {}, ollama=ollama, postgres=postgres)
        self.ollama = ollama or OllamaLLM()

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

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

            # Default farewell using YAML
            default_response = await self._get_default_farewell()

            return {
                "messages": [{"role": "assistant", "content": default_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
                "is_complete": True,
            }

    async def _generate_farewell_response(self, message: str, has_interacted: bool) -> str:
        """Generate a contextual farewell response using YAML prompts."""
        context = (
            "El usuario ha interactuado con varios servicios."
            if has_interacted
            else "Es una conversacion breve."
        )

        try:
            # Load prompt from YAML
            prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_FAREWELL_CONTEXTUAL,
                variables={"message": message, "context": context},
            )

            # Use configured model for user-facing responses
            llm = self.ollama.get_llm(complexity=ModelComplexity.SIMPLE, temperature=0.8)
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating farewell: {str(e)}")
            return await self._get_default_farewell(has_interacted)

    async def _get_default_farewell(self, has_interacted: bool = False) -> str:
        """Get default farewell based on interaction level using YAML."""
        hour = datetime.now().hour

        # Time-based greeting
        if hour < 12:
            time_greeting = "Que tengas un excelente dia!"
        elif hour < 19:
            time_greeting = "Que tengas una linda tarde!"
        else:
            time_greeting = "Que tengas una excelente noche!"

        # Select prompt key based on interaction level
        prompt_key = (
            PromptRegistry.AGENTS_FAREWELL_DEFAULT_INTERACTED
            if has_interacted
            else PromptRegistry.AGENTS_FAREWELL_DEFAULT_BRIEF
        )

        try:
            return await self.prompt_manager.get_prompt(
                prompt_key,
                variables={"time_greeting": time_greeting},
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML farewell: {e}")
            # Hardcoded fallback as last resort
            if has_interacted:
                return (
                    f"Gracias por confiar en nosotros!\n"
                    f"{time_greeting}\n"
                    "Estamos aqui cuando nos necesites. Hasta pronto!"
                )
            else:
                return (
                    f"Hasta luego!\n"
                    f"{time_greeting}\n"
                    "No dudes en contactarnos si necesitas algo."
                )
