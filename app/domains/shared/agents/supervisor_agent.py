"""
Supervisor Agent - Enhances agent responses

Clean architecture agent that transforms agent responses into warm,
professional customer service messages.
Uses centralized YAML-based prompt management.
"""

import logging
from typing import Any, Dict, Optional

from app.core.interfaces.agent import AgentType, IAgent, ISupervisorAgent
from app.core.interfaces.llm import ILLM
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class SupervisorAgent(IAgent, ISupervisorAgent):
    """
    Supervisor Agent following Clean Architecture.

    Single Responsibility: Enhance agent responses with better formatting
    Dependency Inversion: Depends on ILLM interface and PromptManager
    """

    def __init__(
        self,
        llm: ILLM,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize agent with dependencies.

        Args:
            llm: Language model for response enhancement
            config: Optional configuration
        """
        self._config = config or {}
        self._llm = llm
        self._prompt_manager = PromptManager()

        # Language instruction map
        self._language_instructions = {
            "es": "IMPORTANT: You MUST answer ONLY in SPANISH language.",
            "en": "IMPORTANT: You MUST answer ONLY in ENGLISH language.",
            "pt": "IMPORTANT: You MUST answer ONLY in PORTUGUESE language.",
        }

        logger.info("SupervisorAgent initialized with prompt manager")

    @property
    def agent_type(self) -> AgentType:
        """Agent type identifier"""
        return AgentType.SUPERVISOR

    @property
    def agent_name(self) -> str:
        """Agent name"""
        return "supervisor_agent"

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute supervisor agent logic.

        Args:
            state: Current conversation state

        Returns:
            Updated state with enhanced response
        """
        try:
            messages = state.get("messages", [])
            if not messages:
                return state

            # Get the last agent's response to enhance
            original_response = messages[-1].get("content", "") if messages else ""

            # Get user's original message
            user_messages = [m for m in messages if m.get("role") == "user"]
            user_message = user_messages[-1].get("content", "") if user_messages else ""

            # Skip enhancement if no response or already enhanced
            if not original_response or state.get("response_enhanced"):
                return state

            # Enhance the response
            enhanced_response = await self._enhance_response(
                user_message=user_message,
                original_response=original_response,
                state=state,
            )

            # Update the last message with enhanced response
            updated_messages = messages.copy()
            if updated_messages:
                updated_messages[-1]["content"] = enhanced_response

            return {
                **state,
                "messages": updated_messages,
                "response_enhanced": True,
                "supervisor_applied": True,
            }

        except Exception as e:
            logger.error(f"Error in SupervisorAgent.execute: {e}", exc_info=True)
            return state  # Return original state on error

    async def validate_input(self, state: Dict[str, Any]) -> bool:
        """
        Validate input state.

        Args:
            state: State to validate

        Returns:
            True if valid
        """
        messages = state.get("messages", [])
        return len(messages) > 0

    async def route(self, state: Dict[str, Any]) -> str:
        """
        Determine the next agent to execute.

        Args:
            state: Current state

        Returns:
            Name of next agent
        """
        # Supervisor routes based on intent in state
        intent = state.get("intent", {})
        intent_type = intent.get("type", "unknown")

        routing_map = {
            "product": "product_agent",
            "order": "tracking_agent",
            "promotion": "promotions_agent",
            "support": "support_agent",
            "greeting": "greeting_agent",
            "farewell": "farewell_agent",
            "excelencia": "excelencia_agent",
        }

        return routing_map.get(intent_type, "fallback_agent")

    async def analyze_intent(self, message: str) -> Dict[str, Any]:
        """
        Analyze message intent.

        Args:
            message: User message

        Returns:
            Intent analysis result
        """
        # Basic intent analysis - can be enhanced
        message_lower = message.lower()

        intent_keywords = {
            "product": ["producto", "precio", "busco", "tiene", "venden", "cuesta"],
            "order": ["pedido", "orden", "env\u00edo", "rastrear", "seguimiento"],
            "promotion": ["oferta", "descuento", "promoci\u00f3n", "rebaja"],
            "support": ["ayuda", "soporte", "problema", "error", "funciona"],
            "greeting": ["hola", "buenos d\u00edas", "buenas tardes", "buenas noches"],
            "farewell": ["chau", "adi\u00f3s", "hasta luego", "gracias", "bye"],
            "excelencia": ["excelencia", "erp", "sistema", "m\u00f3dulo"],
        }

        for intent_type, keywords in intent_keywords.items():
            if any(kw in message_lower for kw in keywords):
                return {"type": intent_type, "confidence": 0.8}

        return {"type": "unknown", "confidence": 0.3}

    async def _enhance_response(
        self,
        user_message: str,
        original_response: str,
        state: Dict[str, Any],
    ) -> str:
        """
        Enhance agent response using LLM with centralized prompts.

        Args:
            user_message: User's message
            original_response: Agent's original response
            state: Current state

        Returns:
            Enhanced response
        """
        try:
            # Build optional sections
            customer_name = state.get("customer_name")
            customer_name_section = (
                f"- Customer name: {customer_name}" if customer_name else ""
            )

            conversation_summary = state.get("conversation_summary", "")

            # Get language instruction
            language = state.get("language", "es")
            language_instruction = self._language_instructions.get(
                language, self._language_instructions["es"]
            )

            prompt = await self._prompt_manager.get_prompt(
                PromptRegistry.AGENTS_SUPERVISOR_ENHANCEMENT,
                variables={
                    "user_message": user_message,
                    "original_response": original_response,
                    "customer_name_section": customer_name_section,
                    "conversation_summary": conversation_summary,
                    "language_instruction": language_instruction,
                },
            )

            template = await self._prompt_manager.get_template(
                PromptRegistry.AGENTS_SUPERVISOR_ENHANCEMENT
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
            logger.warning(f"Error enhancing response: {e}")
            return original_response  # Return original on error
