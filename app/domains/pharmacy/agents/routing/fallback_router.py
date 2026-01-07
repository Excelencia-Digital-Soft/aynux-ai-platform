"""
Fallback Router

Routes fallback intents to appropriate handlers.
Single responsibility: fallback intent delegation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.fallback_handler import PharmacyFallbackHandler
    from app.domains.pharmacy.agents.state import PharmacyState

logger = logging.getLogger(__name__)


class FallbackRouter:
    """
    Routes fallback intents to the appropriate handler methods.

    Responsibility: Delegate fallback intents to PharmacyFallbackHandler.
    """

    # Intents that are handled by the fallback handler
    FALLBACK_INTENTS: frozenset[str] = frozenset({
        "greeting",
        "reject",
        "unknown",
        "summary",
        "data_query",
        "info_query",
    })

    def __init__(self, fallback_handler: PharmacyFallbackHandler):
        """
        Initialize the fallback router.

        Args:
            fallback_handler: The fallback handler instance
        """
        self.handler = fallback_handler

    def is_fallback_intent(self, intent: str) -> bool:
        """
        Check if an intent should be handled as a fallback.

        Args:
            intent: The intent to check

        Returns:
            True if this is a fallback intent
        """
        return intent in self.FALLBACK_INTENTS

    async def handle(
        self,
        intent: str,
        message: str,
        state: PharmacyState,
    ) -> dict[str, Any]:
        """
        Handle a fallback intent by delegating to the appropriate handler method.

        Args:
            intent: The fallback intent type
            message: The user message
            state: Current conversation state

        Returns:
            State update dictionary from the handler
        """
        state_dict = dict(state)

        # Skip greeting generation if one was already sent this turn
        if intent == "greeting" and state.get("greeting_sent"):
            logger.info("Skipping duplicate greeting - already sent this turn")
            return {
                "next_agent": "__end__",
                "is_complete": False,
                "greeting_sent": False,  # Reset for next turn
            }

        # Route to appropriate handler method
        handler_method = self._get_handler_method(intent)
        if handler_method:
            return await handler_method(message, state_dict)

        # Default to unknown handler
        return await self.handler.handle_unknown(message, state_dict)

    def _get_handler_method(self, intent: str):
        """
        Get the appropriate handler method for an intent.

        Args:
            intent: The intent type

        Returns:
            The handler method or None
        """
        intent_to_method = {
            "greeting": self.handler.handle_greeting,
            "reject": lambda msg, state: self.handler.handle_cancelled(state),
            "summary": self.handler.handle_summary,
            "data_query": self.handler.handle_data_query,
            "info_query": self.handler.handle_info_query,
            "unknown": self.handler.handle_unknown,
        }
        return intent_to_method.get(intent)

    async def handle_greeting(
        self,
        message: str,
        state: PharmacyState,
    ) -> dict[str, Any]:
        """
        Handle a greeting intent.

        Args:
            message: The user message
            state: Current conversation state

        Returns:
            State update dictionary
        """
        return await self.handle("greeting", message, state)

    async def handle_rejection(
        self,
        state: PharmacyState,
    ) -> dict[str, Any]:
        """
        Handle a rejection/cancellation intent.

        Args:
            state: Current conversation state

        Returns:
            State update dictionary
        """
        return await self.handler.handle_cancelled(dict(state))

    async def handle_unknown(
        self,
        message: str,
        state: PharmacyState,
    ) -> dict[str, Any]:
        """
        Handle an unknown intent.

        Args:
            message: The user message
            state: Current conversation state

        Returns:
            State update dictionary
        """
        return await self.handler.handle_unknown(message, dict(state))

    async def handle_error(
        self,
        error: Exception,
        state: PharmacyState,
    ) -> dict[str, Any]:
        """
        Handle an error during routing.

        Args:
            error: The exception that occurred
            state: Current conversation state

        Returns:
            State update dictionary with error response
        """
        return await self.handler.handle_error(error, dict(state))
