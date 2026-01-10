"""
Main Menu Node - Shows the pharmacy chatbot menu.

Implements CASO 2 from docs/pharmacy_flujo_mejorado_v2.md:
- Full menu (7 options) for new users or first interaction of day
- Reduced menu for returning users with debt

Menu Options:
1. Consultar deuda
2. Pagar deuda
3. Ver historial de pagos
4. Información de la farmacia
5. Cambiar de persona
6. Ayuda
0. Salir
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.agents.utils.db_helpers import generate_response

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domains.pharmacy.agents.utils.response_generator import (
        PharmacyResponseGenerator,
    )

logger = logging.getLogger(__name__)


# Menu option to intent mapping
MENU_OPTIONS = {
    "1": "debt_query",
    "2": "payment_link",
    "3": "payment_history",
    "4": "info_query",
    "5": "change_person",
    "6": "help",
    "0": "farewell",
}

# Reverse mapping for display
INTENT_TO_OPTION = {v: k for k, v in MENU_OPTIONS.items()}


class MainMenuNode(BaseAgent):
    """
    Shows the main menu or reduced menu based on user context.

    Logic:
    - First interaction of day: Show full menu with greeting
    - Returning user with debt: Show reduced menu with balance
    - Default: Show full menu

    The menu is purely informational - actual routing happens in the router
    based on user response to the menu options.
    """

    def __init__(
        self,
        db_session: AsyncSession | None = None,
        config: dict[str, Any] | None = None,
        response_generator: PharmacyResponseGenerator | None = None,
    ):
        """
        Initialize main menu node.

        Args:
            db_session: SQLAlchemy async session for DB access
            config: Node configuration
            response_generator: PharmacyResponseGenerator for LLM-driven responses
        """
        super().__init__("main_menu_node", config or {})
        self._db_session = db_session
        self._response_generator = response_generator

    def _get_response_generator(self) -> PharmacyResponseGenerator:
        """Get or create response generator."""
        if self._response_generator is None:
            from app.domains.pharmacy.agents.utils.response_generator import (
                get_response_generator,
            )

            self._response_generator = get_response_generator()
        return self._response_generator

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Show main menu based on user context.

        Args:
            message: User's message
            state_dict: Current pharmacy state

        Returns:
            Updated state with menu displayed
        """
        customer_name = state_dict.get("customer_name") or "Cliente"
        pharmacy_name = state_dict.get("pharmacy_name") or "la farmacia"
        total_debt = state_dict.get("total_debt")
        has_debt = state_dict.get("has_debt", False)
        show_reduced_menu = state_dict.get("show_reduced_menu", False)
        first_interaction_today = self._is_first_interaction_today(state_dict)

        updates: dict[str, Any] = {
            "current_menu": "main",
            "first_interaction_today": first_interaction_today,
            "last_interaction_date": datetime.now(UTC).strftime("%Y-%m-%d"),
        }

        # Determine which menu to show
        if show_reduced_menu and has_debt and total_debt:
            menu_response = await self._generate_reduced_menu(
                customer_name=customer_name,
                pharmacy_name=pharmacy_name,
                total_debt=total_debt,
                state_dict=state_dict,
            )
        else:
            menu_response = await self._generate_full_menu(
                customer_name=customer_name,
                pharmacy_name=pharmacy_name,
                first_interaction=first_interaction_today,
                state_dict=state_dict,
            )

        updates["response"] = menu_response
        return updates

    def _is_first_interaction_today(self, state_dict: dict[str, Any]) -> bool:
        """Check if this is the first interaction today."""
        last_date = state_dict.get("last_interaction_date")
        if not last_date:
            return True

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return last_date != today

    async def _generate_full_menu(
        self,
        customer_name: str,
        pharmacy_name: str,
        first_interaction: bool,
        state_dict: dict[str, Any],
    ) -> str:
        """
        Generate full menu with all options.

        Args:
            customer_name: Customer's name
            pharmacy_name: Pharmacy name
            first_interaction: True if first interaction today
            state_dict: Current state

        Returns:
            Formatted menu string
        """
        db_session = self._db_session
        org_id = state_dict.get("organization_id")

        if db_session and org_id:
            try:
                # Build state with required fields for generate_response
                menu_state = {
                    **state_dict,
                    "customer_name": customer_name,
                    "pharmacy_name": pharmacy_name,
                    "first_interaction": first_interaction,
                }
                response = await generate_response(
                    state=menu_state,
                    intent="main_menu",
                    user_message="menu",
                )
                return response
            except Exception as e:
                logger.warning(f"Failed to generate menu via LLM: {e}")

        # Fallback static menu
        greeting = f"Hola {customer_name} 👋" if first_interaction else f"¿En qué puedo ayudarte, {customer_name}?"

        return f"""🏥 *FARMACIA {pharmacy_name.upper()}*

{greeting}

¿En qué puedo ayudarte?

1️⃣ Consultar mi deuda
2️⃣ Pagar deuda
3️⃣ Ver historial de pagos
4️⃣ Información de la farmacia
5️⃣ Cambiar de persona
6️⃣ Ayuda
0️⃣ Salir

Escribe el número de tu opción o describe lo que necesitas."""

    async def _generate_reduced_menu(
        self,
        customer_name: str,
        pharmacy_name: str,
        total_debt: float,
        state_dict: dict[str, Any],
    ) -> str:
        """
        Generate reduced menu for returning users with debt.

        Args:
            customer_name: Customer's name
            pharmacy_name: Pharmacy name
            total_debt: Total debt amount
            state_dict: Current state

        Returns:
            Formatted reduced menu string
        """
        db_session = self._db_session
        org_id = state_dict.get("organization_id")

        if db_session and org_id:
            try:
                # Build state with required fields for generate_response
                menu_state = {
                    **state_dict,
                    "customer_name": customer_name,
                    "pharmacy_name": pharmacy_name,
                    "total_debt": total_debt,
                }
                response = await generate_response(
                    state=menu_state,
                    intent="reduced_menu",
                    user_message="menu",
                )
                return response
            except Exception as e:
                logger.warning(f"Failed to generate reduced menu via LLM: {e}")

        # Fallback static reduced menu
        debt_formatted = f"${total_debt:,.0f}".replace(",", ".")

        return f"""Hola {customer_name} 👋
Tu deuda actual: *{debt_formatted}*

1️⃣ Pagar  2️⃣ Detalles  3️⃣ Info  4️⃣ Menú completo

¿Qué deseas hacer?"""


