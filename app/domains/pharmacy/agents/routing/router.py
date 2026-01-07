"""
Pharmacy Router

Main routing component for intent analysis and node selection.
Single responsibility: coordinate intent routing decisions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

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
}

DEFAULT_NODE = "debt_check_node"


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

    async def route(self, state: PharmacyState) -> dict[str, Any]:
        """
        Route incoming query to appropriate pharmacy node.

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

            # Build context for intent analysis
            context = self._build_analysis_context(state)

            # Analyze intent
            intent_result = await self.intent_analyzer.analyze(message_content, context)
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
