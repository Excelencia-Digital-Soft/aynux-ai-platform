# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Global keyword matcher for routing.
#              Matches global keywords from database configuration.
# Tenant-Aware: Yes - uses configs loaded per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Global Keyword Matcher - Matches global keywords from database config.

Global keywords can interrupt most flows (e.g., "menu", "cancelar", "ayuda").
When awaiting input, only escape intents are allowed to interrupt.

Special handling for payment keywords:
- When "pagar" or "pagar deuda" is matched with an amount (e.g., "pagar 1111 pesos"),
  the matcher routes to pay_partial instead of pay_debt_menu with the amount in metadata.

Usage:
    matcher = GlobalKeywordMatcher()
    result = await matcher.matches(ctx)
    if result:
        # Handle global keyword match
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchResult

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchContext

logger = logging.getLogger(__name__)

# Intents that trigger amount detection for partial payment
PAYMENT_INTENTS_WITH_AMOUNT = {"pay_debt_menu"}


class GlobalKeywordMatcher:
    """
    Matches global keywords from database configuration.

    Single Responsibility: Check if message matches a global keyword.

    Priority: 100 (high priority, can interrupt flows)

    Global keywords:
    - Can interrupt most flows when not awaiting input
    - Only escape intents can interrupt when awaiting input
    """

    priority = 100

    async def matches(self, ctx: "MatchContext") -> MatchResult | None:
        """
        Check if message matches a global keyword.

        Args:
            ctx: Match context with message, state, and configs

        Returns:
            MatchResult if matched, None otherwise
        """
        configs = ctx.config_loader.get_configs_by_type("global_keyword")
        if not configs:
            return None

        for config in configs:
            if self._matches_config(ctx.message_lower, config):
                # If awaiting input, only allow escape intents
                if ctx.awaiting:
                    if config.target_intent not in ctx.config_loader.escape_intents:
                        logger.info(
                            f"[MATCHER] Global keyword '{config.trigger_value}' ignored "
                            f"while awaiting '{ctx.awaiting}' (not escape: {config.target_intent})"
                        )
                        continue

                # Check for amount in payment-related messages
                # "Pagar 1111 pesos" should route to pay_partial with amount
                if config.target_intent in PAYMENT_INTENTS_WITH_AMOUNT:
                    amount = self._extract_amount(ctx.message)
                    if amount is not None and amount > 0:
                        logger.info(
                            f"[MATCHER] Payment with amount detected: {amount} -> pay_partial"
                        )
                        return MatchResult(
                            config=config,
                            match_type="global_keyword_with_amount",
                            handler_key="global_keyword_amount",
                            metadata={
                                "amount": amount,
                                "original_intent": config.target_intent,
                                "target_intent": "pay_partial",
                                "target_node": "payment_processor",
                            },
                        )

                logger.info(f"[MATCHER] Global keyword matched: {config.trigger_value}")
                return MatchResult(
                    config=config,
                    match_type="global_keyword",
                    handler_key="global_keyword",
                )

        return None

    def _extract_amount(self, message: str) -> float | None:
        """
        Extract amount from message using AmountValidator.

        Args:
            message: User message

        Returns:
            Extracted amount or None
        """
        try:
            from app.domains.pharmacy.agents.utils.payment import AmountValidator

            return AmountValidator.extract_amount(message)
        except Exception as e:
            logger.warning(f"Error extracting amount: {e}")
            return None

    def _matches_config(self, message: str, config) -> bool:
        """
        Check if message matches a specific config.

        Matches:
        - Exact match with trigger_value
        - Message starts with trigger_value + space
        - Any alias match (from metadata.aliases)

        Args:
            message: Lowercase, stripped message
            config: RoutingConfigDTO to check

        Returns:
            True if message matches
        """
        trigger = config.trigger_value.lower()

        # Check direct match
        if message == trigger or message.startswith(trigger + " "):
            return True

        # Check aliases
        if config.metadata and "aliases" in config.metadata:
            for alias in config.metadata["aliases"]:
                alias_lower = alias.lower()
                if message == alias_lower or message.startswith(alias_lower + " "):
                    return True

        return False


__all__ = ["GlobalKeywordMatcher"]
