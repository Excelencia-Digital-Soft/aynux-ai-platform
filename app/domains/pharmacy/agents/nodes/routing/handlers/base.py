# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Base protocol for route handlers.
#              Implements Strategy Pattern for handling matched routes.
# Tenant-Aware: Yes - handlers receive org context via state.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Route Handler Protocol - Base interface for all route handlers.

Each handler processes a matched route and returns state updates.
Handlers implement the logic for context switching, auth checking, etc.

Usage:
    class MyHandler(RouteHandler):
        def handle(self, match, state) -> dict[str, Any]:
            # Process route and return state updates
            return {"next_node": "target_node", "intent": "some_intent"}
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.routing.auth_checker import AuthChecker
    from app.domains.pharmacy.agents.nodes.routing.config_loader import RoutingConfigLoader
    from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchResult


class RouteHandler(Protocol):
    """
    Protocol for route handlers.

    Each handler processes a matched route and returns state updates.
    Handlers are selected based on the match_type from MatchResult.
    """

    def handle(
        self,
        match: "MatchResult",
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle routing and return state updates.

        Args:
            match: The match result from a matcher
            state: Current conversation state

        Returns:
            State update dictionary with:
            - intent: New intent (if changed)
            - previous_intent: Previous intent (for context)
            - next_node: Target node to route to
            - awaiting_input: Cleared or set
            - Additional state updates as needed
        """
        ...


class BaseRouteHandler:
    """
    Base class for route handlers with common functionality.

    Provides shared utilities for auth checking and config lookup.
    """

    def __init__(
        self,
        auth_checker: "AuthChecker",
        config_loader: "RoutingConfigLoader",
    ) -> None:
        """
        Initialize handler with dependencies.

        Args:
            auth_checker: Centralized auth checking service
            config_loader: Routing configuration loader
        """
        self._auth_checker = auth_checker
        self._config_loader = config_loader

    def _get_current_intent(self, state: dict[str, Any]) -> str | None:
        """Extract current intent from state."""
        return state.get("intent")

    def _is_authenticated(self, state: dict[str, Any]) -> bool:
        """Check if user is authenticated."""
        return bool(state.get("is_authenticated"))


__all__ = ["BaseRouteHandler", "RouteHandler"]