def parse_menu_option(message: str) -> str | None:
    """
    Parse a menu option from user message.

    Args:
        message: User's message

    Returns:
        Intent string if valid option, None otherwise
    """
    message = message.strip()

    # Check for exact number match
    if message in MENU_OPTIONS:
        return MENU_OPTIONS[message]

    # Check for emoji numbers
    emoji_map = {
        "1️⃣": "1",
        "2️⃣": "2",
        "3️⃣": "3",
        "4️⃣": "4",
        "5️⃣": "5",
        "6️⃣": "6",
        "0️⃣": "0",
    }

    for emoji, num in emoji_map.items():
        if emoji in message:
            return MENU_OPTIONS.get(num)

    return None


def is_menu_navigation(message: str) -> bool:
    """
    Check if message is a menu navigation request.

    Args:
        message: User's message

    Returns:
        True if user is requesting menu
    """
    message_lower = message.lower().strip()
    menu_keywords = [
        "menu",
        "menú",
        "opciones",
        "ayuda",
        "inicio",
        "volver",
        "atrás",
        "atras",
    ]

    return any(kw in message_lower for kw in menu_keywords)


# Factory function for dependency injection
def create_main_menu_node(
    db_session: AsyncSession | None = None,
    config: dict[str, Any] | None = None,
) -> MainMenuNode:
    """
    Create MainMenuNode with dependencies.

    Args:
        db_session: SQLAlchemy async session
        config: Node configuration

    Returns:
        Configured MainMenuNode instance
    """
    return MainMenuNode(
        db_session=db_session,
        config=config,
    )


__all__ = [
    "MainMenuNode",
    "create_main_menu_node",
    "parse_menu_option",
    "is_menu_navigation",
    "MENU_OPTIONS",
    "INTENT_TO_OPTION",
]
