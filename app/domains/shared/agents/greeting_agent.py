# ============================================================================
# SCOPE: GLOBAL
# Description: Agente de saludos multi-dominio. Singleton compartido pero puede
#              recibir configuración por tenant via apply_tenant_config().
# Tenant-Aware: Yes via BaseAgent - puede usar tenant's model/temperature/config.
# ============================================================================
"""
Agente especializado en saludos y presentacion de capacidades del sistema (Multi-Dominio)

Este agente genera saludos dinamicos basados en los agentes habilitados en el sistema,
con soporte multilenguaje (es, en, pt).
"""

import logging
from datetime import datetime
from typing import Any

from app.config.agent_capabilities import (
    SupportedLanguage,
    format_service_list,
    get_service_names,
)
from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.integrations.llm import VllmLLM
from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry
from app.utils.language_detector import LanguageDetector

logger = logging.getLogger(__name__)


def _get_time_of_day() -> str:
    """Get time of day for greeting personalization (morning/afternoon/evening)."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    else:
        return "evening"


# Mapeo de dominios a contextos (sin servicios hardcodeados)
# Los servicios ahora se obtienen dinamicamente de enabled_agents
DOMAIN_CONTEXTS = {
    "ecommerce": {
        "context": "consultas de tienda online",
        "hint": "e-commerce",
    },
    "hospital": {
        "context": "servicios medicos",
        "hint": "salud",
    },
    "credit": {
        "context": "servicios financieros",
        "hint": "finanzas",
    },
    "excelencia": {
        "context": "software empresarial",
        "hint": "ERP",
    },
}


class GreetingAgent(BaseAgent):
    """
    Agente especializado en saludos multi-dominio con prompts desde YAML.

    Supports dual-mode configuration:
    - Global mode: Uses default model/temperature from BaseAgent
    - Multi-tenant mode: model/temperature can be overridden via apply_tenant_config()
    """

    def __init__(self, llm=None, postgres=None, config: dict[str, Any] | None = None):
        super().__init__("greeting_agent", config or {}, llm=llm, postgres=postgres)
        self.llm = llm or VllmLLM()

        # Note: self.model and self.temperature are set by BaseAgent.__init__()
        # They can be overridden via apply_tenant_config() in multi-tenant mode

        # Store enabled agents for dynamic service suggestions
        self.enabled_agents: list[str] = (config or {}).get("enabled_agents", [])
        # Store enabled domains for filtering e-commerce services when domain is disabled
        self.enabled_domains: list[str] = (config or {}).get("enabled_domains", [])
        logger.debug(
            f"GreetingAgent initialized with enabled_agents: {self.enabled_agents}, "
            f"enabled_domains: {self.enabled_domains}"
        )

        # Inicializar detector de idioma
        self.language_detector = LanguageDetector(
            config={"default_language": "es", "supported_languages": ["es", "en", "pt"]}
        )

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

    @trace_async_method(
        name="greeting_agent_process",
        run_type="chain",
        metadata={"agent_type": "greeting", "model": "llama3.1"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Procesa saludos y proporciona informacion completa sobre las capacidades del sistema.

        Args:
            message: Mensaje del usuario (saludo)
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # Detectar idioma y generar respuesta personalizada (pasar state_dict)
            response_text = await self._generate_greeting_response(message, state_dict)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "is_complete": True,
                "greeting_completed": True,
            }

        except Exception as e:
            logger.error(f"Error in greeting agent: {str(e)}")

            # Respuesta de fallback generica usando YAML
            fallback_response = await self._get_generic_fallback()

            return {
                "messages": [{"role": "assistant", "content": fallback_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
                "is_complete": True,
            }

    async def _get_generic_fallback(self) -> str:
        """Get generic fallback response from YAML."""
        try:
            return await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_GREETING_FALLBACK_GENERIC,
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML generic fallback: {e}")
            return (
                "Hola! Bienvenido a Aynux. "
                "Soy tu asistente virtual y puedo ayudarte con tus consultas. "
                "En que te puedo ayudar hoy?"
            )

    async def _generate_greeting_response(self, message: str, state_dict: dict[str, Any]) -> str:
        """
        Genera respuesta de saludo personalizada usando prompts YAML y contexto de dominio.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual con informacion de dominio

        Returns:
            Respuesta de saludo adaptada al dominio
        """
        # Detectar idioma usando LanguageDetector
        try:
            detection_result = self.language_detector.detect_language(message)
            detected_language = detection_result["language"]
            confidence = detection_result["confidence"]

            logger.info(f"Language detected: {detected_language} (confidence: {confidence:.2f})")

        except Exception as e:
            logger.warning(f"Error detecting language: {e}, using default")
            detected_language = "es"
            confidence = 0.5

        # Obtener el dominio del estado (default: ecommerce)
        business_domain = state_dict.get("business_domain", "ecommerce")
        logger.info(f"Generating greeting for domain: {business_domain}")

        # Obtener contexto del dominio (sin servicios hardcodeados)
        domain_context = DOMAIN_CONTEXTS.get(business_domain, DOMAIN_CONTEXTS["ecommerce"])

        # Get dynamic services based on enabled agents, domains, and detected language
        # Cast to SupportedLanguage (default to "es" if not supported)
        lang: SupportedLanguage = detected_language if detected_language in ("es", "en", "pt") else "es"

        # Obtener dominios habilitados (prioridad: config > state_dict > vacío)
        enabled_domains = self.enabled_domains or state_dict.get("enabled_domains", [])

        # Pasar enabled_domains para filtrar servicios de dominios deshabilitados
        dynamic_services = get_service_names(self.enabled_agents, lang, enabled_domains)

        logger.debug(
            f"Dynamic services for greeting: {dynamic_services} "
            f"(enabled_domains: {enabled_domains})"
        )

        # Cargar prompt desde YAML usando PromptManager
        try:
            # Get user_name from customer_context if available
            customer_context = state_dict.get("customer_context", {})
            user_name = ""
            if isinstance(customer_context, dict):
                user_name = customer_context.get("name", "")
            elif hasattr(customer_context, "name"):
                user_name = customer_context.name or ""

            # Preparar variables para el prompt con servicios dinamicos
            prompt_variables = {
                "domain_type": business_domain,
                "primary_services": (
                    ", ".join(dynamic_services) if dynamic_services else "asistencia general"
                ),
                "language": detected_language,
                "domain_hint": domain_context["hint"],
                "domain_context": domain_context["context"],
                "message": message,
                # Add missing variables for template compatibility
                "user_name": user_name,
                "time_of_day": _get_time_of_day(),
                "context": domain_context["context"],
            }

            # Cargar y renderizar prompt via PromptManager
            rendered_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.CONVERSATION_GREETING_SYSTEM,
                variables=prompt_variables,
            )

            # Agregar el mensaje del usuario
            full_prompt = (
                f"{rendered_prompt}\n\n"
                f"## User Message\n{message}\n\n"
                "Generate your greeting response now:"
            )

            # Generar respuesta con LLM
            llm = self.llm.get_llm(complexity=ModelComplexity.SIMPLE, temperature=self.temperature)
            response = await llm.ainvoke(full_prompt)

            # Extraer el contenido de la respuesta
            if hasattr(response, "content"):
                content = response.content
                # Manejar content que puede ser string o lista
                if isinstance(content, str):
                    return content.strip()
                elif isinstance(content, list):
                    # Si es lista, unir todos los elementos como texto
                    return " ".join(str(item) for item in content).strip()
                else:
                    return str(content).strip()
            else:
                return str(response).strip()

        except Exception as e:
            logger.error(f"Error generating greeting with YAML prompt: {str(e)}")
            # Fallback generico con servicios dinamicos
            return await self._get_fallback_greeting(lang, enabled_domains)

    async def _get_fallback_greeting(
        self,
        language: SupportedLanguage = "es",
        enabled_domains: list[str] | None = None,
    ) -> str:
        """
        Genera un greeting fallback generico basado en idioma y agentes habilitados.

        Uses YAML prompts for multi-language support.

        Args:
            language: Idioma detectado (es, en, pt)
            enabled_domains: Lista de dominios habilitados para filtrar servicios

        Returns:
            Greeting fallback apropiado con servicios dinamicos
        """
        # Usar enabled_domains del parámetro o del config
        domains = enabled_domains or self.enabled_domains

        # Generar lista de servicios dinamica basada en agentes y dominios habilitados
        service_list = format_service_list(self.enabled_agents, language, domains)

        # Map language to registry key
        lang_key_map = {
            "es": PromptRegistry.AGENTS_GREETING_FALLBACK_ES,
            "en": PromptRegistry.AGENTS_GREETING_FALLBACK_EN,
            "pt": PromptRegistry.AGENTS_GREETING_FALLBACK_PT,
        }

        prompt_key = lang_key_map.get(language, PromptRegistry.AGENTS_GREETING_FALLBACK_ES)

        try:
            return await self.prompt_manager.get_prompt(
                prompt_key,
                variables={"service_list": service_list},
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML greeting fallback: {e}")
            # Hardcoded fallback as last resort
            return (
                f"Hola! Bienvenido a Aynux.\n\n"
                f"Soy tu asistente virtual. Puedo ayudarte con:\n"
                f"{service_list}\n\n"
                f"En que te puedo ayudar hoy?"
            )
