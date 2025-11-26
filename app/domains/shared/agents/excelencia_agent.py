"""
Excelencia Agent - Handles Excelencia ERP queries

Clean architecture agent that provides information about the Excelencia ERP system.
Uses centralized YAML-based prompt management with RAG support.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.interfaces.agent import AgentType, IAgent
from app.core.interfaces.llm import ILLM
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


# Module information for Excelencia ERP
EXCELENCIA_MODULES = {
    "historia_clinica": {
        "name": "Historia Cl\u00ednica Electr\u00f3nica",
        "emoji": "\U0001F3E5",
        "description": "Sistema completo de gesti\u00f3n de historias cl\u00ednicas digitales con cumplimiento normativo.",
        "features": [
            "Registro de pacientes",
            "Consultas m\u00e9dicas",
            "Prescripciones",
            "Estudios y resultados",
        ],
        "target": "Hospitales, Cl\u00ednicas, Centros m\u00e9dicos",
    },
    "turnos": {
        "name": "Sistema de Turnos M\u00e9dicos",
        "emoji": "\U0001F4C5",
        "description": "Gesti\u00f3n automatizada de agendas y turnos m\u00e9dicos.",
        "features": [
            "Agendas m\u00faltiples",
            "Turnos online",
            "Recordatorios autom\u00e1ticos",
            "Estad\u00edsticas",
        ],
        "target": "Consultorios, Cl\u00ednicas, Hospitales",
    },
    "hospitalaria": {
        "name": "Gesti\u00f3n Hospitalaria",
        "emoji": "\U0001F3E8",
        "description": "Administraci\u00f3n completa de hospitales y centros de salud.",
        "features": [
            "Internaciones",
            "Farmacia",
            "Facturaci\u00f3n",
            "Recursos humanos",
        ],
        "target": "Hospitales, Sanatorios, Cl\u00ednicas grandes",
    },
    "obras_sociales": {
        "name": "Obras Sociales",
        "emoji": "\U0001F4CB",
        "description": "Gesti\u00f3n de prestaciones y facturaci\u00f3n para obras sociales.",
        "features": [
            "Autorizaciones",
            "Facturaci\u00f3n",
            "Auditoria",
            "Convenios",
        ],
        "target": "Obras sociales, Prepagas",
    },
    "hoteleria": {
        "name": "Gesti\u00f3n Hotelera",
        "emoji": "\U0001F3E8",
        "description": "Software completo de gesti\u00f3n para hoteles y alojamientos.",
        "features": [
            "Reservas",
            "Check-in/out",
            "Facturaci\u00f3n",
            "Housekeeping",
        ],
        "target": "Hoteles, Apart hotels, Hostels",
    },
    "farmacia": {
        "name": "Sistema de Farmacia",
        "emoji": "\U0001F48A",
        "description": "Sistema especializado para gesti\u00f3n de farmacias.",
        "features": [
            "Stock",
            "Dispensaci\u00f3n",
            "Obras sociales",
            "Tr\u00f3quelado",
        ],
        "target": "Farmacias, Droguer\u00edas",
    },
}


class ExcelenciaAgent(IAgent):
    """
    Excelencia Agent following Clean Architecture.

    Single Responsibility: Handle Excelencia ERP queries
    Dependency Inversion: Depends on ILLM interface and PromptManager
    """

    def __init__(
        self,
        llm: ILLM,
        knowledge_service: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
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

        logger.info("ExcelenciaAgent initialized with prompt manager")

    @property
    def agent_type(self) -> AgentType:
        """Agent type identifier"""
        # Use SUPPORT as generic type since EXCELENCIA is not in enum
        return AgentType.SUPPORT

    @property
    def agent_name(self) -> str:
        """Agent name"""
        return "excelencia_agent"

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
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
            response = await self._generate_response(
                user_message, intent_data, rag_context
            )

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

    async def validate_input(self, state: Dict[str, Any]) -> bool:
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

    async def _analyze_intent(self, message: str) -> Dict[str, Any]:
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

            template = await self._prompt_manager.get_template(
                PromptRegistry.EXCELENCIA_QUERY_INTENT
            )
            temperature = (
                template.metadata.get("temperature", 0.3)
                if template and template.metadata
                else 0.3
            )
            max_tokens = (
                template.metadata.get("max_tokens", 300)
                if template and template.metadata
                else 300
            )

            response = await self._llm.generate(
                prompt, temperature=temperature, max_tokens=max_tokens
            )

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
            results = await self._knowledge_service.search(
                query=message, limit=3, threshold=0.7
            )

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
        intent_data: Dict[str, Any],
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

            # Build modules context
            modules_context = self._build_modules_context(
                intent_data.get("specific_modules", [])
            )

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

            template = await self._prompt_manager.get_template(
                PromptRegistry.EXCELENCIA_RESPONSE_GENERAL
            )
            temperature = (
                template.metadata.get("temperature", 0.7)
                if template and template.metadata
                else 0.7
            )
            max_tokens = (
                template.metadata.get("max_tokens", 500)
                if template and template.metadata
                else 500
            )

            response = await self._llm.generate(
                prompt, temperature=temperature, max_tokens=max_tokens
            )
            return response.strip()

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._get_default_response()

    async def _get_demo_response(self) -> str:
        """Get demo request response"""
        try:
            template = await self._prompt_manager.get_template(
                PromptRegistry.EXCELENCIA_DEMO_REQUEST
            )
            if template:
                return template.template
        except Exception:
            pass

        return """\u00a1Hola! \U0001F44B Con gusto te puedo mostrar una demo de Excelencia ERP.

Ofrecemos demostraciones personalizadas de nuestros sistemas:
- Historia Cl\u00ednica Electr\u00f3nica
- Gesti\u00f3n Hospitalaria
- Sistema de Turnos
- Gesti\u00f3n Hotelera

\u00bfSobre qu\u00e9 m\u00f3dulo te gustar\u00eda ver la demo?"""

    def _build_modules_context(self, modules: List[str]) -> str:
        """Build context string for mentioned modules"""
        if not modules:
            return ""

        context_parts = ["\nM\u00d3DULOS RELEVANTES:\n"]

        for module_key in modules:
            module_key_lower = module_key.lower().replace(" ", "_")
            module = EXCELENCIA_MODULES.get(module_key_lower)

            if module:
                context_parts.append(f"**{module['name']}** {module['emoji']}")
                context_parts.append(f"- {module['description']}")
                context_parts.append(f"- Caracter\u00edsticas: {', '.join(module['features'])}")
                context_parts.append(f"- Target: {module['target']}\n")

        return "\n".join(context_parts)

    def _get_default_response(self) -> str:
        """Get default response when LLM fails"""
        return """\u00a1Hola! Soy el asistente de Excelencia ERP. \U0001F60A

Excelencia es un sistema ERP modular especializado en:
\u2022 \U0001F3E5 Gesti\u00f3n Hospitalaria
\u2022 \U0001F4C5 Sistema de Turnos M\u00e9dicos
\u2022 \U0001F3E8 Gesti\u00f3n Hotelera
\u2022 \U0001F48A Sistema de Farmacia

\u00bfSobre qu\u00e9 m\u00f3dulo te gustar\u00eda saber m\u00e1s?"""

    def _error_response(self, error: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": "Disculpa, tuve un problema procesando tu consulta sobre Excelencia. \u00bfPodr\u00edas reformularla?",
                }
            ],
            "current_agent": self.agent_name,
            "error_count": state.get("error_count", 0) + 1,
            "error": error,
        }
