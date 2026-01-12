"""
Pharmacy Router

Main routing component for intent analysis and node selection.
Single responsibility: coordinate intent routing decisions.

Implements CASO 2 and Interruptions from docs/pharmacy_flujo_mejorado_v2.md:
- Menu number detection (1-6, 0)
- Global keyword handling (MENU, AYUDA, CANCELAR, SALIR, HUMANO, INICIO)
- Priority: Global keywords > Menu numbers > Intent analysis
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.domains.pharmacy.agents.routing.fallback_router import FallbackRouter
from app.domains.pharmacy.agents.routing.state_builder import RoutingStateBuilder
from app.domains.pharmacy.agents.utils.conversation_context import ConversationContextBuilder
from app.domains.pharmacy.agents.utils.greeting_detector import GreetingDetector
from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.intent_analyzer import PharmacyIntentAnalyzer
    from app.domains.pharmacy.agents.state import PharmacyState

logger = logging.getLogger(__name__)


# Intent to node mapping - imported here to avoid circular imports
INTENT_NODE_MAP: dict[str, str] = {
    "debt_query": "debt_check_node",
    "confirm": "confirmation_node",
    "invoice": "invoice_generation_node",
    "payment_link": "payment_link_node",
    "register": "customer_registration_node",
    "info_query": "pharmacy_info_node",
    "payment_history": "payment_history_node",
    "help": "help_center_node",
    "change_person": "person_selection_node",
    "farewell": "farewell_node",
    "show_menu": "main_menu_node",
    "human_escalation": "human_escalation_node",
}

DEFAULT_NODE = "debt_check_node"

# Menu option to intent mapping (CASO 2)
MENU_OPTIONS: dict[str, str] = {
    "1": "debt_query",
    "2": "payment_link",
    "3": "payment_history",
    "4": "info_query",
    "5": "change_person",
    "6": "help",
    "0": "farewell",
}

# Emoji to number mapping
EMOJI_TO_NUMBER: dict[str, str] = {
    "1️⃣": "1",
    "2️⃣": "2",
    "3️⃣": "3",
    "4️⃣": "4",
    "5️⃣": "5",
    "6️⃣": "6",
    "0️⃣": "0",
}

# Global keywords (Interruptions from pharmacy_flujo_mejorado_v2.md)
GLOBAL_KEYWORDS: dict[str, str] = {
    "menu": "show_menu",
    "menú": "show_menu",
    "ayuda": "help",
    "cancelar": "cancel_flow",
    "salir": "farewell",
    "humano": "human_escalation",
    "agente": "human_escalation",
    "persona": "human_escalation",
    "operador": "human_escalation",
    "inicio": "show_menu",
    "volver": "show_menu",
    "atrás": "show_menu",
    "atras": "show_menu",
}


class PharmacyRouter:
    """
    Main router for pharmacy domain intent analysis and routing.

    Responsibility: Coordinate intent analysis and route to appropriate nodes.
    """

    def __init__(
        self,
        intent_analyzer: PharmacyIntentAnalyzer,
        fallback_router: FallbackRouter,
        state_builder: RoutingStateBuilder | None = None,
        greeting_detector: GreetingDetector | None = None,
        context_builder: ConversationContextBuilder | None = None,
    ):
        """
        Initialize the router.

        Args:
            intent_analyzer: The intent analyzer instance
            fallback_router: The fallback router instance
            state_builder: Optional state builder (created if not provided)
            greeting_detector: Optional greeting detector (created if not provided)
            context_builder: Optional context builder (created if not provided)
        """
        self.intent_analyzer = intent_analyzer
        self.fallback_router = fallback_router
        self.state_builder = state_builder or RoutingStateBuilder()
        self.greeting_detector = greeting_detector or GreetingDetector()
        self.context_builder = context_builder or ConversationContextBuilder()

    def _get_organization_id(self, state: "PharmacyState") -> UUID | None:
        """Extract organization_id from state for multi-tenant intent analysis."""
        org_id = state.get("organization_id")
        if org_id is None:
            return None
        if isinstance(org_id, UUID):
            return org_id
        try:
            return UUID(str(org_id))
        except (ValueError, TypeError):
            return None

    async def route(self, state: PharmacyState) -> dict[str, Any]:
        """
        Route incoming query to appropriate pharmacy node.

        Priority order:
        1. Handle just-identified customers
        2. Check for global keywords (MENU, AYUDA, CANCELAR, SALIR, HUMANO)
        3. Check for menu numbers (1-6, 0)
        4. Run intent analysis

        Args:
            state: Current conversation state

        Returns:
            State update dictionary with routing decision
        """
        try:
            # Handle just-identified customers
            identification_result = await self._handle_just_identified(state)
            if identification_result is not None:
                # If we got a final result, return it
                if identification_result.get("_is_final"):
                    del identification_result["_is_final"]
                    return identification_result

            # Extract identification updates for later merging
            identification_updates = identification_result or {}

            # Extract message content
            message_content = MessageExtractor.extract_last_human_message(state)
            if not message_content:
                return self.state_builder.build_end_state_update(
                    is_complete=True,
                    **identification_updates,
                )

            # === PRIORITY 1: Check global keywords ===
            global_intent = self._detect_global_keyword(message_content)
            if global_intent:
                logger.info(f"Global keyword detected: {global_intent}")
                return self._handle_global_keyword(global_intent, state, identification_updates)

            # === PRIORITY 2: Check menu numbers (only if in menu context) ===
            if state.get("current_menu"):
                menu_intent = self._detect_menu_option(message_content)
                if menu_intent:
                    logger.info(f"Menu option detected: {menu_intent}")
                    return self._handle_menu_option(menu_intent, state, identification_updates)

            # === PRIORITY 3: Intent analysis ===
            # Build context for intent analysis
            context = self._build_analysis_context(state)

            # Analyze intent (pass organization_id for multi-tenant patterns)
            org_id = self._get_organization_id(state)
            intent_result = await self.intent_analyzer.analyze(
                message_content, context, organization_id=org_id
            )
            logger.info(
                f"Intent: {intent_result.intent} "
                f"(conf: {intent_result.confidence:.2f}, method: {intent_result.method})"
            )

            # Handle fallback intents
            if intent_result.is_out_of_scope or self.fallback_router.is_fallback_intent(
                intent_result.intent
            ):
                result = await self.fallback_router.handle(
                    intent_result.intent, message_content, state
                )
                return self.state_builder.merge_identification_updates(
                    result, identification_updates
                )

            # Handle invoice intent without debt_id
            if intent_result.intent == "invoice" and not state.get("debt_id"):
                logger.info("Invoice intent without debt_id - auto-fetching debt first")
                return self.state_builder.merge_identification_updates(
                    self.state_builder.build_auto_debt_fetch_update(
                        intent=intent_result.intent,
                        confidence=intent_result.confidence,
                        entities=intent_result.entities,
                    ),
                    identification_updates,
                )

            # Check if intent requires authentication
            requires_auth = intent_result.intent in {
                "debt_query", "payment_link", "payment_history", "change_person"
            }
            if requires_auth and not state.get("customer_identified"):
                logger.info(
                    f"Intent '{intent_result.intent}' requires auth - "
                    f"routing to person_resolution_node"
                )
                updates = {
                    "pharmacy_intent_type": intent_result.intent,
                    "pending_flow": intent_result.intent,
                    "next_agent": "person_resolution_node",
                    "routing_decision": {
                        "intent": intent_result.intent,
                        "confidence": intent_result.confidence,
                        "method": intent_result.method,
                        "requires_auth": True,
                    },
                }
                # Preserve payment amount if extracted
                extracted_amount = intent_result.entities.get("amount")
                if extracted_amount and extracted_amount > 0:
                    updates["payment_amount"] = extracted_amount
                    logger.info(f"Preserving payment_amount={extracted_amount} for post-auth")

                return self.state_builder.merge_identification_updates(
                    updates, identification_updates
                )

            # Build standard routing update
            next_node = INTENT_NODE_MAP.get(intent_result.intent, DEFAULT_NODE)
            updates = self.state_builder.build_intent_state_update(
                intent=intent_result.intent,
                next_node=next_node,
                confidence=intent_result.confidence,
                method=intent_result.method,
                entities=intent_result.entities,
            )

            # Handle payment amount extraction
            extracted_amount = intent_result.entities.get("amount")
            total_debt = state.get("total_debt", 0) or 0

            if extracted_amount and extracted_amount > 0:
                updates = self.state_builder.build_payment_state_update(
                    payment_amount=extracted_amount,
                    total_debt=total_debt,
                    base_updates=updates,
                )
                logger.info(
                    f"Partial payment detected: requested=${extracted_amount}, "
                    f"total_debt=${total_debt}, payment_amount=${updates.get('payment_amount')}"
                )

            return self.state_builder.merge_identification_updates(
                updates, identification_updates
            )

        except Exception as e:
            logger.error(f"Error in pharmacy routing: {e}", exc_info=True)
            error_response = await self.fallback_router.handle_error(e, state)
            error_response["next_agent"] = DEFAULT_NODE
            return error_response

    async def _handle_just_identified(
        self, state: PharmacyState
    ) -> dict[str, Any] | None:
        """
        Handle customers who were just identified.

        Args:
            state: Current conversation state

        Returns:
            State updates if just identified, None otherwise.
            If _is_final is True, the result should be returned immediately.
        """
        if not state.get("just_identified"):
            return None

        pending_greeting = state.get("pending_greeting")
        message_content = MessageExtractor.extract_last_human_message(state)

        # Check if message has content beyond greeting
        has_additional_content = self.greeting_detector.has_content_beyond_greeting(
            message_content
        )

        if pending_greeting:
            if has_additional_content:
                # User asked something along with greeting - continue processing
                logger.info(
                    f"Just identified with additional content: "
                    f"'{message_content[:50] if message_content else ''}...'"
                )
                return {
                    "just_identified": False,
                    "greeting_sent": True,
                }
            else:
                # Just a greeting - return greeting and end
                from langchain_core.messages import AIMessage

                return {
                    "_is_final": True,  # Marker to indicate this is the final result
                    "just_identified": False,
                    "pending_greeting": None,
                    "greeting_sent": True,
                    "messages": [AIMessage(content=pending_greeting)],
                    "pharmacy_intent_type": "greeting",
                    "next_agent": "__end__",
                    "is_complete": False,
                }

        # Fallback: generate greeting only if no pending_greeting exists
        result = await self.fallback_router.handle_greeting("", state)
        return {"_is_final": True, "just_identified": False, **result}

    def _build_analysis_context(self, state: PharmacyState) -> dict[str, Any]:
        """
        Build context dictionary for intent analysis.

        Args:
            state: Current conversation state

        Returns:
            Context dictionary
        """
        conversation_history = self.context_builder.format_recent_history(
            dict(state), max_turns=5
        )

        return {
            "customer_identified": state.get("customer_identified", False),
            "awaiting_confirmation": state.get("awaiting_confirmation", False),
            "awaiting_document_input": state.get("awaiting_document_input", False),
            "requires_disambiguation": state.get("requires_disambiguation", False),
            "debt_status": state.get("debt_status"),
            "has_debt": state.get("has_debt", False),
            "conversation_history": conversation_history,
        }

    # =========================================================================
    # Menu and Global Keyword Detection (pharmacy_flujo_mejorado_v2.md)
    # =========================================================================

    def _detect_global_keyword(self, message: str) -> str | None:
        """
        Detect global keywords that interrupt any flow.

        Global keywords have highest priority and always trigger their action.

        Args:
            message: User's message

        Returns:
            Intent string if keyword detected, None otherwise
        """
        message_lower = message.strip().lower()

        # Check for exact match first
        if message_lower in GLOBAL_KEYWORDS:
            return GLOBAL_KEYWORDS[message_lower]

        # Check if message starts with keyword (for phrases like "ayuda por favor")
        for keyword, intent in GLOBAL_KEYWORDS.items():
            if message_lower.startswith(keyword):
                return intent

        return None

    def _detect_menu_option(self, message: str) -> str | None:
        """
        Detect menu option numbers (1-6, 0) including emoji variants.

        Args:
            message: User's message

        Returns:
            Intent string if menu option detected, None otherwise
        """
        message_clean = message.strip()

        # Check for exact number match
        if message_clean in MENU_OPTIONS:
            return MENU_OPTIONS[message_clean]

        # Check for emoji numbers
        for emoji, number in EMOJI_TO_NUMBER.items():
            if emoji in message_clean:
                return MENU_OPTIONS.get(number)

        return None

    def _handle_global_keyword(
        self,
        intent: str,
        state: "PharmacyState",
        identification_updates: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle global keyword intent.

        Preserves pending flow context when interrupting.

        Args:
            intent: The detected intent
            state: Current state
            identification_updates: Updates from identification

        Returns:
            State update dictionary
        """
        # Preserve current flow context for potential resume
        pending_flow = state.get("pending_flow")
        current_flow_context = None

        if not pending_flow and state.get("current_menu"):
            # Save current context if interrupting a flow
            current_flow_context = {
                "current_menu": state.get("current_menu"),
                "awaiting_debt_action": state.get("awaiting_debt_action"),
                "awaiting_payment_confirmation": state.get("awaiting_payment_confirmation"),
                "awaiting_payment_amount_input": state.get("awaiting_payment_amount_input"),
            }

        # Build routing update
        next_node = INTENT_NODE_MAP.get(intent, "main_menu_node")

        updates: dict[str, Any] = {
            "pharmacy_intent_type": intent,
            "next_agent": next_node,
            "routing_decision": {
                "intent": intent,
                "confidence": 1.0,
                "method": "global_keyword",
            },
        }

        # Handle cancel flow
        if intent == "cancel_flow":
            updates.update({
                "pending_flow": None,
                "pending_flow_context": None,
                "awaiting_debt_action": False,
                "awaiting_payment_confirmation": False,
                "awaiting_payment_amount_input": False,
                "next_agent": "main_menu_node",
            })
        elif current_flow_context:
            updates["pending_flow"] = state.get("current_menu")
            updates["pending_flow_context"] = current_flow_context

        return self.state_builder.merge_identification_updates(
            updates, identification_updates
        )

    def _handle_menu_option(
        self,
        intent: str,
        state: "PharmacyState",
        identification_updates: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle menu option selection.

        Routes directly to the appropriate node based on menu selection.

        Args:
            intent: The detected intent from menu option
            state: Current state
            identification_updates: Updates from identification

        Returns:
            State update dictionary
        """
        next_node = INTENT_NODE_MAP.get(intent, DEFAULT_NODE)

        # Check if customer needs to be identified for this intent
        requires_auth = intent in ["debt_query", "payment_link", "payment_history", "change_person"]
        if requires_auth and not state.get("customer_identified"):
            # Route to identification first
            updates = {
                "pharmacy_intent_type": intent,
                "pending_flow": intent,
                "next_agent": "person_resolution_node",
                "routing_decision": {
                    "intent": intent,
                    "confidence": 1.0,
                    "method": "menu_option",
                    "requires_auth": True,
                },
            }
        else:
            updates = {
                "pharmacy_intent_type": intent,
                "next_agent": next_node,
                "current_menu": None,  # Clear menu context after selection
                "routing_decision": {
                    "intent": intent,
                    "confidence": 1.0,
                    "method": "menu_option",
                },
            }

        return self.state_builder.merge_identification_updates(
            updates, identification_updates
        )
