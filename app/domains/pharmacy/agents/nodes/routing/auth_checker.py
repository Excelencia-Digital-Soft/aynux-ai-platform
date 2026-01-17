# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Centralized authentication requirement checking.
#              Single source of truth for auth redirect logic.
# Tenant-Aware: Yes - checks auth status from state.
# Domain-Aware: Yes - uses config_loader for domain-specific rules.
# ============================================================================
"""
Authentication Checker - Centralized auth requirement checking.

Consolidates authentication logic that was duplicated across
multiple handler methods (_handle_global_keyword, _handle_button_selection,
_handle_menu_option).

Usage:
    checker = AuthChecker(config_loader)

    redirect = checker.requires_redirect(config, state)
    if redirect:
        return redirect  # State updates for auth redirect

    # Continue with normal handling...
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.cache.routing_config_cache import RoutingConfigDTO
    from app.domains.pharmacy.agents.nodes.routing.config_loader import RoutingConfigLoader

logger = logging.getLogger(__name__)


class AuthChecker:
    """
    Centralized authentication requirement checking.

    Single Responsibility: Determine if routing requires auth redirect.

    Checks both:
    1. config.requires_auth on the matched routing config
    2. intent_node_mapping for the target intent's auth requirement

    This replaces duplicated auth checking in 3+ handler methods.
    """

    def __init__(self, config_loader: "RoutingConfigLoader") -> None:
        """
        Initialize checker with config loader.

        Args:
            config_loader: Loaded routing configuration
        """
        self._config_loader = config_loader

    def requires_redirect(
        self,
        config: "RoutingConfigDTO",
        state: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Check if auth redirect is needed and return state updates.

        Checks:
        1. config.requires_auth flag on the matched config
        2. Intent-level auth requirement from intent_node_mapping

        Args:
            config: Matched routing configuration
            state: Current conversation state

        Returns:
            State updates for auth redirect, or None if no redirect needed
        """
        # Get current intent for context preservation
        current_intent = state.get("intent")

        # Check if already authenticated
        if state.get("is_authenticated"):
            return None

        # Check config-level auth requirement
        config_requires_auth = config.requires_auth

        # Check intent-level auth requirement
        intent_requires_auth = self._config_loader.intent_requires_auth(
            config.target_intent
        )

        # Either source can require auth
        requires_auth = config_requires_auth or intent_requires_auth

        if requires_auth:
            logger.info(
                f"Auth required for '{config.target_intent}' "
                f"(config={config_requires_auth}, intent={intent_requires_auth})"
            )
            return {
                "intent": config.target_intent,
                "previous_intent": current_intent,
                "next_node": "auth_plex",
                "awaiting_input": None,
            }

        return None

    def check_intent_auth(
        self,
        intent: str,
        state: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Check if intent requires auth (without a matched config).

        Used when routing to an intent without a specific config match.

        Args:
            intent: Target intent
            state: Current conversation state

        Returns:
            State updates for auth redirect, or None if no redirect needed
        """
        if state.get("is_authenticated"):
            return None

        if self._config_loader.intent_requires_auth(intent):
            current_intent = state.get("intent")
            logger.info(f"Auth required for intent '{intent}'")
            return {
                "intent": intent,
                "previous_intent": current_intent,
                "next_node": "auth_plex",
                "awaiting_input": None,
            }

        return None


__all__ = ["AuthChecker"]
