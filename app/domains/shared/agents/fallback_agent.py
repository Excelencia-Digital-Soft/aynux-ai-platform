# ============================================================================
# SCOPE: GLOBAL
# Description: Agente de fallback para consultas no reconocidas. Sugiere
#              servicios disponibles basándose en ENABLED_AGENTS del sistema.
# Tenant-Aware: Yes via BaseAgent - puede recibir config por tenant.
# ============================================================================
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
from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class FallbackAgent(BaseAgent):
    """
    Agente para manejar consultas no reconocidas y guiar al usuario.

    Supports dual-mode configuration:
    - Global mode: Uses default model/temperature from BaseAgent
    - Multi-tenant mode: model/temperature can be overridden via apply_tenant_config()
    """

    def __init__(self, ollama=None, postgres=None, config: dict[str, Any] | None = None):
        super().__init__("fallback_agent", config or {}, ollama=ollama, postgres=postgres)
        self.ollama = ollama or OllamaLLM()

        # Note: self.model and self.temperature are set by BaseAgent.__init__()
        # They can be overridden via apply_tenant_config() in multi-tenant mode

        # Store enabled agents for dynamic service suggestions
        self.enabled_agents: list[str] = (config or {}).get("enabled_agents", [])

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

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
            error_response = await self._get_error_response(lang)

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

        # Build dynamic LLM prompt based on language using YAML
        prompt = await self._build_dynamic_prompt(message, services_str, language)

        try:
            # Use configured model for user-facing responses
            llm = self.ollama.get_llm(complexity=ModelComplexity.SIMPLE, temperature=0.7)
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating fallback response: {str(e)}")
            return await self._get_default_response(language)

    async def _build_dynamic_prompt(
        self,
        message: str,
        services_str: str,
        language: SupportedLanguage,
    ) -> str:
        """
        Build LLM prompt with available services only using YAML.

        Args:
            message: User message
            services_str: Comma-separated list of available services
            language: Target language

        Returns:
            Prompt string for LLM
        """
        # Map language to registry key
        lang_key_map = {
            "es": PromptRegistry.AGENTS_FALLBACK_DYNAMIC_ES,
            "en": PromptRegistry.AGENTS_FALLBACK_DYNAMIC_EN,
            "pt": PromptRegistry.AGENTS_FALLBACK_DYNAMIC_PT,
        }

        prompt_key = lang_key_map.get(language, PromptRegistry.AGENTS_FALLBACK_DYNAMIC_ES)

        try:
            return await self.prompt_manager.get_prompt(
                prompt_key,
                variables={"message": message, "services_str": services_str},
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML prompt: {e}")
            # Fallback to simple prompt
            return (
                f'El usuario escribio: "{message}"\n\n'
                f"Servicios disponibles: {services_str}\n\n"
                "Responde de forma amable."
            )

    async def _get_default_response(self, language: SupportedLanguage = "es") -> str:
        """
        Get default fallback response with dynamic services using YAML.

        Args:
            language: Target language

        Returns:
            Default response with available services
        """
        service_list = format_service_list(self.enabled_agents, language)

        # Map language to registry key
        lang_key_map = {
            "es": PromptRegistry.AGENTS_FALLBACK_DEFAULT_ES,
            "en": PromptRegistry.AGENTS_FALLBACK_DEFAULT_EN,
            "pt": PromptRegistry.AGENTS_FALLBACK_DEFAULT_PT,
        }

        prompt_key = lang_key_map.get(language, PromptRegistry.AGENTS_FALLBACK_DEFAULT_ES)

        try:
            return await self.prompt_manager.get_prompt(
                prompt_key,
                variables={"service_list": service_list},
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML default response: {e}")
            return f"No entendi tu consulta, pero estoy aqui para ayudarte.\n\nPuedo asistirte con:\n{service_list}"

    async def _get_error_response(self, language: SupportedLanguage = "es") -> str:
        """
        Get error response with dynamic services using YAML.

        Args:
            language: Target language

        Returns:
            Error response with available services
        """
        service_list = format_service_list(self.enabled_agents, language)

        # Map language to registry key
        lang_key_map = {
            "es": PromptRegistry.AGENTS_FALLBACK_ERROR_ES,
            "en": PromptRegistry.AGENTS_FALLBACK_ERROR_EN,
            "pt": PromptRegistry.AGENTS_FALLBACK_ERROR_PT,
        }

        prompt_key = lang_key_map.get(language, PromptRegistry.AGENTS_FALLBACK_ERROR_ES)

        try:
            return await self.prompt_manager.get_prompt(
                prompt_key,
                variables={"service_list": service_list},
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML error response: {e}")
            return (
                f"No entendi tu consulta, pero puedo ayudarte con:\n{service_list}\n\n"
                "Con que te gustaria empezar?"
            )
