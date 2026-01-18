# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Router Supervisor - Database-driven routing orchestrator.
#              Uses Strategy Pattern for flexible, maintainable routing.
# Tenant-Aware: Yes - loads configs per organization_id.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Router Supervisor - Orchestrates priority-based routing using Strategy Pattern.

Single Responsibility: Coordinate matchers and handlers in priority order.

This is the refactored version of the original RouterSupervisor (~600 lines)
reduced to ~100 lines by extracting responsibilities into focused components.

Priority Order:
0. Protected awaiting input - valid responses bypass global keywords
1. Global keywords (priority=100) - interrupt (unless protected)
2. Button/List selection (priority=50) - WhatsApp interactive responses
3. Known list item patterns (priority=45) - fallback patterns
4. Menu options if in menu context (priority=40) - 1-6, 0 options
5. Awaiting specific input - non-protected responses
6. Intent analysis if not awaiting specific input

Usage:
    router = RouterSupervisor(db_session)
    result = await router.route(state)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from app.domains.pharmacy.agents.nodes.intent_route_resolver import IntentRouteResolver
from app.domains.pharmacy.agents.nodes.routing import (
    AuthChecker,
    AwaitedInputHandler,
    AwaitedInputMatcher,
    ButtonMappingMatcher,
    ButtonSelectionHandler,
    GlobalKeywordAmountHandler,
    GlobalKeywordHandler,
    GlobalKeywordMatcher,
    IntentOverrideHandler,
    KnownListItemHandler,
    KnownListItemMatcher,
    MatchContext,
    MenuOptionHandler,
    MenuOptionMatcher,
    RoutingConfigLoader,
)
from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


class RouterSupervisor:
    """
    Orchestrates priority-based routing using Strategy pattern.

    Single Responsibility: Coordinate matchers and handlers in priority order.

    This class has been refactored from ~600 lines to ~100 lines by extracting:
    - Config loading → RoutingConfigLoader
    - Auth checking → AuthChecker
    - Matching logic → *Matcher classes
    - Handling logic → *Handler classes
    """

    def __init__(self, db: "AsyncSession") -> None:
        """
        Initialize router with database session.

        Args:
            db: AsyncSession for database operations
        """
        self._db = db
        self._config_loader = RoutingConfigLoader(db)
        self._auth_checker = AuthChecker(self._config_loader)
        self._intent_resolver: IntentRouteResolver | None = None

        # Initialize matchers (ordered by priority)
        self._matchers = [
            AwaitedInputMatcher(db),   # Priority 0 (highest)
            GlobalKeywordMatcher(),     # Priority 100
            ButtonMappingMatcher(),     # Priority 50
            KnownListItemMatcher(),     # Priority 45
            MenuOptionMatcher(),        # Priority 40
        ]

        # Initialize handlers (keyed by handler_key from MatchResult)
        self._handlers: dict[str, Any] = {
            "global_keyword": GlobalKeywordHandler(self._auth_checker, self._config_loader),
            "global_keyword_amount": GlobalKeywordAmountHandler(),
            "button_selection": ButtonSelectionHandler(self._auth_checker, self._config_loader),
            "known_list_item": KnownListItemHandler(),
            "menu_option": MenuOptionHandler(self._auth_checker, self._config_loader),
            "awaited_input": AwaitedInputHandler(self._config_loader),
            "awaited_input_amount": AwaitedInputHandler(self._config_loader),
            "intent_override": IntentOverrideHandler(self._config_loader),
        }

    def _get_intent_resolver(self) -> IntentRouteResolver:
        """Get or create intent route resolver (lazy initialization)."""
        if self._intent_resolver is None:
            self._intent_resolver = IntentRouteResolver(self._db)
        return self._intent_resolver

    async def route(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Route incoming message to appropriate node.

        Args:
            state: Current conversation state

        Returns:
            State update dictionary with routing decision
        """
        # Load configs if not cached
        org_id = self._get_organization_id(state)
        await self._config_loader.load(org_id)

        # Extract message content
        message = MessageExtractor.extract_last_human_message(state) or ""
        if not message:
            return {"is_complete": True, "next_node": "__end__"}

        # Build match context
        ctx = MatchContext(
            message=message,
            message_lower=message.strip().lower(),
            state=dict(state),
            config_loader=self._config_loader,
            awaiting=state.get("awaiting_input"),
            current_intent=state.get("intent"),
        )

        # Try matchers in priority order
        for matcher in self._matchers:
            result = await matcher.matches(ctx)
            if result:
                handler = self._handlers.get(result.handler_key)
                if handler:
                    return handler.handle(result, dict(state))

        # Fallback: Non-protected awaited input (except menu_selection)
        if ctx.awaiting and ctx.awaiting != "menu_selection":
            handler = self._handlers["awaited_input"]
            from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchResult
            fallback_match = MatchResult(
                config=None,
                match_type="awaited_input",
                handler_key="awaited_input",
                metadata={"awaiting_type": ctx.awaiting},
            )
            return handler.handle(fallback_match, dict(state))

        # Final fallback: Intent analysis
        resolver = self._get_intent_resolver()
        return await resolver.resolve(message, state, org_id)

    def _get_organization_id(self, state: "PharmacyStateV2") -> UUID | None:
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


async def create_router_supervisor(db: "AsyncSession") -> RouterSupervisor:
    """
    Factory function to create a RouterSupervisor.

    Args:
        db: AsyncSession for database operations

    Returns:
        Configured RouterSupervisor instance
    """
    return RouterSupervisor(db)


# Node function for LangGraph integration
async def router_supervisor_node(
    state: "PharmacyStateV2",
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """
    LangGraph node function for router supervisor.

    This function is called by the LangGraph engine to route messages.
    It creates a RouterSupervisor instance and calls the route method.

    Args:
        state: Current conversation state
        config: Optional configuration (may contain db session)

    Returns:
        State updates from routing decision
    """
    from app.database.async_db import get_async_db_context

    # Get db from config or create new session
    db = config.get("db") if config else None

    if db:
        router = RouterSupervisor(db)
        return await router.route(state)
    else:
        async with get_async_db_context() as db:
            router = RouterSupervisor(db)
            return await router.route(state)
