# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Global keyword route handler.
#              Handles global keyword routing with context switching.
# Tenant-Aware: Yes - uses configs loaded per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Global Keyword Handler - Handles global keyword routing.

Processes global keyword matches with:
- Authentication checking via AuthChecker
- Context switching (preserves previous_intent)
- Context clearing for cancel/exit intents

Usage:
    handler = GlobalKeywordHandler(auth_checker, config_loader)
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


class GlobalKeywordHandler(BaseRouteHandler):
    """
    Handles global keyword routing.

    Single Responsibility: Process global keyword matches into state updates.

    Handles:
    - Auth redirection if required
    - Context switching (previous_intent preservation)
    - Context clearing for cancel/exit keywords
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
        Handle global keyword routing.

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
            logger.info(f"Global keyword '{config.trigger_value}' requires auth")
            return auth_redirect

        # Build state updates
        target_node = config.target_node or self._config_loader.get_default_node(
            config.target_intent
        )

        updates: dict[str, Any] = {
            "intent": config.target_intent,
            "previous_intent": current_intent,
            "awaiting_input": None,  # Clear any pending input
            "next_node": target_node,
        }

        # Handle context clearing for cancel/exit keywords
        if config.clears_context:
            updates.update({
                "awaiting_payment_confirmation": False,
                "awaiting_account_selection": False,
            })

        logger.info(f"[HANDLER] Global keyword -> {config.target_intent} -> {target_node}")
        return updates


__all__ = ["GlobalKeywordHandler"]
