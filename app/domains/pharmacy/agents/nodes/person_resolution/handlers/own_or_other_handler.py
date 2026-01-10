"""Handler for own vs other debt question."""

from __future__ import annotations

from typing import Any

from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    OTHER_INDICATORS,
    OWN_INDICATORS,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.base_handler import (
    PersonResolutionBaseHandler,
)
from app.domains.pharmacy.agents.utils.db_helpers import generate_response


class OwnOrOtherHandler(PersonResolutionBaseHandler):
    """
    Handler for own vs other's debt question.

    Responsibilities:
    - Ask if user is querying own debt or someone else's
    - Handle response and route accordingly
    """

    async def ask(
        self,
        plex_customer: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ask user if querying own debt or someone else's.

        Args:
            plex_customer: PLEX customer dict
            state_dict: Current state

        Returns:
            State updates with question
        """
        customer_name = plex_customer.get("nombre", "")

        response_state = {**state_dict, "customer_name": customer_name}

        response_content = await generate_response(
            state=response_state,
            intent="ask_own_or_other",
            user_message="",
            current_task="Pregunta si el cliente desea consultar su propia deuda o la de otra persona.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "awaiting_own_or_other": True,
            "self_plex_customer": plex_customer,
            **self._preserve_pharmacy_config(state_dict),
        }

    async def handle_response(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle user response to own vs other question.

        Args:
            message: User's response
            state_dict: Current state

        Returns:
            State updates with decision
        """
        message_lower = message.lower().strip()

        is_own = any(ind in message_lower for ind in OWN_INDICATORS)
        is_other = any(ind in message_lower for ind in OTHER_INDICATORS)

        if is_own and not is_other:
            return {
                "decision": "own",
                "self_plex_customer": state_dict.get("self_plex_customer"),
            }

        if is_other and not is_own:
            return {
                "decision": "other",
                "is_querying_for_other": True,
            }

        # Ambiguous response
        response_content = await generate_response(
            state=state_dict,
            intent="ambiguous_own_other",
            user_message=message,
            current_task="El usuario dio una respuesta ambigua. Pide clarificación.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "awaiting_own_or_other": True,
            "self_plex_customer": state_dict.get("self_plex_customer"),
        }


__all__ = ["OwnOrOtherHandler"]
