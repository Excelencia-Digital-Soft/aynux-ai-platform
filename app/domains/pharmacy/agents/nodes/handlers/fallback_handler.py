"""
Pharmacy Fallback Handler

Handles unknown intents, errors, cancellations, and out-of-scope messages.
Uses PharmacyResponseGenerator for LLM-driven responses.
"""

from __future__ import annotations

from typing import Any

from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
from app.tasks import TaskRegistry
from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
    get_response_generator,
)

from .base_handler import BasePharmacyHandler


class FallbackHandler(BasePharmacyHandler):
    """
    Handle fallback scenarios for pharmacy domain.

    Handles:
    - Unknown/unrecognized intents
    - Out-of-scope messages
    - Processing errors
    - User cancellations

    Uses PharmacyResponseGenerator for LLM-driven responses
    with automatic fallback to templates.
    """

    def __init__(
        self,
        response_generator: PharmacyResponseGenerator | None = None,
        **kwargs: Any,
    ):
        """Initialize with optional response generator."""
        super().__init__(**kwargs)
        self._response_generator = response_generator

    def _get_response_generator(self) -> PharmacyResponseGenerator:
        """Get or create response generator."""
        if self._response_generator is None:
            self._response_generator = get_response_generator()
        return self._response_generator

    async def handle_unknown(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle unknown/out-of-scope message.

        Args:
            message: Original user message
            state: Current state dictionary

        Returns:
            State updates with fallback response
        """
        state = state or {}

        response_content = await generate_response(
            state=state,
            intent="unknown",
            user_message=message,
            current_task=await get_current_task(TaskRegistry.PHARMACY_FALLBACK_DEFAULT),
        )

        self.logger.info(f"Handling unknown intent for message: '{message[:30]}...'")

        return self._format_state_update(
            message=response_content,
            intent_type="unknown",
            workflow_step="fallback",
            state=state,
            is_out_of_scope=True,
        )

    async def handle_out_of_scope(
        self,
        message: str,
        suggested_response: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle message that is clearly out of scope.

        Args:
            message: Original user message
            suggested_response: Optional suggested response from intent analyzer
            state: Current state dictionary

        Returns:
            State updates with out-of-scope response
        """
        state = state or {}

        if suggested_response:
            response_content = suggested_response
        else:
            response_content = await generate_response(
                state=state,
                intent="out_of_scope",
                user_message=message,
                current_task=await get_current_task(TaskRegistry.PHARMACY_FALLBACK_OUT_OF_SCOPE),
            )
            response_content = response_content

        self.logger.info(f"Out of scope message: '{message[:30]}...'")

        return self._format_state_update(
            message=response_content,
            intent_type="out_of_scope",
            workflow_step="fallback",
            state=state,
            is_out_of_scope=True,
        )

    async def handle_error(
        self,
        error: str | Exception,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle processing error gracefully.
        Uses critical template for consistency.

        Args:
            error: Error message or exception
            state: Current state dictionary

        Returns:
            State updates with error response
        """
        state = state or {}

        response_content = await self._generate_response(
            intent="system_error",
            state=state,
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_ERROR_TECHNICAL),
        )

        self.logger.error(f"Pharmacy error: {error}")

        return self._format_state_update(
            message=response_content,
            intent_type="error",
            workflow_step="error",
            state=state,
            error_count=state.get("error_count", 0) + 1,
        )

    async def handle_cancelled(
        self,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle user cancellation/rejection.

        Args:
            state: Current state dictionary

        Returns:
            State updates with cancellation response
        """
        state = state or {}

        response_content = await generate_response(
            state=state,
            intent="cancelled",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_FALLBACK_CANCELLATION),
        )

        return self._format_state_update(
            message=response_content,
            intent_type="cancelled",
            workflow_step="cancelled",
            state=state,
            is_complete=True,
            awaiting_confirmation=False,
            debt_status="cancelled",
        )

    async def handle_farewell(
        self,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle farewell/goodbye message.

        Args:
            state: Current state dictionary

        Returns:
            State updates with farewell response
        """
        state = state or {}

        response_content = await generate_response(
            state=state,
            intent="farewell",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_FALLBACK_FAREWELL),
        )

        return self._format_state_update(
            message=response_content,
            intent_type="farewell",
            workflow_step="farewell",
            state=state,
            is_complete=True,
        )

    async def handle_thanks(
        self,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle thanks/gratitude message.

        Args:
            state: Current state dictionary

        Returns:
            State updates with thanks response
        """
        state = state or {}

        response_content = await generate_response(
            state=state,
            intent="thanks",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_FALLBACK_THANKS),
        )

        return self._format_state_update(
            message=response_content,
            intent_type="thanks",
            workflow_step="thanks",
            state=state,
            is_complete=False,  # Allow continued conversation
        )
