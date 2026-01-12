"""
Pharmacy Greeting Handler

Handles greeting messages using PharmacyResponseGenerator for LLM-driven responses.
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


class GreetingHandler(BasePharmacyHandler):
    """
    Handle greeting messages for pharmacy domain.

    Uses PharmacyResponseGenerator for LLM-driven natural responses
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

    async def handle(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle greeting message.

        Args:
            message: User greeting message
            state: Current state dictionary

        Returns:
            State updates with greeting response
        """
        state = state or {}

        # Use ResponseGenerator for LLM-driven greeting
        response_content = await generate_response(
            state=state,
            intent="greeting",
            user_message=message,
            current_task=await get_current_task(TaskRegistry.PHARMACY_GREETING_DEFAULT),
        )

        return self._format_state_update(
            message=response_content,
            intent_type="greeting",
            workflow_step="greeted",
            state=state,
        )
