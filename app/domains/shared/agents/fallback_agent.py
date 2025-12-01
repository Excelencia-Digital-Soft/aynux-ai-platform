"""
Agente de fallback para consultas no reconocidas

Este agente genera respuestas dinamicas basadas en los agentes habilitados en el sistema,
con soporte multilenguaje (es, en, pt). Las sugerencias de servicios se adaptan
automaticamente segun los agentes activos.
"""

import logging
from typing import Any

from app.config.agent_capabilities import (
    SupportedLanguage,
    format_service_list,
    get_service_names,
)
from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.integrations.llm import OllamaLLM

logger = logging.getLogger(__name__)


class FallbackAgent(BaseAgent):
    """Agente para manejar consultas no reconocidas y guiar al usuario"""

    def __init__(self, ollama=None, postgres=None, config: dict[str, Any] | None = None):
        super().__init__("fallback_agent", config or {}, ollama=ollama, postgres=postgres)
        self.ollama = ollama or OllamaLLM()

        # Store enabled agents for dynamic service suggestions
        self.enabled_agents: list[str] = (config or {}).get("enabled_agents", [])
        logger.debug(f"FallbackAgent initialized with enabled_agents: {self.enabled_agents}")

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
        # Get detected language from state (default to Spanish)
        detected_language = state_dict.get("detected_language", "es")
        lang: SupportedLanguage = detected_language if detected_language in ("es", "en", "pt") else "es"

        try:
            # Generate helpful response with dynamic services
            response_text = await self._generate_helpful_response(message, lang)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in fallback agent: {str(e)}")

            # Dynamic error response based on enabled agents
            error_response = self._get_error_response(lang)

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _generate_helpful_response(
        self,
        message: str,
        language: SupportedLanguage = "es",
    ) -> str:
        """
        Generate a helpful response for unrecognized queries with dynamic services.

        Args:
            message: User message that wasn't recognized
            language: Target language for response

        Returns:
            Helpful response suggesting available services
        """
        # Get dynamic service names based on enabled agents
        service_names = get_service_names(self.enabled_agents, language)
        services_str = ", ".join(service_names) if service_names else "asistencia general"

        logger.debug(f"Generating fallback response with services: {services_str}")

        # Build dynamic LLM prompt based on language
        prompt = self._build_dynamic_prompt(message, services_str, language)

        try:
            # Use configured model for user-facing responses
            llm = self.ollama.get_llm(temperature=0.7)
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating fallback response: {str(e)}")
            return self._get_default_response(language)

    def _build_dynamic_prompt(
        self,
        message: str,
        services_str: str,
        language: SupportedLanguage,
    ) -> str:
        """
        Build LLM prompt with available services only.

        Args:
            message: User message
            services_str: Comma-separated list of available services
            language: Target language

        Returns:
            Prompt string for LLM
        """
        prompts = {
            "es": f'''El usuario escribio: "{message}"

Servicios disponibles: {services_str}

Responde de forma amable y util:
- Menciona SOLO los servicios disponibles listados arriba
- NO menciones servicios que no estan en la lista
- Sugiere 2-3 opciones de los servicios disponibles
- Se breve (maximo 4 lineas)
- Usa emojis para hacerlo mas calido
- No repitas el mensaje del usuario
''',
            "en": f'''The user wrote: "{message}"

Available services: {services_str}

Respond in a friendly and helpful way:
- Mention ONLY the available services listed above
- DO NOT mention services that are not in the list
- Suggest 2-3 options from the available services
- Be brief (maximum 4 lines)
- Use emojis to make it warmer
- Do not repeat the user's message
''',
            "pt": f'''O usuario escreveu: "{message}"

Servicos disponiveis: {services_str}

Responda de forma amigavel e util:
- Mencione APENAS os servicos disponiveis listados acima
- NAO mencione servicos que nao estao na lista
- Sugira 2-3 opcoes dos servicos disponiveis
- Seja breve (maximo 4 linhas)
- Use emojis para torna-lo mais acolhedor
- Nao repita a mensagem do usuario
''',
        }
        return prompts.get(language, prompts["es"])

    def _get_default_response(self, language: SupportedLanguage = "es") -> str:
        """
        Get default fallback response with dynamic services.

        Args:
            language: Target language

        Returns:
            Default response with available services
        """
        service_list = format_service_list(self.enabled_agents, language)

        templates = {
            "es": f"""No entendi tu consulta, pero estoy aqui para ayudarte

Puedo asistirte con:
{service_list}

Que te gustaria hacer?""",
            "en": f"""I didn't understand your query, but I'm here to help

I can assist you with:
{service_list}

What would you like to do?""",
            "pt": f"""Nao entendi sua consulta, mas estou aqui para ajudar

Posso ajuda-lo com:
{service_list}

O que voce gostaria de fazer?""",
        }
        return templates.get(language, templates["es"])

    def _get_error_response(self, language: SupportedLanguage = "es") -> str:
        """
        Get error response with dynamic services.

        Args:
            language: Target language

        Returns:
            Error response with available services
        """
        service_list = format_service_list(self.enabled_agents, language)

        templates = {
            "es": f"""No entendi tu consulta, pero puedo ayudarte con:
{service_list}

Con que te gustaria empezar?""",
            "en": f"""I didn't understand your query, but I can help you with:
{service_list}

What would you like to start with?""",
            "pt": f"""Nao entendi sua consulta, mas posso ajuda-lo com:
{service_list}

Com o que voce gostaria de comecar?""",
        }
        return templates.get(language, templates["es"])
