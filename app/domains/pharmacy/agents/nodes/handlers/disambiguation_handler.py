"""
Disambiguation Handler

Handles the disambiguation flow when multiple customers match.
Single responsibility: disambiguation selection and response formatting.
Uses LLM-driven ResponseGenerator for natural language responses.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler
from app.domains.pharmacy.agents.utils.greeting_manager import GreetingManager
from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
)
from app.domains.pharmacy.domain.entities.plex_customer import PlexCustomer

logger = logging.getLogger(__name__)


class DisambiguationHandler(BasePharmacyHandler):
    """
    Handler for customer disambiguation flow.

    Single responsibility: Handle user selection from multiple
    customer matches and format disambiguation messages.
    """

    def __init__(
        self,
        response_generator: PharmacyResponseGenerator | None = None,
        greeting_manager: GreetingManager | None = None,
    ):
        """
        Initialize disambiguation handler.

        Args:
            response_generator: ResponseGenerator for LLM-driven responses
            greeting_manager: GreetingManager for greeting state
        """
        super().__init__(response_generator)
        self._greeting_manager = greeting_manager or GreetingManager()

    async def handle_selection(
        self,
        message: str,
        candidates_data: list[dict[str, Any]],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle user's disambiguation selection.

        Args:
            message: User message with selection
            candidates_data: List of candidate customer dictionaries
            state: Current state dictionary

        Returns:
            State update with selection result or error
        """
        if not candidates_data:
            logger.warning("No disambiguation candidates in state")
            return await self.request_document_instead(state)

        # Reconstruct PlexCustomer objects
        candidates = [PlexCustomer.from_dict(c) for c in candidates_data]

        # Parse user selection
        message_clean = message.strip().lower()

        # Try to parse as number
        try:
            selection = int(message_clean)
        except ValueError:
            # Check if user wants to provide document instead
            if any(word in message_clean for word in ["dni", "documento", "doc"]):
                return await self.request_document_instead(state)

            return self._format_invalid_selection_message(len(candidates), state)

        # Validate selection
        if 1 <= selection <= len(candidates):
            return self._handle_valid_selection(selection, candidates, state)

        return self._format_invalid_selection_message(len(candidates), state)

    def _handle_valid_selection(
        self,
        selection: int,
        candidates: list[PlexCustomer],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle valid selection from candidates.

        Args:
            selection: 1-based selection index
            candidates: List of candidate customers
            state: Current state dictionary

        Returns:
            State update for selected customer
        """
        customer = candidates[selection - 1]
        phone = state.get("customer_id") or state.get("user_id")
        pharmacy_name = state.get("pharmacy_name") or "la farmacia"

        logger.info(f"User selected customer: {customer}")

        result: dict[str, Any] = {
            "plex_customer_id": customer.id,
            "plex_customer": customer.to_dict(),
            "customer_name": customer.display_name,
            "customer_identified": True,
            "requires_disambiguation": False,
            "disambiguation_candidates": None,
            "whatsapp_phone": phone,
            "workflow_step": "identified",
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

        # Apply greeting if customer should be greeted
        self._greeting_manager.apply_greeting_if_needed(
            result,
            customer.display_name,
            pharmacy_name,
            state,
            greeting_type="selected",
        )

        return result

    def format_disambiguation_request(
        self,
        candidates: list[PlexCustomer],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Format message asking user to select from candidates.

        Args:
            candidates: List of candidate customers
            state: Current state with pharmacy config

        Returns:
            State update with disambiguation options
        """
        options = "\n".join([f"{i + 1}. {c.display_name} (Doc: {c.masked_document})" for i, c in enumerate(candidates)])

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Encontré varias cuentas asociadas a tu número. "
                        "Por favor indica cuál es la tuya:\n\n"
                        f"{options}\n\n"
                        "Responde con el número de opción (ej: 1)"
                    ),
                }
            ],
            "requires_disambiguation": True,
            "disambiguation_candidates": [c.to_dict() for c in candidates],
            "awaiting_document_input": False,
            "is_complete": False,
            # Preserve pharmacy config
            "pharmacy_id": state.get("pharmacy_id"),
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

    async def request_document_instead(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Return state update to switch to document input.

        Args:
            state: Current state with pharmacy config

        Returns:
            State update requesting document input
        """
        result_content = await self._generate_response(
            intent="request_dni_disambiguation",
            state=state,
            user_message="",
            current_task="Solicita el número de documento para identificar al cliente.",
        )

        return {
            "messages": [{"role": "assistant", "content": result_content}],
            "awaiting_document_input": True,
            "requires_disambiguation": False,
            "disambiguation_candidates": None,
            "is_complete": False,
            # Preserve pharmacy config
            "pharmacy_id": state.get("pharmacy_id"),
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

    def _format_invalid_selection_message(
        self,
        num_candidates: int,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Format message for invalid selection.

        Args:
            num_candidates: Number of candidates available
            state: Current state with pharmacy config

        Returns:
            State update with error message
        """
        # Preserve pharmacy config in all returns
        pharmacy_fields = {
            "pharmacy_id": state.get("pharmacy_id"),
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

        if num_candidates > 0:
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            f"Por favor ingresa el número de la opción que corresponde "
                            f"a tu cuenta (1 a {num_candidates}).\n\n"
                            "O escribe 'DNI' si prefieres buscar por documento."
                        ),
                    }
                ],
                **pharmacy_fields,
            }

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"Opción inválida. Por favor elige un número entre 1 y {num_candidates}.",
                }
            ],
            **pharmacy_fields,
        }
