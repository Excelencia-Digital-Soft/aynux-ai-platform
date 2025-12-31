"""
Excelencia Agent - Handles Excelencia Software queries

Clean architecture agent that provides information about the Excelencia Software system.
Uses centralized YAML-based prompt management with RAG support.

Modules are loaded dynamically from PostgreSQL (erp_modules table) instead of hardcoded.
"""

import json
import logging
from typing import Any

from app.core.interfaces.agent import AgentType, IAgent
from app.core.interfaces.llm import ILLM
from app.database.async_db import get_async_db_context
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


# Fallback modules when database is unavailable
_FALLBACK_MODULES: dict[str, dict[str, Any]] = {
    "ZM-001": {
        "name": "ZisMed - Sistema Médico Integral",
        "emoji": "🏥",
        "description": "Suite médica completa que incluye Historia Clínica Electrónica y Turnos Médicos",
        "features": ["Historia Clínica", "Turnos Médicos", "Registro Pacientes", "Prescripciones"],
        "target": "Clínicas, Hospitales, Centros de Salud",
    },
    "HC-001": {
        "name": "Historia Clínica Electrónica",
        "emoji": "🏥",
        "description": "Sistema de gestión de historias clínicas digitales",
        "features": ["Registro de pacientes", "Consultas médicas", "Prescripciones"],
        "target": "Hospitales, Clínicas",
    },
    "TM-001": {
        "name": "Sistema de Turnos Médicos",
        "emoji": "📅",
        "description": "Gestión de agendas y turnos de pacientes",
        "features": ["Agenda médica", "Turnos online", "Recordatorios"],
        "target": "Consultorios, Clínicas",
    },
    "HO-001": {
        "name": "Gestión Hotelera",
        "emoji": "🏨",
        "description": "Software para administración de hoteles",
        "features": ["Reservas", "Check-in/out", "Facturación"],
        "target": "Hoteles, Apart hotels",
    },
}


