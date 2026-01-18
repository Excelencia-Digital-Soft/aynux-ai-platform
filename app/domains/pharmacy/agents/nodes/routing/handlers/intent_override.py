# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Intent override route handler.
#              Handles intent changes during awaited input states.
# Tenant-Aware: Yes - uses configs loaded per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Intent Override Handler - Handles intent changes during awaited input.

When a user says "pago parcial" during payment_confirmation, this handler
clears the awaited state and routes to the new intent's target node.

This allows users to change their mind during confirmation flows without
having to fully cancel and restart.

Usage:
    handler = IntentOverrideHandler(config_loader)
    result = handler.handle(match, state)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.routing.config_loader import RoutingConfigLoader
    from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchResult

logger = logging.getLogger(__name__)


class IntentOverrideHandler:
    """
    Handles intent override during awaited input.

    Single Responsibility: Process intent override matches into state updates.

    When an intent override is detected (e.g., "pago parcial" during
    payment_confirmation), this handler:
    1. Clears the awaiting_input state
    2. Sets the new intent from the override
    3. Routes to the new intent's target node
    4. Preserves the previous intent for context

    Example flow:
    - User is in payment_confirmation for full payment
    - User says "prefiero pago parcial"
    - Handler clears confirmation, sets intent=pay_partial
    - Routes to payment_processor for partial payment flow
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
        Handle intent override during awaited input.

        Args:
            match: Match result with metadata containing target_intent
            state: Current conversation state

        Returns:
            State update dictionary with:
            - intent: New intent from override
            - previous_intent: Intent before override
            - awaiting_input: None (cleared)
            - next_node: Target node for new intent
            - Additional context clearing for payment-related overrides
        """
        if not match.metadata:
            logger.warning("[HANDLER] Intent override without metadata")
            return {}

        target_intent = match.metadata.get("target_intent")
        if not target_intent:
            logger.warning("[HANDLER] Intent override without target_intent")
            return {}

        previous_awaiting = match.metadata.get("previous_awaiting")
        current_intent = state.get("intent")

        # Get the target node for the new intent
        target_node = self._config_loader.get_default_node(target_intent)

        updates: dict[str, Any] = {
            "intent": target_intent,
            "previous_intent": current_intent,
            "awaiting_input": None,  # Clear awaiting state
            "next_node": target_node,
        }

        # Clear payment-related context for payment overrides
        # This prevents stale payment data from affecting the new flow
        payment_intents = {"pay_partial", "pay_full", "check_debt", "view_invoice"}
        if target_intent in payment_intents or previous_awaiting in (
            "payment_confirmation",
            "pay_debt_action",
            "amount",
        ):
            updates.update({
                "awaiting_payment_confirmation": False,
                # Don't clear mp_payment_link here - let the new flow handle it
                # This allows switching between partial/full without losing context
                "payment_amount": None,
                "is_partial_payment": target_intent == "pay_partial",
            })

        logger.info(
            f"[HANDLER] Intent override: {current_intent} -> {target_intent} "
            f"(was awaiting: {previous_awaiting}) -> {target_node}"
        )
        return updates


__all__ = ["IntentOverrideHandler"]
