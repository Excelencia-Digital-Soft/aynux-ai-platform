"""Handler for welcome message flow."""

from __future__ import annotations

from typing import Any

from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    STEP_AWAITING_IDENTIFIER,
    STEP_AWAITING_WELCOME,
    WELCOME_OPTIONS,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.base_handler import (
    PersonResolutionBaseHandler,
)
from app.domains.pharmacy.agents.utils.db_helpers import generate_response


class WelcomeFlowHandler(PersonResolutionBaseHandler):
    """
    Handler for new user welcome flow.

    Responsibilities:
    - Show welcome message with 3 options
    - Handle option selection (existing/new/info)
    """

    async def show_welcome_message(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Show welcome message for new users with 3 options.

        CASO 1 from pharmacy_flujo_mejorado_v2.md:
        1️⃣ Sí, soy cliente → STEP_AWAITING_IDENTIFIER
        2️⃣ No, quiero registrarme → Registration flow
        3️⃣ Solo quiero información general → Info flow (no auth)

        Args:
            state_dict: Current state

        Returns:
            State updates with welcome message
        """
        pharmacy_name = state_dict.get("pharmacy_name") or "la farmacia"

        response_state = {**state_dict, "pharmacy_name": pharmacy_name}

        response_content = await generate_response(
            state=response_state,
            intent="welcome_new_user",
            user_message="",
            current_task="Muestra mensaje de bienvenida con 3 opciones para usuario nuevo.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_WELCOME,
            "identification_retries": 0,
            **self._preserve_pharmacy_config(state_dict),
        }

    async def handle_response(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle user's response to welcome message (1/2/3).

        Args:
            message: User's response
            state_dict: Current state

        Returns:
            State updates routing to appropriate flow
        """
        message_clean = message.strip().lower()

        # Option 1: Existing client - ask for identifier
        if message_clean in WELCOME_OPTIONS["existing_client"]:
            return await self._ask_for_identifier(state_dict)

        # Option 2: New client - route to registration
        if message_clean in WELCOME_OPTIONS["new_client"]:
            return self._route_to_registration(state_dict)

        # Option 3: Just info - route to info flow (no auth required)
        if message_clean in WELCOME_OPTIONS["info_only"]:
            return {
                "identification_step": None,
                "pharmacy_intent_type": "info_query",
                "next_node": "router",
                **self._preserve_pharmacy_config(state_dict),
            }

        # Ambiguous response - ask again
        response_content = await generate_response(
            state=state_dict,
            intent="ambiguous_welcome_response",
            user_message=message,
            current_task="El usuario dio una respuesta no reconocida. Pide que elija 1, 2 o 3.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_WELCOME,
        }

    async def _ask_for_identifier(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ask user for identifier (DNI/client number).

        Args:
            state_dict: Current state

        Returns:
            State updates asking for identifier
        """
        response_content = await generate_response(
            state=state_dict,
            intent="request_identifier",
            user_message="",
            current_task="Solicita DNI, número de cliente o CUIT/CUIL para identificar al usuario.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_IDENTIFIER,
            "identification_retries": 0,
            **self._preserve_pharmacy_config(state_dict),
        }

    def _route_to_registration(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Route to customer registration flow.

        Args:
            state_dict: Current state

        Returns:
            State updates for registration
        """
        return {
            "identification_step": None,
            "awaiting_registration_data": True,
            "registration_step": "nombre",
            "next_node": "customer_registration_node",
            **self._preserve_pharmacy_config(state_dict),
        }


__all__ = ["WelcomeFlowHandler"]
