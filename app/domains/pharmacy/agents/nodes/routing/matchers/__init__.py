# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Routing matchers package.
#              Strategy implementations for matching message types.
# Tenant-Aware: Yes - matchers use configs per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Routing Matchers Package - Strategy implementations for message matching.

Each matcher implements the RoutingMatcher protocol to check if a message
matches a specific routing type (global keyword, button, menu, etc.).

Matchers are tried in priority order:
- 0: AwaitedInputMatcher (highest - protects awaited input)
- 100: GlobalKeywordMatcher (can interrupt flows)
- 50: ButtonMappingMatcher (WhatsApp interactive)
- 45: KnownListItemMatcher (fallback patterns)
- 40: MenuOptionMatcher (when in menu context)

Usage:
    from app.domains.pharmacy.agents.nodes.routing.matchers import (
        MatchContext,
        MatchResult,
        GlobalKeywordMatcher,
    )

    matcher = GlobalKeywordMatcher()
    ctx = MatchContext(message=msg, message_lower=msg.lower(), ...)
    result = await matcher.matches(ctx)
"""

from app.domains.pharmacy.agents.nodes.routing.matchers.awaited_input import (
    AwaitedInputMatcher,
)
from app.domains.pharmacy.agents.nodes.routing.matchers.base import (
    MatchContext,
    MatchResult,
    RoutingMatcher,
)
from app.domains.pharmacy.agents.nodes.routing.matchers.button_mapping import (
    ButtonMappingMatcher,
    KnownListItemMatcher,
)
from app.domains.pharmacy.agents.nodes.routing.matchers.global_keyword import (
    GlobalKeywordMatcher,
)
from app.domains.pharmacy.agents.nodes.routing.matchers.menu_option import (
    MenuOptionMatcher,
)

__all__ = [
    # Base protocol and types
    "MatchContext",
    "MatchResult",
    "RoutingMatcher",
    # Matcher implementations
    "AwaitedInputMatcher",
    "ButtonMappingMatcher",
    "GlobalKeywordMatcher",
    "KnownListItemMatcher",
    "MenuOptionMatcher",
]
