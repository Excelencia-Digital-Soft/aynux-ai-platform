"""Handler for escalation to human support."""

from __future__ import annotations

from typing import Any

from app.domains.pharmacy.agents.nodes.person_resolution.handlers.base_handler import (
    PersonResolutionBaseHandler,
)
from app.domains.pharmacy.agents.utils.db_helpers import generate_response


class EscalationHandler(PersonResolutionBaseHandler):
    """
    Handler for escalation to human support.

    Responsibilities:
    - Escalate identification failures
    - Escalate name verification failures
    """

    async def escalate_identification_failure(
        self,
        state_dict: dict[str, Any],
        retries: int,
    ) -> dict[str, Any]:
        """
        Escalate when identification fails after max retries.

        Args:
            state_dict: Current state
            retries: Number of failed attempts

        Returns:
            State updates with escalation message
        """
        response_state = {
            **state_dict,
            "identification_retries": retries,
        }

        response_content = await generate_response(
            state=response_state,
            intent="identification_escalation",
            user_message="",
            current_task="No se pudo identificar después de varios intentos. Sugiere contactar farmacia.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": None,
            "requires_human": True,
            "escalation_reason": "identification_failed",
            **self._preserve_pharmacy_config(state_dict),
        }

    async def escalate_name_verification_failure(
        self,
        state_dict: dict[str, Any],
        mismatch_count: int,
    ) -> dict[str, Any]:
        """
        Escalate when name verification fails after max retries.

        Args:
            state_dict: Current state
            mismatch_count: Number of failed attempts

        Returns:
            State updates with escalation message
        """
        response_state = {
            **state_dict,
            "name_mismatch_count": mismatch_count,
        }

        response_content = await generate_response(
            state=response_state,
            intent="name_verification_escalation",
            user_message="",
            current_task="No se pudo verificar identidad. Sugiere contactar farmacia.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": None,
            "plex_customer_to_confirm": None,
            "requires_human": True,
            "escalation_reason": "name_verification_failed",
            **self._preserve_pharmacy_config(state_dict),
        }


__all__ = ["EscalationHandler"]
