# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Button selection route handler.
#              Handles WhatsApp button/list selection routing.
# Tenant-Aware: Yes - uses configs loaded per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Button Selection Handler - Handles button/list selection routing.

Processes button and list selections from WhatsApp interactive messages.
Handles special confirmation buttons that don't change node.

Usage:
    handler = ButtonSelectionHandler(auth_checker, config_loader)
    result = handler.handle(match, state)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.nodes.routing.handlers.base import BaseRouteHandler

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.routing.auth_checker import AuthChecker
    from app.domains.pharmacy.agents.nodes.routing.config_loader import RoutingConfigLoader
    from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchResult

logger = logging.getLogger(__name__)

# Confirmation intents that don't change node (handled by current node)
INLINE_CONFIRMATION_INTENTS = frozenset({
    "confirm_yes",
    "confirm_no",
    "own_debt",
    "other_debt",
})


class ButtonSelectionHandler(BaseRouteHandler):
    """
    Handles button/list selection routing.

    Single Responsibility: Process button selection matches into state updates.

    Handles:
    - Auth redirection if required
    - Inline confirmations (don't change node)
    - Standard button selections (change node)
    """

    def __init__(
        self,
        auth_checker: "AuthChecker",
        config_loader: "RoutingConfigLoader",
    ) -> None:
        super().__init__(auth_checker, config_loader)

    def handle(
        self,
        match: "MatchResult",
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle button selection routing.

        Args:
            match: Match result with config
            state: Current conversation state

        Returns:
            State update dictionary
        """
        config = match.config
        if not config:
            return {}

        current_intent = self._get_current_intent(state)

        # Check if auth redirect needed
        auth_redirect = self._auth_checker.requires_redirect(config, state)
        if auth_redirect:
            logger.info(f"Button '{config.trigger_value}' requires auth")
            return auth_redirect

        # For confirmation buttons, don't change node - let current node handle
        if config.target_intent in INLINE_CONFIRMATION_INTENTS:
            logger.info(f"[HANDLER] Inline confirmation: {config.target_intent}")
            return {
                "intent": config.target_intent,
                "previous_intent": current_intent,
            }

        # Standard button - change node
        target_node = config.target_node or self._config_loader.get_default_node(
            config.target_intent
        )

        logger.info(f"[HANDLER] Button selection -> {config.target_intent} -> {target_node}")
        return {
            "intent": config.target_intent,
            "previous_intent": current_intent,
            "awaiting_input": None,
            "next_node": target_node,
        }


class KnownListItemHandler:
    """
    Handles known list item patterns without database config.

    Single Responsibility: Process known list item matches into state updates.
    """

    def handle(
        self,
        match: "MatchResult",
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle known list item routing.

        Args:
            match: Match result with metadata
            state: Current conversation state

        Returns:
            State update dictionary
        """
        if not match.metadata:
            return {}

        current_intent = state.get("intent")

        logger.info(f"[HANDLER] Known list item -> {match.metadata.get('intent')}")
        return {
            "intent": match.metadata.get("intent", "unknown"),
            "previous_intent": current_intent,
            "awaiting_input": match.metadata.get("awaiting_input"),
            "awaiting_account_selection": False,
            "next_node": match.metadata.get("next_node", "router"),
        }


__all__ = ["ButtonSelectionHandler", "KnownListItemHandler"]
