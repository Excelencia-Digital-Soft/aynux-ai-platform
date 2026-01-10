"""Handler for name verification flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    MAX_IDENTIFICATION_RETRIES,
    NAME_MATCH_THRESHOLD,
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


class NameVerificationHandler(PersonResolutionBaseHandler):
    """
    Handler for name verification with fuzzy matching.

    Responsibilities:
    - Verify provided name against PLEX record
    - Calculate name similarity using Jaccard similarity
    - Signal completion or escalation
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
        Handle name verification with fuzzy matching.

        Args:
            message: User's name input
            state_dict: Current state

        Returns:
            State updates with verification result
        """
        service = self._get_identification_service()
        plex_customer = state_dict.get("plex_customer_to_confirm", {})
        expected_name = plex_customer.get("nombre", "")
        provided_name = message.strip()
        mismatch_count = state_dict.get("name_mismatch_count", 0)

        # Calculate similarity
        similarity = service.calculate_name_similarity(provided_name, expected_name)

        if similarity >= NAME_MATCH_THRESHOLD:
            # Name matches - signal completion
            return {
                "identification_complete": True,
                "plex_customer_verified": plex_customer,
            }

        # Name doesn't match
        mismatch_count += 1

        if mismatch_count >= MAX_IDENTIFICATION_RETRIES:
            # Signal escalation needed
            return {
                "name_verification_failed": True,
                "name_mismatch_count": mismatch_count,
            }

        # Ask to retry
        response_state = {
            **state_dict,
            "name_mismatch_count": mismatch_count,
            "max_retries": MAX_IDENTIFICATION_RETRIES,
        }

        response_content = await generate_response(
            state=response_state,
            intent="name_mismatch",
            user_message=message,
            current_task="El nombre no coincide. Pide que reintente con el nombre exacto.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_NAME,
            "name_mismatch_count": mismatch_count,
            "plex_customer_to_confirm": plex_customer,
        }


__all__ = ["NameVerificationHandler"]
