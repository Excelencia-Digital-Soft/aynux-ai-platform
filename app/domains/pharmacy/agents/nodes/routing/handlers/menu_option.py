# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Menu option route handler.
#              Handles menu selection routing.
# Tenant-Aware: Yes - uses configs loaded per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Menu Option Handler - Handles menu option routing.

Processes menu selections (1-6, 0) when user is in menu context.

Usage:
    handler = MenuOptionHandler(auth_checker, config_loader)
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


class MenuOptionHandler(BaseRouteHandler):
    """
    Handles menu option routing.

    Single Responsibility: Process menu option matches into state updates.

    Handles:
    - Auth redirection if required
    - Menu context clearing (awaiting_input = None)
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
        Handle menu option routing.

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
            logger.info(f"Menu option '{config.trigger_value}' requires auth")
            return auth_redirect

        # Get target node
        target_node = config.target_node or self._config_loader.get_default_node(
            config.target_intent
        )

        logger.info(f"[HANDLER] Menu option -> {config.target_intent} -> {target_node}")
        return {
            "intent": config.target_intent,
            "previous_intent": current_intent,
            "awaiting_input": None,  # Clear menu context
            "next_node": target_node,
        }


__all__ = ["MenuOptionHandler"]
