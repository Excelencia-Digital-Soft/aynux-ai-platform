# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Menu option matcher for routing.
#              Matches menu selections (1-6, 0) with emoji support.
# Tenant-Aware: Yes - uses configs loaded per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Menu Option Matcher - Matches menu options from database config.

Handles menu selections when user is in menu context (awaiting_input == "menu_selection").
Supports both numeric (1-6, 0) and emoji number inputs.

Usage:
    matcher = MenuOptionMatcher()
    result = await matcher.matches(ctx)
    if result:
        # Handle menu option match
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchResult

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchContext

logger = logging.getLogger(__name__)


# Emoji number mappings (keycap emojis)
EMOJI_MAP: dict[str, str] = {
    "1\ufe0f\u20e3": "1",
    "2\ufe0f\u20e3": "2",
    "3\ufe0f\u20e3": "3",
    "4\ufe0f\u20e3": "4",
    "5\ufe0f\u20e3": "5",
    "6\ufe0f\u20e3": "6",
    "0\ufe0f\u20e3": "0",
}


class MenuOptionMatcher:
    """
    Matches menu options from database configuration.

    Single Responsibility: Check if message matches a menu option.

    Priority: 40 (after buttons, only when in menu context)

    Menu options:
    - Only active when awaiting_input == "menu_selection"
    - Matches single characters (1-6, 0)
    - Converts emoji numbers to regular numbers
    """

    priority = 40

    async def matches(self, ctx: "MatchContext") -> MatchResult | None:
        """
        Check if message matches a menu option.

        Only active when in menu context (awaiting_input == "menu_selection").

        Args:
            ctx: Match context with message, state, and configs

        Returns:
            MatchResult if matched, None otherwise
        """
        # Only check menu options when in menu context
        if ctx.awaiting != "menu_selection":
            return None

        configs = ctx.config_loader.get_configs_by_type("menu_option")
        if not configs:
            return None

        # Normalize message (handle emoji numbers)
        message_clean = ctx.message.strip()
        message_clean = EMOJI_MAP.get(message_clean, message_clean)

        # Find matching config
        for config in configs:
            if config.trigger_value == message_clean:
                logger.info(f"[MATCHER] Menu option matched: {config.trigger_value}")
                return MatchResult(
                    config=config,
                    match_type="menu_option",
                    handler_key="menu_option",
                )

        return None


__all__ = ["MenuOptionMatcher"]
