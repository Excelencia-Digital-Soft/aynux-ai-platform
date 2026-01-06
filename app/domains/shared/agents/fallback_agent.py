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
from app.config.settings import get_settings
from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.domains.excelencia.application.services.support_response import (
    KnowledgeBaseSearch,
    RagQueryLogger,
    SearchMetrics,
)
from app.integrations.llm import VllmLLM
from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

settings = get_settings()

logger = logging.getLogger(__name__)


class FallbackAgent(BaseAgent):
    """
    Agente para manejar consultas no reconocidas y guiar al usuario.

    Supports dual-mode configuration:
    - Global mode: Uses default model/temperature from BaseAgent
    - Multi-tenant mode: model/temperature can be overridden via apply_tenant_config()
    """

    def __init__(self, llm=None, postgres=None, config: dict[str, Any] | None = None):
        super().__init__("fallback_agent", config or {}, llm=llm, postgres=postgres)
        self.llm = llm or VllmLLM()

        # Note: self.model and self.temperature are set by BaseAgent.__init__()
        # They can be overridden via apply_tenant_config() in multi-tenant mode

        # Store enabled agents for dynamic service suggestions
        self.enabled_agents: list[str] = (config or {}).get("enabled_agents", [])

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

        # Initialize KnowledgeBaseSearch for RAG integration
        # Searches all knowledge sources: agent_knowledge, company_knowledge, software_modules
        self._knowledge_enabled = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)
        self._knowledge_search = KnowledgeBaseSearch(agent_key="fallback_agent", max_results=3)
        self._rag_logger = RagQueryLogger(agent_key="fallback_agent")
        self._last_search_metrics: SearchMetrics | None = None

        logger.debug(f"FallbackAgent initialized with enabled_agents: {self.enabled_agents}, RAG enabled: {self._knowledge_enabled}")

    @trace_async_method(
        name="fallback_agent_process",
        run_type="chain",
        metadata={"agent_type": "fallback", "recovery_mode": "active"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Procesa mensajes no reconocidos y guia al usuario.

        Now includes RAG search to provide context-aware responses.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        # Get detected language from state (default to Spanish)
        detected_language = state_dict.get("detected_language", "es")
        lang: SupportedLanguage = detected_language if detected_language in ("es", "en", "pt") else "es"

        # RAG metrics for visualization
        rag_metrics: dict[str, Any] = {
            "used": False,
            "query": message[:100],
            "agent": self.name,
            "results_count": 0,
            "sources": [],
        }

        try:
            # Search knowledge base for relevant context (RAG)
            rag_context = ""
            self._last_search_metrics = None
            if self._knowledge_enabled:
                try:
                    search_result = await self._knowledge_search.search(message, "general")
                    rag_context = search_result.context
                    self._last_search_metrics = search_result.metrics
                    if rag_context:
                        rag_metrics["used"] = True
                        rag_metrics["results_count"] = search_result.metrics.result_count
                        logger.info(f"FallbackAgent RAG found context ({rag_metrics['results_count']} sources)")
                except Exception as rag_err:
                    logger.warning(f"RAG search failed, continuing without context: {rag_err}")

            # Generate helpful response with dynamic services and RAG context
            response_text = await self._generate_helpful_response(message, lang, rag_context)

            # Log RAG query with response (fire-and-forget)
            if self._last_search_metrics and self._last_search_metrics.result_count > 0:
                self._rag_logger.log_async(
                    query=message,
                    metrics=self._last_search_metrics,
                    response=response_text,
                )

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "is_complete": True,
                "rag_metrics": rag_metrics,
            }

        except Exception as e:
            logger.error(f"Error in fallback agent: {str(e)}")

            # Dynamic error response based on enabled agents
            error_response = await self._get_error_response(lang)

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
                "rag_metrics": rag_metrics,
            }

    async def _generate_helpful_response(
        self,
        message: str,
        language: SupportedLanguage = "es",
        rag_context: str = "",
    ) -> str:
        """
        Generate a helpful response for unrecognized queries with dynamic services.

        Now supports RAG context for more informed responses.

        Args:
            message: User message that wasn't recognized
            language: Target language for response
            rag_context: Optional RAG context from knowledge base search

        Returns:
            Helpful response suggesting available services
        """
        # Get dynamic service names based on enabled agents
        service_names = get_service_names(self.enabled_agents, language)
        services_str = ", ".join(service_names) if service_names else "asistencia general"

        logger.debug(f"Generating fallback response with services: {services_str}, RAG: {bool(rag_context)}")

        # Build dynamic LLM prompt based on language using YAML
        prompt = await self._build_dynamic_prompt(message, services_str, language, rag_context)

        try:
            # Use configured model for user-facing responses
            llm = self.llm.get_llm(complexity=ModelComplexity.SIMPLE, temperature=0.7)
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
        rag_context: str = "",
    ) -> str:
        """
        Build LLM prompt with available services and RAG context.

        Args:
            message: User message
            services_str: Comma-separated list of available services
            language: Target language
            rag_context: Optional RAG context from knowledge base

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
            base_prompt = await self.prompt_manager.get_prompt(
                prompt_key,
                variables={"message": message, "services_str": services_str},
            )

            # Append RAG context if available
            if rag_context:
                rag_instruction = (
                    "\n\n## INFORMACION RELEVANTE (usa esto para responder):\n"
                    if language == "es"
                    else "\n\n## RELEVANT INFORMATION (use this to answer):\n"
                )
                base_prompt = f"{base_prompt}{rag_instruction}{rag_context}"

            return base_prompt
        except Exception as e:
            logger.warning(f"Failed to load YAML prompt: {e}")
            # Fallback to simple prompt with RAG context
            rag_section = f"\n\nInformacion relevante:\n{rag_context}" if rag_context else ""
            return (
                f'El usuario escribio: "{message}"\n\n'
                f"Servicios disponibles: {services_str}"
                f"{rag_section}\n\n"
                "Responde de forma amable usando la informacion disponible."
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
