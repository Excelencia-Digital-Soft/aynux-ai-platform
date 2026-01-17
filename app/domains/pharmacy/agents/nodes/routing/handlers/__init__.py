# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Route handlers package.
#              Strategy implementations for processing matched routes.
# Tenant-Aware: Yes - handlers use configs per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Route Handlers Package - Strategy implementations for route processing.

Each handler processes a matched route and returns state updates.
Handlers are selected based on the handler_key from MatchResult.

Handler mapping:
- "global_keyword": GlobalKeywordHandler
- "button_selection": ButtonSelectionHandler
- "known_list_item": KnownListItemHandler
- "menu_option": MenuOptionHandler
- "awaited_input": AwaitedInputHandler
- "awaited_input_amount": AwaitedInputHandler (special amount handling)

Usage:
    from app.domains.pharmacy.agents.nodes.routing.handlers import (
        GlobalKeywordHandler,
        AuthChecker,
    )

    handler = GlobalKeywordHandler(auth_checker, config_loader)
    result = handler.handle(match, state)
"""

from app.domains.pharmacy.agents.nodes.routing.handlers.awaited_input import (
    AwaitedInputHandler,
)
from app.domains.pharmacy.agents.nodes.routing.handlers.base import (
    BaseRouteHandler,
    RouteHandler,
)
from app.domains.pharmacy.agents.nodes.routing.handlers.button_selection import (
    ButtonSelectionHandler,
    KnownListItemHandler,
)
from app.domains.pharmacy.agents.nodes.routing.handlers.global_keyword import (
    GlobalKeywordHandler,
)
from app.domains.pharmacy.agents.nodes.routing.handlers.menu_option import (
    MenuOptionHandler,
)

__all__ = [
    # Base protocol and class
    "BaseRouteHandler",
    "RouteHandler",
    # Handler implementations
    "AwaitedInputHandler",
    "ButtonSelectionHandler",
    "GlobalKeywordHandler",
    "KnownListItemHandler",
    "MenuOptionHandler",
]
