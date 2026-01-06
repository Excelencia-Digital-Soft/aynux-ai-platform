"""Intent validation and agent mapping.

Extracted from IntentRouter to follow Single Responsibility Principle.
Handles intent validation, agent mapping, and multi-turn flow detection.
"""

import logging
from typing import Any

from app.core.schemas import get_intent_to_agent_mapping, get_valid_intents

logger = logging.getLogger(__name__)


class IntentValidator:
    """Validates intents and maps them to agents.

    Responsibilities:
    - Validate intents against schema
    - Map agent names to intent names (LLM correction)
    - Map intents to target agents
    - Detect active multi-turn flows
    """

    # Mapping from agent names to valid intents
    # Used when LLM returns agent name instead of intent name
    AGENT_TO_INTENT_MAPPING: dict[str, str] = {
        "excelencia_agent": "excelencia",
        "excelencia_support_agent": "excelencia_soporte",
        "excelencia_invoice_agent": "excelencia_facturacion",
        "excelencia_promotions_agent": "excelencia_promociones",
        "support_agent": "soporte",
        "greeting_agent": "saludo",
        "fallback_agent": "fallback",
        "farewell_agent": "despedida",
        "product_agent": "producto",
        "ecommerce_agent": "ecommerce",
        "data_insights_agent": "datos",
        "pharmacy_operations_agent": "pharmacy",
    }

    # Agents with multi-turn conversational flows
    FLOW_AGENTS: set[str] = {
        "excelencia_support_agent",  # 3-step incident creation
        "excelencia_invoice_agent",  # Invoice lookup flow
        "pharmacy_operations_agent",  # Pharmacy operations
    }

    # Keyword-based routing for fallback scenarios
    # Used when follow_up is detected but no previous agent exists
    KEYWORD_TO_AGENT: dict[str, list[str]] = {
        "pharmacy_operations_agent": [
            "receta", "medicamento", "farmacia", "medicamentos", "pedido farmacia",
            "deuda farmacia", "urgente receta", "envié receta", "mandé receta",
        ],
        "excelencia_support_agent": [
            "problema", "error", "falla", "no funciona", "ayuda", "soporte",
            "incidente", "bug", "ticket",
        ],
        "excelencia_invoice_agent": [
            "factura", "facturación", "cobro", "pago", "cuenta", "deuda",
        ],
        "greeting_agent": [
            "hola", "buenos días", "buenas tardes", "buenas noches", "hi", "hello",
        ],
        "farewell_agent": [
            "adiós", "chao", "bye", "hasta luego", "gracias", "nos vemos",
        ],
    }

    def validate_and_map_intent(
        self,
        intent: str,
        valid_intents: set[str] | None = None,
    ) -> tuple[str, float, str]:
        """Validate intent and map if needed.

        Args:
            intent: Intent from LLM response
            valid_intents: Set of valid intents (defaults to schema intents + follow_up)

        Returns:
            Tuple of (validated_intent, confidence, reasoning)
        """
        if valid_intents is None:
            valid_intents = set(get_valid_intents()) | {"follow_up"}

        # Check if already valid
        if intent in valid_intents:
            return intent, 1.0, "Valid intent"

        # Try mapping agent name to intent
        mapped_intent = self.AGENT_TO_INTENT_MAPPING.get(intent)
        if mapped_intent and mapped_intent in valid_intents:
            logger.info(f"Mapped agent name '{intent}' to intent '{mapped_intent}'")
            return mapped_intent, 0.9, f"Mapped from agent name '{intent}'"

        # Invalid intent - fallback
        logger.warning(f"Invalid intent detected: {intent}. Using fallback intent.")
        return "fallback", 0.4, "LLM returned an invalid intent"

    def map_intent_to_agent(self, intent: str) -> str:
        """Map intent to target agent.

        Args:
            intent: Validated intent name

        Returns:
            Agent name to route to
        """
        mapping = get_intent_to_agent_mapping()
        agent = mapping.get(intent, "fallback_agent")
        logger.debug(f"Mapping intent '{intent}' to agent '{agent}'")
        return agent

    def check_active_flow(self, conversation_data: dict[str, Any] | None) -> dict[str, Any] | None:
        """Check if previous agent has an active flow that should continue.

        This prevents routing away from agents during multi-step flows like:
        - excelencia_support_agent: incident creation (description → priority → confirm)
        - excelencia_invoice_agent: invoice lookup flow
        - pharmacy_operations_agent: pharmacy operations

        Args:
            conversation_data: Conversation context dict

        Returns:
            Flow continuation result if active flow detected, None otherwise
        """
        if not conversation_data:
            return None

        previous_agent = conversation_data.get("previous_agent")

        # Skip if no previous agent or if it was orchestrator/supervisor
        if not previous_agent or previous_agent in ("orchestrator", "supervisor"):
            return None

        if previous_agent in self.FLOW_AGENTS:
            logger.info(f"Active flow detected, continuing with {previous_agent}")
            return {
                "primary_intent": "follow_up",
                "intent": "follow_up",
                "confidence": 0.95,
                "target_agent": previous_agent,
                "requires_handoff": False,
                "entities": {},
                "method": "flow_continuation",
                "reasoning": f"Continuing active flow with {previous_agent}",
            }

        return None

    def _try_keyword_routing(self, message: str) -> str | None:
        """Try to route based on keywords in the message.

        This is used as a fallback when follow_up is detected but there's
        no previous agent to route to. Instead of going to fallback_agent,
        we try to match keywords to find an appropriate agent.

        Args:
            message: User message text

        Returns:
            Agent name if keywords match, None otherwise
        """
        if not message:
            return None

        message_lower = message.lower()

        # Check each agent's keywords
        for agent, keywords in self.KEYWORD_TO_AGENT.items():
            for keyword in keywords:
                if keyword in message_lower:
                    logger.info(f"Keyword '{keyword}' matched, routing to {agent}")
                    return agent

        return None

    def handle_follow_up_intent(
        self,
        conversation_data: dict[str, Any] | None,
    ) -> str:
        """Determine target agent for follow_up intent.

        When follow_up is detected but no previous agent exists (e.g., new
        conversation misclassified as follow_up), tries keyword-based routing
        before falling back.

        Args:
            conversation_data: Conversation context

        Returns:
            Target agent name
        """
        if not conversation_data:
            return "fallback_agent"

        previous_agent = conversation_data.get("previous_agent")
        if previous_agent and previous_agent not in ("orchestrator", None):
            logger.info(f"Follow-up detected, routing to previous agent: {previous_agent}")
            return previous_agent

        # No previous agent - this might be a misclassification
        # Try keyword-based routing before defaulting to fallback
        message = conversation_data.get("message", "")
        if message:
            keyword_agent = self._try_keyword_routing(message)
            if keyword_agent:
                logger.info(f"Follow-up reclassified via keywords to: {keyword_agent}")
                return keyword_agent

        logger.warning("Follow-up detected but no previous agent and no keyword match, using fallback")
        return "fallback_agent"
