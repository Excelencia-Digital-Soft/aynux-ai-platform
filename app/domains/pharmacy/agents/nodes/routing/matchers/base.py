# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Base protocol for routing matchers.
#              Implements Strategy Pattern for flexible routing logic.
# Tenant-Aware: Yes - matchers receive org_id via state.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Routing Matcher Protocol - Base interface for all routing matchers.

Each matcher implements the Strategy Pattern to check if a message
matches a specific routing type (global keyword, button, menu, etc.).

Usage:
    class MyMatcher(RoutingMatcher):
        @property
        def priority(self) -> int:
            return 50  # Lower = higher priority

        async def matches(self, ctx) -> MatchResult | None:
            # Check if message matches
            return MatchResult(...) if matched else None
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from app.core.cache.routing_config_cache import RoutingConfigDTO
    from app.domains.pharmacy.agents.nodes.routing.config_loader import RoutingConfigLoader


@dataclass(frozen=True)
class MatchResult:
    """
    Result of a successful match.

    Attributes:
        config: Matched routing configuration (or None for non-config matches)
        match_type: Type of match (global_keyword, button_mapping, etc.)
        handler_key: Key to select the handler for this match
        metadata: Additional match-specific data
    """

    config: "RoutingConfigDTO | None"
    match_type: str
    handler_key: str
    metadata: dict[str, Any] | None = None


@dataclass
class MatchContext:
    """
    Context passed to matchers for evaluation.

    Provides all information needed to determine if a message matches.

    Attributes:
        message: Original user message
        message_lower: Lowercase, stripped message for case-insensitive matching
        state: Current conversation state
        config_loader: Loaded routing configurations
        awaiting: Current awaiting_input value (if any)
        current_intent: Current intent (if any)
    """

    message: str
    message_lower: str
    state: dict[str, Any]
    config_loader: "RoutingConfigLoader"
    awaiting: str | None
    current_intent: str | None


class RoutingMatcher(Protocol):
    """
    Protocol for routing matchers.

    Each matcher checks if a message matches a specific routing type.
    Matchers are tried in priority order (lower = higher priority).

    Implementing classes must:
    - Define a priority property (0 = highest)
    - Implement matches() to return MatchResult or None
    """

    @property
    def priority(self) -> int:
        """
        Priority level for this matcher (0 = highest priority).

        Standard priorities:
        - 0: Protected awaiting input (highest - bypass global keywords)
        - 100: Global keywords (interrupt most flows)
        - 50: Button/list selections (WhatsApp interactive)
        - 40: Menu options (when in menu context)
        """
        ...

    async def matches(self, ctx: MatchContext) -> MatchResult | None:
        """
        Check if message matches this routing type.

        Args:
            ctx: Match context with message, state, and configs

        Returns:
            MatchResult if matched, None otherwise
        """
        ...


__all__ = ["MatchContext", "MatchResult", "RoutingMatcher"]
