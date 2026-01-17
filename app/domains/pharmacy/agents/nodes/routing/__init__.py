# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Routing package for RouterSupervisor refactoring.
#              Strategy Pattern implementation for flexible routing.
# Tenant-Aware: Yes - all components support multi-tenant routing.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Routing Package - Strategy Pattern implementation for RouterSupervisor.

This package contains the refactored routing logic split into focused components:

Components:
- config_loader: Centralized configuration loading
- auth_checker: Authentication requirement checking
- matchers/: Strategy implementations for matching message types
- handlers/: Route handlers for processing matched routes

Usage:
    from app.domains.pharmacy.agents.nodes.routing import (
        RoutingConfigLoader,
        AuthChecker,
        GlobalKeywordMatcher,
        GlobalKeywordHandler,
    )

    # Initialize components
    loader = RoutingConfigLoader(db)
    await loader.load(org_id, "pharmacy")

    checker = AuthChecker(loader)
    handler = GlobalKeywordHandler(checker, loader)
"""

from app.domains.pharmacy.agents.nodes.routing.auth_checker import AuthChecker
from app.domains.pharmacy.agents.nodes.routing.config_loader import RoutingConfigLoader
from app.domains.pharmacy.agents.nodes.routing.handlers import (
    AwaitedInputHandler,
    BaseRouteHandler,
    ButtonSelectionHandler,
    GlobalKeywordHandler,
    KnownListItemHandler,
    MenuOptionHandler,
    RouteHandler,
)
from app.domains.pharmacy.agents.nodes.routing.matchers import (
    AwaitedInputMatcher,
    ButtonMappingMatcher,
    GlobalKeywordMatcher,
    KnownListItemMatcher,
    MatchContext,
    MatchResult,
    MenuOptionMatcher,
    RoutingMatcher,
)

__all__ = [
    # Core components
    "AuthChecker",
    "RoutingConfigLoader",
    # Matcher protocol and context
    "MatchContext",
    "MatchResult",
    "RoutingMatcher",
    # Matcher implementations
    "AwaitedInputMatcher",
    "ButtonMappingMatcher",
    "GlobalKeywordMatcher",
    "KnownListItemMatcher",
    "MenuOptionMatcher",
    # Handler protocol
    "BaseRouteHandler",
    "RouteHandler",
    # Handler implementations
    "AwaitedInputHandler",
    "ButtonSelectionHandler",
    "GlobalKeywordHandler",
    "KnownListItemHandler",
    "MenuOptionHandler",
]
