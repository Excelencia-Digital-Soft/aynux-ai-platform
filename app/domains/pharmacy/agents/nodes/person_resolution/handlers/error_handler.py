"""Handler for error scenarios."""

from __future__ import annotations

import logging
import re
import traceback
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.domains.pharmacy.agents.nodes.identification_constants import (
    OUT_OF_SCOPE_INTENTS,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.base_handler import (
    PersonResolutionBaseHandler,
)
from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
from app.tasks import TaskRegistry

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.intent_analyzer import PharmacyIntentAnalyzer

logger = logging.getLogger(__name__)


class ErrorHandler(PersonResolutionBaseHandler):
    """
    Handler for error scenarios.

    Responsibilities:
    - Handle missing phone
    - Handle missing pharmacy
    - Handle general errors
    """

    def __init__(
        self,
        intent_analyzer: PharmacyIntentAnalyzer | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._intent_analyzer = intent_analyzer

    def _get_intent_analyzer(self) -> PharmacyIntentAnalyzer:
        """Get or create intent analyzer."""
        if self._intent_analyzer is None:
            from app.domains.pharmacy.agents.intent_analyzer import PharmacyIntentAnalyzer

            self._intent_analyzer = PharmacyIntentAnalyzer()
        return self._intent_analyzer

    def _get_organization_id_safe(self, state_dict: dict[str, Any]) -> UUID | None:
        """Extract organization_id from state safely."""
        org_id = state_dict.get("organization_id")
        if org_id is None:
            return None
        if isinstance(org_id, UUID):
            return org_id
        try:
            return UUID(str(org_id))
        except (ValueError, TypeError):
            return None

    async def handle_no_phone(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle case when no phone is available.

        Args:
            message: User message
            state_dict: Current state

        Returns:
            State updates
        """
        # PRIORITY CHECK: If we're already waiting for DNI and message looks like a DNI,
        # forward directly to PersonValidationNode instead of running intent analysis.
        # This fixes the bug where "2259863" was analyzed as intent and classified as out-of-scope.
        validation_step = state_dict.get("validation_step")
        if validation_step == "dni":
            dni_match = re.search(r"\b(\d{7,8})\b", message)
            if dni_match:
                logger.info(
                    f"[handle_no_phone] DNI detected in message during validation_step=dni: "
                    f"'{dni_match.group(1)}'. Forwarding to PersonValidationNode."
                )
                return {
                    **self._preserve_all(state_dict),
                    "validation_step": "dni",
                    "next_node": "person_validation_node",
                }

        org_id = self._get_organization_id_safe(state_dict)
        intent_result = await self._get_intent_analyzer().analyze(
            message,
            {"customer_identified": False},
            organization_id=org_id,
        )

        if intent_result.intent == "info_query":
            return {
                **self._preserve_all(state_dict),
                "intent": "info_query",
                "next_node": "router",
            }

        if intent_result.is_out_of_scope or intent_result.intent in OUT_OF_SCOPE_INTENTS:
            return {
                **self._preserve_all(state_dict),
                "intent": intent_result.intent,
                "is_out_of_scope": True,
                "next_node": "router",
            }

        # Route to validation without phone context
        response_content = await generate_response(
            state=state_dict,
            intent="request_dni_welcome",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_IDENTIFICATION_REQUEST_IDENTIFIER),
        )

        return {
            **self._preserve_all(state_dict),
            "messages": [{"role": "assistant", "content": response_content}],
            "validation_step": "dni",
            "next_node": "person_validation_node",
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }

    async def handle_no_pharmacy(
        self,
        message: str,  # noqa: ARG002
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle case when no pharmacy_id is available.

        Args:
            message: User message (unused)
            state_dict: Current state

        Returns:
            State updates with error
        """
        logger.error("No pharmacy_id in state - cannot proceed with resolution")

        response_content = await generate_response(
            state=state_dict,
            intent="no_pharmacy_error",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_ERROR_PHARMACY_NOT_FOUND),
        )

        return {
            **self._preserve_all(state_dict),
            "messages": [{"role": "assistant", "content": response_content}],
            "is_complete": True,
            "requires_human": True,
        }

    async def handle_error(
        self,
        error: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle processing error.

        Args:
            error: Error message
            state_dict: Current state

        Returns:
            State updates with error message
        """
        tb = traceback.format_exc()
        logger.error(f"Person resolution error: {error}")
        logger.error(f"Full traceback:\n{tb}")
        error_count = state_dict.get("error_count", 0) + 1

        if error_count >= state_dict.get("max_errors", 3):
            response_content = await generate_response(
                state=state_dict,
                intent="max_errors_reached",
                user_message="",
                current_task=await get_current_task(TaskRegistry.PHARMACY_ERROR_MULTIPLE_FAILURES),
            )
            return {
                **self._preserve_all(state_dict),
                "messages": [{"role": "assistant", "content": response_content}],
                "error_count": error_count,
                "is_complete": True,
                "requires_human": True,
            }

        response_content = await generate_response(
            state=state_dict,
            intent="generic_error",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_ERROR_RETRY),
        )
        return {
            **self._preserve_all(state_dict),
            "messages": [{"role": "assistant", "content": response_content}],
            "error_count": error_count,
        }


__all__ = ["ErrorHandler"]
