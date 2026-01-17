# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Awaited input route handler.
#              Handles routing for valid awaited input responses.
# Tenant-Aware: Yes - uses configs loaded per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Awaited Input Handler - Handles awaited input routing.

Routes valid awaited input responses to the appropriate handler node
based on database configuration.

Usage:
    handler = AwaitedInputHandler(config_loader)
    result = handler.handle(match, state)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.routing.config_loader import RoutingConfigLoader
    from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchResult

logger = logging.getLogger(__name__)


class AwaitedInputHandler:
    """
    Handles awaited input routing.

    Single Responsibility: Route awaited input to handler node from config.

    Uses awaiting_type_config from database to determine target_node.
    Falls back to "router" if no config found.
    """

    def __init__(self, config_loader: "RoutingConfigLoader") -> None:
        """
        Initialize handler with config loader.

        Args:
            config_loader: Loaded routing configuration
        """
        self._config_loader = config_loader

    def handle(
        self,
        match: "MatchResult",
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle awaited input routing.

        Args:
            match: Match result with metadata
            state: Current conversation state

        Returns:
            State update dictionary with next_node
        """
        # Check for special amount handling
        if match.handler_key == "awaited_input_amount" and match.metadata:
            next_node = match.metadata.get("next_node", "payment_processor")
            logger.info(f"[HANDLER] Awaited amount -> {next_node}")
            return {"next_node": next_node}

        # Get awaiting type from metadata
        awaiting_type = match.metadata.get("awaiting_type") if match.metadata else None

        if not awaiting_type:
            # Fallback to current awaiting_input from state
            awaiting_type = state.get("awaiting_input")

        if awaiting_type:
            # Look up handler node from database config
            config = self._config_loader.get_awaiting_config(awaiting_type)
            if config:
                logger.info(f"[HANDLER] Awaited input '{awaiting_type}' -> {config.target_node}")
                return {"next_node": config.target_node}

        # Fallback if no config found
        logger.warning(f"No awaiting type config for '{awaiting_type}', defaulting to router")
        return {"next_node": "router"}


__all__ = ["AwaitedInputHandler"]
