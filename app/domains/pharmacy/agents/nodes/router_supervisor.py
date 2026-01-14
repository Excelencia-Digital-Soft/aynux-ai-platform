"""
Router Supervisor - Database-driven routing with context switching.

This router implements the priority-based routing system described in the
refactoring plan. All routing rules are loaded from database via cache.

Priority Order:
1. Global keywords (priority=100) - ALWAYS interrupt any flow
2. Button/List selection IDs (priority=50) - WhatsApp interactive responses
3. Menu options if in menu context (priority=40) - 1-6, 0 options
4. Intent analysis if not awaiting specific input

Context Switching:
- Detects change of intention at any point
- Preserves previous_intent for potential resume
- Clears context when appropriate (cancelar, salir)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from app.core.cache.routing_config_cache import RoutingConfigDTO, routing_config_cache
from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


# Intent to node mapping (default fallbacks when target_node is None)
DEFAULT_INTENT_NODE_MAP: dict[str, str | None] = {
    "check_debt": "debt_manager",
    "debt_query": "debt_manager",
    "pay_full": "payment_processor",
    "pay_partial": "payment_processor",
    "payment_link": "payment_processor",
    "switch_account": "account_switcher",
    "change_person": "account_switcher",
    "select_account": "debt_manager",
    "info_query": "info_node",
    "help": "help_center_node",
    "farewell": "farewell_node",
    "show_menu": "main_menu_node",
    "go_back": "main_menu_node",
    "human_escalation": "human_escalation_node",
    "cancel_flow": "main_menu_node",
    "confirm_yes": None,  # Handled by current node
    "confirm_no": None,  # Handled by current node
    "own_debt": None,  # Handled by current node
    "other_debt": None,  # Handled by current node
    "add_new_person": "auth_plex",
    # V2 Flow intents (pharmacy_flujo_mejorado_v2.md)
    "pay_debt_menu": "debt_manager",  # PAY_DEBT_MENU: shows debt summary + payment options
    "view_invoice_detail": "debt_manager",  # INVOICE_DETAIL: shows invoice detail
}

# Intents that require authentication
AUTH_REQUIRED_INTENTS = frozenset(
    {
        "check_debt",
        "debt_query",
        "pay_full",
        "pay_partial",
        "payment_link",
        "payment_history",
        "switch_account",
        "change_person",
    }
)


class RouterSupervisor:
    """
    Database-driven router supervisor with context switching support.

    Loads routing rules from database via multi-tier cache and applies
    them in priority order. Handles context switching for global keywords.

    Usage:
        router = RouterSupervisor(db_session)
        result = await router.route(state)
        # result contains intent, next_node, and state updates
    """

    def __init__(self, db: "AsyncSession") -> None:
        """
        Initialize router with database session.

        Args:
            db: AsyncSession for database operations (used by cache)
        """
        self._db = db
        self._configs: dict[str, list[RoutingConfigDTO]] | None = None

    async def _load_configs(self, organization_id: UUID | None) -> None:
        """Load routing configurations from cache."""
        if self._configs is None:
            self._configs = await routing_config_cache.get_configs(self._db, organization_id, "pharmacy")
            logger.debug(
                f"Loaded routing configs for org {organization_id}: "
                f"{sum(len(v) for v in self._configs.values())} total"
            )

    async def route(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Route incoming message to appropriate node.

        Priority order (from DB config priority field):
        1. Global keywords (priority=100) - ALWAYS interrupt
        2. Button/List selection (priority=50) - WhatsApp interactive
        3. Menu options if in menu context (priority=40)
        4. Intent analysis if not awaiting specific input

        Args:
            state: Current conversation state

        Returns:
            State update dictionary with:
            - intent: Detected intent
            - previous_intent: Previous intent (for context switching)
            - next_node: Node to route to
            - awaiting_input: Cleared if routing to new flow
            - Additional state updates as needed
        """
        # Load configs if not cached
        org_id = self._get_organization_id(state)
        await self._load_configs(org_id)

        # Extract message content
        message = self._extract_last_message(state)
        if not message:
            return {
                "is_complete": True,
                "next_node": "__end__",
            }

        message_lower = message.strip().lower()
        current_intent = state.get("intent")

        # === PRIORITY 1: Global Keywords ===
        global_config = self._find_global_keyword(message_lower)
        if global_config:
            logger.info(f"Global keyword detected: {global_config.trigger_value}")
            return self._handle_global_keyword(global_config, state, current_intent)

        # === PRIORITY 2: Button/List Selection ===
        # Check if message looks like a button ID
        button_config = self._find_button_mapping(message)
        if button_config:
            logger.info(f"Button mapping detected: {button_config.trigger_value}")
            return self._handle_button_selection(button_config, state, current_intent)

        # === PRIORITY 3: Menu Options (only if in menu context) ===
        if state.get("awaiting_input") == "menu_selection":
            menu_config = self._find_menu_option(message_lower)
            if menu_config:
                logger.info(f"Menu option detected: {menu_config.trigger_value}")
                return self._handle_menu_option(menu_config, state, current_intent)

        # === PRIORITY 4: Awaiting Specific Input ===
        awaiting = state.get("awaiting_input")
        if awaiting:
            return self._handle_awaited_input(awaiting, message, state)

        # === PRIORITY 5: Intent Analysis ===
        # TODO: Integrate with LLM-based intent analyzer
        # For now, return to debt manager as default for authenticated users
        if state.get("is_authenticated"):
            return {
                "intent": "check_debt",
                "next_node": "debt_manager",
            }
        else:
            return {
                "intent": "greeting",
                "next_node": "auth_plex",
            }

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

    def _extract_last_message(self, state: "PharmacyStateV2") -> str:
        """Extract the last human message from state."""
        result = MessageExtractor.extract_last_human_message(state)
        return result if result else ""

    def _find_global_keyword(self, message: str) -> RoutingConfigDTO | None:
        """Find matching global keyword config."""
        if not self._configs:
            return None

        for config in self._configs.get("global_keyword", []):
            trigger = config.trigger_value.lower()
            if message == trigger or message.startswith(trigger + " "):
                return config

            # Check aliases
            if config.metadata and "aliases" in config.metadata:
                for alias in config.metadata["aliases"]:
                    if message == alias.lower() or message.startswith(alias.lower() + " "):
                        return config

        return None

    def _find_button_mapping(self, message: str) -> RoutingConfigDTO | None:
        """Find matching button mapping config."""
        if not self._configs:
            return None

        # Button IDs are usually exact matches
        message_clean = message.strip()

        for config in self._configs.get("button_mapping", []):
            if config.trigger_value == message_clean:
                return config

        return None

    def _find_menu_option(self, message: str) -> RoutingConfigDTO | None:
        """Find matching menu option config."""
        if not self._configs:
            return None

        # Menu options are single characters (1-6, 0)
        message_clean = message.strip()

        # Handle emoji numbers
        emoji_map = {
            "1\ufe0f\u20e3": "1",
            "2\ufe0f\u20e3": "2",
            "3\ufe0f\u20e3": "3",
            "4\ufe0f\u20e3": "4",
            "5\ufe0f\u20e3": "5",
            "6\ufe0f\u20e3": "6",
            "0\ufe0f\u20e3": "0",
        }
        if message_clean in emoji_map:
            message_clean = emoji_map[message_clean]

        for config in self._configs.get("menu_option", []):
            if config.trigger_value == message_clean:
                return config

        return None

    def _handle_global_keyword(
        self,
        config: RoutingConfigDTO,
        state: "PharmacyStateV2",
        current_intent: str | None,
    ) -> dict[str, Any]:
        """Handle global keyword routing."""
        updates: dict[str, Any] = {
            "intent": config.target_intent,
            "previous_intent": current_intent,
            "awaiting_input": None,  # Clear any pending input
            "next_node": config.target_node or DEFAULT_INTENT_NODE_MAP.get(config.target_intent, "main_menu_node"),
        }

        # Handle context clearing
        if config.clears_context:
            updates.update(
                {
                    "awaiting_payment_confirmation": False,
                    "awaiting_account_selection": False,
                }
            )

        return updates

    def _handle_button_selection(
        self,
        config: RoutingConfigDTO,
        state: "PharmacyStateV2",
        current_intent: str | None,
    ) -> dict[str, Any]:
        """Handle button selection routing."""
        # Check if auth required
        if config.requires_auth and not state.get("is_authenticated"):
            return {
                "intent": config.target_intent,
                "previous_intent": current_intent,
                "next_node": "auth_plex",
                "awaiting_input": None,
            }

        target_node = config.target_node or DEFAULT_INTENT_NODE_MAP.get(config.target_intent)

        # For confirmation buttons, don't change node - let current node handle
        if config.target_intent in ("confirm_yes", "confirm_no", "own_debt", "other_debt"):
            return {
                "intent": config.target_intent,
                "previous_intent": current_intent,
            }

        return {
            "intent": config.target_intent,
            "previous_intent": current_intent,
            "awaiting_input": None,
            "next_node": target_node,
        }

    def _handle_menu_option(
        self,
        config: RoutingConfigDTO,
        state: "PharmacyStateV2",
        current_intent: str | None,
    ) -> dict[str, Any]:
        """Handle menu option routing."""
        # Check if auth required
        if config.requires_auth and not state.get("is_authenticated"):
            return {
                "intent": config.target_intent,
                "previous_intent": current_intent,
                "next_node": "auth_plex",
                "awaiting_input": None,
            }

        target_node = config.target_node or DEFAULT_INTENT_NODE_MAP.get(config.target_intent, "debt_manager")

        return {
            "intent": config.target_intent,
            "previous_intent": current_intent,
            "awaiting_input": None,  # Clear menu context
            "next_node": target_node,
        }

    def _handle_awaited_input(
        self,
        awaiting: str,
        message: str,
        state: "PharmacyStateV2",
    ) -> dict[str, Any]:
        """
        Handle input when we're waiting for specific data.

        The awaiting_input field tells us what kind of input we expect.
        We pass the input to the appropriate handler node.
        """
        # Map awaiting types to nodes that handle them
        awaiting_node_map = {
            "dni": "auth_plex",
            "name": "auth_plex",
            "amount": "payment_processor",
            "payment_confirmation": "payment_processor",
            "account_selection": "account_switcher",
            "own_or_other": "account_switcher",
            "menu_selection": "main_menu_node",
            # V2 Flow awaiting types
            "debt_action": "debt_manager",  # SHOW_DEBT 4-option menu
            "pay_debt_action": "debt_manager",  # PAY_DEBT_MENU 3-option menu
            "invoice_detail_action": "debt_manager",  # INVOICE_DETAIL 3-option menu
        }

        node = awaiting_node_map.get(awaiting, "router")

        return {
            "next_node": node,
            # Don't clear awaiting_input - let the handler node do that
        }

    def _requires_auth(self, intent: str) -> bool:
        """Check if intent requires authentication."""
        return intent in AUTH_REQUIRED_INTENTS


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
