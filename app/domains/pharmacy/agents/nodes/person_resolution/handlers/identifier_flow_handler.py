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
from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
from app.tasks import TaskRegistry

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
        If found and name provided → verify directly
        If found without name → STEP_NAME (ask for name)
        If not found → retry or escalate

        Args:
            message: User's identifier input (may include name)
            state_dict: Current state

        Returns:
            State updates
        """
        self.logger.info(f"[IDENT] handle() called with message='{message[:50]}...'")

        service = self._get_identification_service()
        identifier = service.normalize_identifier(message)
        retries = state_dict.get("identification_retries", 0)

        self.logger.info(f"[IDENT] normalized identifier={identifier}, retries={retries}")

        if not identifier:
            # Invalid format
            response_content = await generate_response(
                state=state_dict,
                intent="invalid_identifier_format",
                user_message=message,
                current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_IDENTIFIER_INVALID),
            )
            return {
                **self._preserve_all(state_dict),
                "messages": [{"role": "assistant", "content": response_content}],
                "identification_step": STEP_AWAITING_IDENTIFIER,
            }

        # Extract name if provided alongside identifier
        # E.g., "2259863 Pedrozo Adela" → identifier="2259863", name="Pedrozo Adela"
        provided_name = self._extract_name_from_message(message, identifier)
        self.logger.info(f"[IDENT] extracted provided_name='{provided_name}'")

        # Search PLEX
        plex_customer = await service.search_by_identifier(identifier)
        self.logger.info(
            f"[IDENT] plex_customer found={plex_customer is not None}, "
            f"nombre={plex_customer.get('nombre') if plex_customer else 'N/A'}"
        )

        if plex_customer:
            # If name was provided, try to verify directly
            if provided_name:
                expected_name = plex_customer.get("nombre", "")
                from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
                    NAME_MATCH_THRESHOLD,
                )

                similarity = service.calculate_name_similarity(
                    provided_name, expected_name
                )
                self.logger.info(
                    f"[IDENT] name verification: provided='{provided_name}', "
                    f"expected='{expected_name}', similarity={similarity:.2f}, "
                    f"threshold={NAME_MATCH_THRESHOLD}"
                )

                if similarity >= NAME_MATCH_THRESHOLD:
                    # Name matches - complete identification directly
                    return {
                        **self._preserve_all(state_dict),
                        "identification_complete": True,
                        "plex_customer_verified": plex_customer,
                        "identification_step": STEP_NAME,
                        "plex_customer_to_confirm": plex_customer,
                    }

            # Name not provided or doesn't match - ask for verification
            return await self._ask_for_name_verification(plex_customer, state_dict)

        # Not found - increment retries
        retries += 1

        if retries >= MAX_IDENTIFICATION_RETRIES:
            # Signal escalation needed
            return {
                **self._preserve_all(state_dict),
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
            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_IDENTIFIER_NOT_FOUND),
        )

        return {
            **self._preserve_all(state_dict),
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_IDENTIFIER,
            "identification_retries": retries,
        }

    def _extract_name_from_message(
        self,
        message: str,
        identifier: str,
    ) -> str | None:
        """
        Extract name from message if provided alongside identifier.

        Handles cases like:
        - "2259863 Pedrozo Adela" → "Pedrozo Adela"
        - "Adela Pedrozo 2259863" → "Adela Pedrozo"
        - "2259863" → None

        Args:
            message: Original user message
            identifier: Extracted identifier (DNI/client number)

        Returns:
            Extracted name or None if only identifier was provided
        """
        import re

        # Remove the identifier from the message
        # Handle identifier at start, end, or middle of message
        remaining = message.strip()

        # Remove identifier pattern (may have spaces/dashes around it)
        remaining = re.sub(rf"\b{re.escape(identifier)}\b", " ", remaining)

        # Clean up extra whitespace
        remaining = " ".join(remaining.split()).strip()

        # If something remains and it looks like a name (has letters), return it
        if remaining and re.search(r"[a-záéíóúñ]", remaining, re.IGNORECASE):
            # Must have at least 2 characters to be a valid name part
            if len(remaining) >= 2:
                return remaining

        return None

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
            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_NAME_VERIFICATION),
        )

        return {
            **self._preserve_all(state_dict),
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_NAME,
            "plex_customer_to_confirm": plex_customer,
            "name_mismatch_count": 0,
        }


__all__ = ["IdentifierFlowHandler"]