class ExcelenciaAgent(IAgent):
    """
    Excelencia Agent following Clean Architecture.

    Single Responsibility: Handle Excelencia Software queries
    Dependency Inversion: Depends on ILLM interface and PromptManager
    """

    def __init__(
        self,
        llm: ILLM,
        knowledge_service: Any | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize agent with dependencies.

        Args:
            llm: Language model for response generation
            knowledge_service: Optional knowledge base service for RAG
            config: Optional configuration
        """
        self._config = config or {}
        self._llm = llm
        self._knowledge_service = knowledge_service
        self._prompt_manager = PromptManager()

        # Module cache (loaded on first use from DB)
        self._modules_cache: dict[str, dict[str, Any]] | None = None

        logger.info("ExcelenciaAgent initialized with prompt manager")

    async def _get_modules(self) -> dict[str, dict[str, Any]]:
        """
        Get ERP modules from database with caching.

        Returns:
            Dict of module_code -> module_info
        """
        if self._modules_cache is not None:
            return self._modules_cache

        try:
            from app.core.container import DependencyContainer

            async with get_async_db_context() as db:
                container = DependencyContainer()
                use_case = container.create_get_modules_use_case(db)
                result = await use_case.execute(only_available=True)

                # Build dict with emoji support
                self._modules_cache = {}
                for module in result.modules:
                    self._modules_cache[module.code] = {
                        "name": module.name,
                        "emoji": "📦",  # Default emoji
                        "description": module.description,
                        "features": module.features,
                        "target": module.category.value,
                    }

                logger.info(f"Loaded {len(self._modules_cache)} ERP modules from database")
                return self._modules_cache

        except Exception as e:
            logger.warning(f"Failed to load modules from DB: {e}, using fallback")
            self._modules_cache = _FALLBACK_MODULES.copy()
            return self._modules_cache

    @property
    def agent_type(self) -> AgentType:
        """Agent type identifier"""
        # Use SUPPORT as generic type since EXCELENCIA is not in enum
        return AgentType.SUPPORT

    @property
    def agent_name(self) -> str:
        """Agent name"""
        return "excelencia_agent"

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Execute Excelencia agent logic.

        Args:
            state: Current conversation state

        Returns:
            Updated state with response
        """
        try:
            messages = state.get("messages", [])
            if not messages:
                return self._error_response("No message provided", state)

            user_message = messages[-1].get("content", "")

            # Analyze intent
            intent_data = await self._analyze_intent(user_message)
            logger.info(f"Detected Excelencia intent: {intent_data}")

            # Get RAG context if available
            rag_context = await self._get_rag_context(user_message)

            # Generate response based on intent
            response = await self._generate_response(user_message, intent_data, rag_context)

            return {
                "messages": [{"role": "assistant", "content": response}],
                "current_agent": self.agent_name,
                "agent_history": state.get("agent_history", []) + [self.agent_name],
                "retrieved_data": {
                    "query_type": intent_data.get("query_type", "general"),
                    "modules_mentioned": intent_data.get("specific_modules", []),
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in ExcelenciaAgent.execute: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def validate_input(self, state: dict[str, Any]) -> bool:
        """
        Validate input state.

        Args:
            state: State to validate

        Returns:
            True if valid
        """
        messages = state.get("messages", [])
        if not messages:
            return False
        return bool(messages[-1].get("content"))

    async def _analyze_intent(self, message: str) -> dict[str, Any]:
        """
        Analyze user intent using LLM with centralized prompts.

        Args:
            message: User message

        Returns:
            Intent analysis result
        """
        try:
            prompt = await self._prompt_manager.get_prompt(
                PromptRegistry.EXCELENCIA_QUERY_INTENT,
                variables={"message": message},
            )

            template = await self._prompt_manager.get_template(PromptRegistry.EXCELENCIA_QUERY_INTENT)
            temperature = template.metadata.get("temperature", 0.3) if template and template.metadata else 0.3
            max_tokens = template.metadata.get("max_tokens", 300) if template and template.metadata else 300

            response = await self._llm.generate(prompt, temperature=temperature, max_tokens=max_tokens)

            # Parse JSON response
            try:
                return json.loads(response.strip())
            except json.JSONDecodeError:
                return {
                    "query_type": "general",
                    "user_intent": message,
                    "specific_modules": [],
                    "requires_demo": False,
                    "urgency": "medium",
                }

        except Exception as e:
            logger.warning(f"Error analyzing intent: {e}")
            return {
                "query_type": "general",
                "user_intent": message,
                "specific_modules": [],
                "requires_demo": False,
                "urgency": "medium",
            }

    async def _get_rag_context(self, message: str) -> str:
        """
        Get relevant context from knowledge base.

        Args:
            message: User message

        Returns:
            RAG context string
        """
        if not self._knowledge_service:
            return ""

        try:
            results = await self._knowledge_service.search(query=message, limit=3, threshold=0.7)

            if not results:
                return ""

            context_parts = ["\n## INFORMACI\u00d3N CORPORATIVA RELEVANTE (Knowledge Base):"]
            for i, result in enumerate(results, 1):
                context_parts.append(f"### {i}. {result.get('title', 'Sin t\u00edtulo')}")
                context_parts.append(result.get("content", ""))

            return "\n".join(context_parts)

        except Exception as e:
            logger.warning(f"Error getting RAG context: {e}")
            return ""

    async def _generate_response(
        self,
        user_message: str,
        intent_data: dict[str, Any],
        rag_context: str,
    ) -> str:
        """
        Generate response using LLM with centralized prompts.

        Args:
            user_message: User's message
            intent_data: Analyzed intent
            rag_context: Context from knowledge base

        Returns:
            Generated response
        """
        try:
            # Check if demo request
            if intent_data.get("requires_demo"):
                return await self._get_demo_response()

            # Build modules context from DB
            modules_context = await self._build_modules_context(intent_data.get("specific_modules", []))

            prompt = await self._prompt_manager.get_prompt(
                PromptRegistry.EXCELENCIA_RESPONSE_GENERAL,
                variables={
                    "user_message": user_message,
                    "query_type": intent_data.get("query_type", "general"),
                    "user_intent": intent_data.get("user_intent", user_message),
                    "requires_demo": str(intent_data.get("requires_demo", False)),
                    "modules_context": modules_context,
                    "rag_context": rag_context,
                },
            )

            template = await self._prompt_manager.get_template(PromptRegistry.EXCELENCIA_RESPONSE_GENERAL)
            temperature = template.metadata.get("temperature", 0.7) if template and template.metadata else 0.7
            max_tokens = template.metadata.get("max_tokens", 500) if template and template.metadata else 500

            response = await self._llm.generate(prompt, temperature=temperature, max_tokens=max_tokens)
            return response.strip()

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return await self._get_default_response()

    async def _get_demo_response(self) -> str:
        """Get demo request response"""
        try:
            template = await self._prompt_manager.get_template(PromptRegistry.EXCELENCIA_DEMO_REQUEST)
            if template:
                return template.template
        except Exception:
            pass

        return """\u00a1Hola! \U0001f44b Con gusto te puedo mostrar una demo de Excelencia Software.

Ofrecemos demostraciones personalizadas de nuestros sistemas:
- Historia Cl\u00ednica Electr\u00f3nica
- Gesti\u00f3n Hospitalaria
- Sistema de Turnos
- Gesti\u00f3n Hotelera

\u00bfSobre qu\u00e9 m\u00f3dulo te gustar\u00eda ver la demo?"""

    async def _build_modules_context(self, modules: list[str]) -> str:
        """Build context string for mentioned modules from DB."""
        if not modules:
            return ""

        db_modules = await self._get_modules()
        context_parts = ["\nMÓDULOS RELEVANTES:\n"]

        for module_key in modules:
            # Try exact match first
            module = db_modules.get(module_key)

            # Try fuzzy match by name if not found
            if not module:
                module_key_lower = module_key.lower()
                for _, info in db_modules.items():
                    if module_key_lower in info["name"].lower():
                        module = info
                        break

            if module:
                emoji = module.get("emoji", "📦")
                context_parts.append(f"**{module['name']}** {emoji}")
                context_parts.append(f"- {module['description']}")
                features = module.get("features", [])
                if features:
                    context_parts.append(f"- Características: {', '.join(features)}")
                context_parts.append(f"- Target: {module.get('target', 'N/A')}\n")

        return "\n".join(context_parts)

    async def _get_default_response(self) -> str:
        """Get default response when LLM fails, using dynamic modules."""
        modules = await self._get_modules()

        if not modules:
            return "¡Hola! Soy el asistente de Excelencia Software. ¿En qué puedo ayudarte?"

        # Build dynamic module list
        module_lines = []
        for _, info in list(modules.items())[:4]:
            emoji = info.get("emoji", "📦")
            module_lines.append(f"• {emoji} {info['name']}")

        modules_text = "\n".join(module_lines)

        return f"""¡Hola! Soy el asistente de Excelencia Software. 😊

Excelencia es un sistema ERP modular especializado en:
{modules_text}

¿Sobre qué módulo te gustaría saber más?"""

    def _error_response(self, error: str, state: dict[str, Any]) -> dict[str, Any]:
        """Generate error response"""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": "Disculpa, tuve un problema procesando tu consulta sobre \
                            Excelencia. \u00bfPodr\u00edas reformularla?",
                }
            ],
            "current_agent": self.agent_name,
            "error_count": state.get("error_count", 0) + 1,
            "error": error,
        }
