"""
Agente especializado en saludos y presentacion de capacidades del sistema (Multi-Dominio)

Este agente genera saludos dinamicos basados en los agentes habilitados en el sistema,
con soporte multilenguaje (es, en, pt).
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
from app.prompts.loader import PromptLoader
from app.prompts.registry import PromptRegistry
from app.utils.language_detector import LanguageDetector

logger = logging.getLogger(__name__)


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
    """Agente especializado en saludos multi-dominio con prompts desde YAML"""

    def __init__(self, ollama=None, postgres=None, config: dict[str, Any] | None = None):
        super().__init__("greeting_agent", config or {}, ollama=ollama, postgres=postgres)
        self.ollama = ollama or OllamaLLM()

        # Configuracion especifica del agente
        self.model = "llama3.1"  # Modelo rapido para saludos
        self.temperature = 0.7  # Un poco de creatividad para respuestas amigables

        # Store enabled agents for dynamic service suggestions
        self.enabled_agents: list[str] = (config or {}).get("enabled_agents", [])
        logger.debug(f"GreetingAgent initialized with enabled_agents: {self.enabled_agents}")

        # Inicializar detector de idioma
        self.language_detector = LanguageDetector(
            config={"default_language": "es", "supported_languages": ["es", "en", "pt"]}
        )

        # Inicializar PromptLoader
        self.prompt_loader = PromptLoader()

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

            # Respuesta de fallback generica (sin mencionar dominio especifico)
            fallback_response = (
                "Hola! Bienvenido a Aynux. "
                "Soy tu asistente virtual y puedo ayudarte con tus consultas. "
                "En que te puedo ayudar hoy?"
            )

            return {
                "messages": [{"role": "assistant", "content": fallback_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
                "is_complete": True,
            }

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

        # Get dynamic services based on enabled agents and detected language
        # Cast to SupportedLanguage (default to "es" if not supported)
        lang: SupportedLanguage = detected_language if detected_language in ("es", "en", "pt") else "es"
        dynamic_services = get_service_names(self.enabled_agents, lang)

        logger.debug(f"Dynamic services for greeting: {dynamic_services}")

        # Cargar prompt desde YAML
        try:
            prompt_template = await self.prompt_loader.load(
                PromptRegistry.CONVERSATION_GREETING_SYSTEM, prefer_db=False
            )

            if not prompt_template:
                logger.warning("Could not load greeting prompt from YAML, using fallback")
                return self._get_fallback_greeting(lang)

            # Preparar variables para el prompt con servicios dinamicos
            prompt_variables = {
                "domain_type": business_domain,
                "primary_services": ", ".join(dynamic_services) if dynamic_services else "asistencia general",
                "language": detected_language,
                "domain_hint": domain_context["hint"],
                "domain_context": domain_context["context"],
            }

            # Renderizar el prompt con variables
            rendered_prompt = prompt_template.template.format(**prompt_variables)

            # Agregar el mensaje del usuario
            full_prompt = f"{rendered_prompt}\n\n## User Message\n{message}\n\nGenerate your greeting response now:"

            # Generar respuesta con LLM
            llm = self.ollama.get_llm(temperature=self.temperature, model=self.model)
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
            return self._get_fallback_greeting(lang)

    def _get_fallback_greeting(self, language: SupportedLanguage = "es") -> str:
        """
        Genera un greeting fallback generico basado en idioma y agentes habilitados.

        Args:
            language: Idioma detectado (es, en, pt)

        Returns:
            Greeting fallback apropiado con servicios dinamicos
        """
        # Generar lista de servicios dinamica basada en agentes habilitados
        service_list = format_service_list(self.enabled_agents, language)

        if language == "en":
            return (
                f"Hello! Welcome to Aynux.\n\n"
                f"I'm your virtual assistant. I can help you with:\n"
                f"{service_list}\n\n"
                f"How can I help you today?"
            )
        elif language == "pt":
            return (
                f"Ola! Bem-vindo ao Aynux.\n\n"
                f"Sou seu assistente virtual. Posso ajuda-lo com:\n"
                f"{service_list}\n\n"
                f"Como posso ajuda-lo hoje?"
            )
        else:  # Spanish (default)
            return (
                f"Hola! Bienvenido a Aynux.\n\n"
                f"Soy tu asistente virtual. Puedo ayudarte con:\n"
                f"{service_list}\n\n"
                f"En que te puedo ayudar hoy?"
            )
