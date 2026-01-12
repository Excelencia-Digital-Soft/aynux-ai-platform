"""
Identification Response Handler

Formats all responses for the customer identification flow.
Single responsibility: response formatting for identification.
Uses LLM-driven ResponseGenerator for natural language responses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler
from app.domains.pharmacy.agents.utils.greeting_manager import GreetingManager
from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
)

if TYPE_CHECKING:
    from app.domains.pharmacy.domain.entities.plex_customer import PlexCustomer

logger = logging.getLogger(__name__)


class IdentificationResponseHandler(BasePharmacyHandler):
    """
    Handler for formatting identification flow responses.

    Single responsibility: Format all response messages for the
    customer identification workflow.
    """

    def __init__(
        self,
        response_generator: PharmacyResponseGenerator | None = None,
        greeting_manager: GreetingManager | None = None,
    ):
        """
        Initialize response handler.

        Args:
            response_generator: ResponseGenerator for LLM-driven responses
            greeting_manager: GreetingManager for greeting state
        """
        super().__init__(response_generator)
        self._greeting_manager = greeting_manager or GreetingManager()

    async def format_out_of_scope_response(
        self,
        message: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Format out-of-scope response with pharmacy contact info.

        If customer is NOT identified, also suggests identification to use
        debt/payment services.

        Args:
            message: Original user message
            state: Current state with pharmacy config

        Returns:
            State update with out-of-scope response
        """
        customer_identified = state.get("customer_identified")

        # Use different intent based on identification status
        intent = "out_of_scope_identified" if customer_identified else "out_of_scope_not_identified"

        result_content = await self._generate_response(
            intent=intent,
            state=state,
            user_message=message,
            current_task="Explica qué puedes hacer y sugiere contactar la farmacia para otros temas.",
        )

        logger.info(f"Returning out-of-scope response for: '{message[:30]}...'")

        return {
            "messages": [{"role": "assistant", "content": result_content}],
            "is_complete": False,  # Keep conversation open
            "is_out_of_scope": True,
            "out_of_scope_handled": True,  # Prevents loop back to identification
            "pharmacy_intent_type": "out_of_scope",
            "awaiting_document_input": True,  # Ready to receive DNI if user provides
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

    async def format_info_query_response(
        self,
        message: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Format response for pharmacy info queries (horarios, direccion, etc).

        These are PUBLIC queries that don't require customer identification.
        Delegates to PharmacyInfoHandler for actual info retrieval.

        Args:
            message: Original user message
            state: Current state with pharmacy config

        Returns:
            State update with pharmacy info response
        """
        from app.domains.pharmacy.agents.nodes.handlers.pharmacy_info_handler import (
            PharmacyInfoHandler,
        )

        logger.info(f"Handling info query without identification: '{message[:30]}...'")

        handler = PharmacyInfoHandler(self._response_generator)
        result = await handler.handle(message, state)

        # Keep conversation open for further queries or identification
        result["is_complete"] = False
        result["awaiting_document_input"] = True  # Ready to receive DNI if user wants

        return result

    async def format_welcome_message(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Format welcome message requesting document input.

        Args:
            state: Current state with pharmacy config

        Returns:
            State update with welcome message
        """
        result_content = await self._generate_response(
            intent="welcome_message",
            state=state,
            user_message="",
            current_task="Da la bienvenida y solicita el DNI para identificar al cliente.",
        )

        return {
            "messages": [{"role": "assistant", "content": result_content}],
            "awaiting_document_input": True,
            "requires_disambiguation": False,
            "is_complete": False,
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

    async def format_registration_offer(
        self,
        phone: str | None,
        state: dict[str, Any],
        document: str | None = None,
    ) -> dict[str, Any]:
        """
        Format registration offer for unknown customer.

        Args:
            phone: WhatsApp phone number
            state: Current state with pharmacy config
            document: Document/DNI already provided (to avoid asking again)

        Returns:
            State update with registration offer
        """
        response_content = await self._generate_response(
            intent="registration_offer",
            state=state,
            user_message="",
            current_task="Ofrece registrarse como nuevo cliente.",
        )

        result: dict[str, Any] = {
            "messages": [{"role": "assistant", "content": response_content}],
            "awaiting_document_input": False,
            "awaiting_registration_data": True,
            "pharmacy_intent_type": "register_prompt",
            "whatsapp_phone": phone,
            "is_complete": False,
            # Preserve pharmacy config
            "pharmacy_id": state.get("pharmacy_id"),
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }
        # Store pre-provided document to skip DNI step in registration
        if document:
            result["registration_document"] = document
        return result

    def format_identified_customer(
        self,
        customer: PlexCustomer,
        phone: str | None,
        state: dict[str, Any],
        greeting_type: str = "welcome",
    ) -> dict[str, Any]:
        """
        Format successful identification response.

        Args:
            customer: Identified PlexCustomer
            phone: WhatsApp phone number
            state: Current state with pharmacy config
            greeting_type: Type of greeting (welcome, found, selected)

        Returns:
            State update for identified customer
        """
        pharmacy_name = state.get("pharmacy_name") or "la farmacia"

        result: dict[str, Any] = {
            "plex_customer_id": customer.id,
            "plex_customer": customer.to_dict(),
            "customer_name": customer.display_name,
            "customer_identified": True,
            "just_identified": True,
            "requires_disambiguation": False,
            "awaiting_document_input": False,
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
            greeting_type,
        )

        return result

    async def format_invalid_document_message(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Format message for invalid document input.

        Args:
            state: Current state with pharmacy config

        Returns:
            State update with validation error message
        """
        response_content = await self._generate_response(
            intent="invalid_document",
            state=state,
            user_message="",
            current_task="Informa que el documento no es válido y solicita el formato correcto.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "awaiting_document_input": True,
            "is_complete": False,
            # Preserve pharmacy config
            "pharmacy_id": state.get("pharmacy_id"),
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

    async def format_document_reminder_message(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Format reminder message when user sends non-document intent while awaiting document.

        This is used when user tries to perform an action (like "pagar 5000")
        before providing their identification.

        Args:
            state: Current state with pharmacy config

        Returns:
            State update with reminder message
        """
        response_content = await self._generate_response(
            intent="document_reminder",
            state=state,
            user_message="",
            current_task="Recuerda que necesita identificarse antes de realizar la acción.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "awaiting_document_input": True,
            "is_complete": False,
            # Preserve pharmacy config
            "pharmacy_id": state.get("pharmacy_id"),
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }
