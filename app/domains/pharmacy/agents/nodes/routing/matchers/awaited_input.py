# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Awaited input matcher for routing.
#              Validates responses when awaiting specific input types.
# Tenant-Aware: Yes - uses configs loaded per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Awaited Input Matcher - Validates and matches awaited input responses.

Highest priority matcher that protects awaited input from global keywords.
For example, prevents "otra persona" from triggering "otra cuenta" keyword
when awaiting "own_or_other" selection.

Usage:
    matcher = AwaitedInputMatcher()
    result = await matcher.matches(ctx)
    if result:
        # Valid awaited input, route to handler node
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from uuid import UUID

from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchResult
from app.domains.pharmacy.agents.utils.keyword_matcher import KeywordMatcher

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchContext

logger = logging.getLogger(__name__)


class AwaitedInputMatcher:
    """
    Validates awaited input responses.

    Single Responsibility: Check if message is a valid response for awaited input.

    Priority: 0 (highest - protects awaited input from global keywords)

    Validation:
    - Uses validation_pattern (regex) from awaiting_type_config
    - Uses valid_response_intents via KeywordMatcher
    - Special handling for amount-related awaiting states
    """

    priority = 0

    def __init__(self, db: "AsyncSession") -> None:
        """
        Initialize matcher with database session.

        Args:
            db: AsyncSession for KeywordMatcher operations
        """
        self._db = db

    async def matches(self, ctx: "MatchContext") -> MatchResult | None:
        """
        Check if message is a valid response for awaited input.

        Args:
            ctx: Match context with message, state, and configs

        Returns:
            MatchResult if valid awaited response, None otherwise
        """
        if not ctx.awaiting:
            return None

        # Get organization_id from state
        org_id = self._get_organization_id(ctx.state)

        # Check if valid awaited response
        is_valid = await self._is_valid_awaited_response(
            ctx.awaiting,
            ctx.message_lower,
            org_id,
            ctx.config_loader,
        )

        if is_valid:
            logger.info(f"[MATCHER] Valid awaited input for '{ctx.awaiting}'")

            # Check for special amount handling in pay_debt_action
            if ctx.awaiting == "pay_debt_action":
                amount = self._extract_amount(ctx.message)
                if amount is not None and amount > 0:
                    logger.info(f"[MATCHER] Amount {amount} in pay_debt_action -> payment_processor")
                    return MatchResult(
                        config=None,
                        match_type="awaited_input",
                        handler_key="awaited_input_amount",
                        metadata={"amount": amount, "next_node": "payment_processor"},
                    )

            return MatchResult(
                config=None,
                match_type="awaited_input",
                handler_key="awaited_input",
                metadata={"awaiting_type": ctx.awaiting},
            )

        return None

    async def _is_valid_awaited_response(
        self,
        awaiting: str,
        message: str,
        org_id: UUID | None,
        config_loader,
    ) -> bool:
        """
        Check if message is a valid response for the awaited input type.

        Args:
            awaiting: Current awaiting_input type
            message: User message to check
            org_id: Organization ID for DB lookup
            config_loader: Loaded routing configuration

        Returns:
            True if message is a valid response
        """
        # Special handling for amount-related awaiting states
        if awaiting in ("amount", "pay_debt_action"):
            amount = self._extract_amount(message)
            if amount is not None and amount > 0:
                logger.info(f"[MATCHER] Amount extracted: {amount}")
                return True

        # Get awaiting type config
        config = config_loader.get_awaiting_config(awaiting)
        if not config:
            return False

        # Check validation pattern (regex)
        if config.validation_pattern:
            if re.match(config.validation_pattern, message.strip()):
                return True

        # Check valid response intents via KeywordMatcher
        intent_keys = list(config.valid_response_intents)
        if org_id and intent_keys:
            matched = await KeywordMatcher.matches_any_of(
                self._db, org_id, message, intent_keys, "pharmacy"
            )
            return matched is not None

        return False

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

    def _get_organization_id(self, state: dict) -> UUID | None:
        """Extract organization_id from state."""
        org_id = state.get("organization_id")
        if org_id is None:
            return None
        if isinstance(org_id, UUID):
            return org_id
        try:
            return UUID(str(org_id))
        except (ValueError, TypeError):
            return None


__all__ = ["AwaitedInputMatcher"]
