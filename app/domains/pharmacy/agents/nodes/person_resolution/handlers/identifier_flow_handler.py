"""Handler for identifier input flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    MAX_IDENTIFICATION_RETRIES,
    STEP_AWAITING_IDENTIFIER,
    STEP_NAME,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.base_handler import (
    PersonResolutionBaseHandler,
)
from app.domains.pharmacy.agents.utils.db_helpers import generate_response

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.person_resolution.services.person_identification_service import (
        PersonIdentificationService,
    )


class IdentifierFlowHandler(PersonResolutionBaseHandler):
    """
    Handler for identifier input flow.

    Responsibilities:
    - Handle DNI/client number input
    - Validate identifier format
    - Search PLEX and transition to name verification
    """

    def __init__(
        self,
        identification_service: PersonIdentificationService | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._identification_service = identification_service

    def _get_identification_service(self) -> PersonIdentificationService:
        """Get or create identification service."""
        if self._identification_service is None:
            from app.domains.pharmacy.agents.nodes.person_resolution.services.person_identification_service import (
                PersonIdentificationService,
            )

            self._identification_service = PersonIdentificationService()
        return self._identification_service

    async def handle(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle identifier input (DNI/client number).

        Search PLEX for customer matching the identifier.
        If found → STEP_NAME (name verification)
        If not found → retry or escalate

        Args:
            message: User's identifier input
            state_dict: Current state

        Returns:
            State updates
        """
        service = self._get_identification_service()
        identifier = service.normalize_identifier(message)
        retries = state_dict.get("identification_retries", 0)

        if not identifier:
            # Invalid format
            response_content = await generate_response(
                state=state_dict,
                intent="invalid_identifier_format",
                user_message=message,
                current_task="El formato del identificador no es válido. Pide que reintente.",
            )
            return {
                "messages": [{"role": "assistant", "content": response_content}],
                "identification_step": STEP_AWAITING_IDENTIFIER,
            }

        # Search PLEX
        plex_customer = await service.search_by_identifier(identifier)

        if plex_customer:
            return await self._ask_for_name_verification(plex_customer, state_dict)

        # Not found - increment retries
        retries += 1

        if retries >= MAX_IDENTIFICATION_RETRIES:
            # Signal escalation needed
            return {
                "identification_failed": True,
                "identification_retries": retries,
            }

        # Ask to retry
        response_state = {
            **state_dict,
            "identification_retries": retries,
            "max_retries": MAX_IDENTIFICATION_RETRIES,
        }

        response_content = await generate_response(
            state=response_state,
            intent="identifier_not_found",
            user_message=message,
            current_task="No se encontró cliente con ese dato. Ofrece reintentar, registrarse o contactar.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_IDENTIFIER,
            "identification_retries": retries,
        }

    async def _ask_for_name_verification(
        self,
        plex_customer: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ask user to verify their name.

        Args:
            plex_customer: PLEX customer found
            state_dict: Current state

        Returns:
            State updates asking for name verification
        """
        response_content = await generate_response(
            state=state_dict,
            intent="request_name_verification",
            user_message="",
            current_task="Pide que ingrese su nombre completo para verificar identidad.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_NAME,
            "plex_customer_to_confirm": plex_customer,
            "name_mismatch_count": 0,
            **self._preserve_pharmacy_config(state_dict),
        }


__all__ = ["IdentifierFlowHandler"]
