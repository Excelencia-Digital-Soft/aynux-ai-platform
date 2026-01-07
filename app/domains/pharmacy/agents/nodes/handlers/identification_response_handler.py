"""
Identification Response Handler

Formats all responses for the customer identification flow.
Single responsibility: response formatting for identification.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler
from app.domains.pharmacy.agents.utils.greeting_manager import GreetingManager
from app.prompts.registry import PromptRegistry

if TYPE_CHECKING:
    from app.domains.pharmacy.domain.entities.plex_customer import PlexCustomer
    from app.prompts.manager import PromptManager

logger = logging.getLogger(__name__)


class IdentificationResponseHandler(BasePharmacyHandler):
    """
    Handler for formatting identification flow responses.

    Single responsibility: Format all response messages for the
    customer identification workflow.
    """

    def __init__(
        self,
        prompt_manager: PromptManager | None = None,
        greeting_manager: GreetingManager | None = None,
    ):
        """
        Initialize response handler.

        Args:
            prompt_manager: PromptManager for templates
            greeting_manager: GreetingManager for greeting state
        """
        super().__init__(prompt_manager)
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
        pharmacy_phone = state.get("pharmacy_phone") or "la farmacia"
        customer_identified = state.get("customer_identified")

        try:
            response = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_RESPONSE_OUT_OF_SCOPE,
                variables={"pharmacy_phone": pharmacy_phone},
            )
        except ValueError:
            response = (
                "*Para mejor atencion*\n"
                "Actualmente solo manejo consultas de deuda y envio de links de pago.\n"
                "Para otros asuntos, te recomiendo contactar a nuestros canales especializados:\n"
                f"• *Pedidos y entregas*: {pharmacy_phone}\n"
                f"• *Consultas medicas/recetas*: {pharmacy_phone}\n"
                f"• *Horarios y sucursales*: {pharmacy_phone}"
            )

        # If NOT identified, suggest identification to use debt/payment services
        if not customer_identified:
            response += (
                "\n\n*¿Quieres usar nuestros servicios?*\n"
                "Puedo ayudarte con consulta de deuda y links de pago.\n"
                "Solo necesito tu DNI o numero de cliente para identificarte."
            )

        logger.info(f"Returning out-of-scope response for: '{message[:30]}...'")

        return {
            "messages": [{"role": "assistant", "content": response}],
            "is_complete": False,  # Keep conversation open
            "is_out_of_scope": True,
            "out_of_scope_handled": True,  # Prevents loop back to identification
            "pharmacy_intent_type": "out_of_scope",
            "awaiting_document_input": True,  # Ready to receive DNI if user provides
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

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
        pharmacy_name = state.get("pharmacy_name") or "la farmacia"

        try:
            message = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_IDENTIFICATION_WELCOME,
                variables={"pharmacy_name": pharmacy_name},
            )
        except ValueError:
            message = (
                f"¡Hola! Soy el asistente virtual de {pharmacy_name}.\n\n"
                "Actualmente puedo ayudarte con:\n"
                "• Consulta de deuda en cuenta corriente\n"
                "• Envio de link de pago\n\n"
                "Para consultar tu deuda, necesito que me proporciones tu numero de cliente o documento de identidad.\n"
                "Por favor, envialo en el siguiente formato:\n"
                "• Cliente: [tu numero]\n"
                "o\n"
                "• DNI: [tu documento]\n"
                "Tu informacion sera tratada de forma confidencial."
            )

        return {
            "messages": [{"role": "assistant", "content": message}],
            "awaiting_document_input": True,
            "requires_disambiguation": False,
            "is_complete": False,
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

    def format_registration_offer(
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
        result: dict[str, Any] = {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No encontré una cuenta con esos datos. "
                        "¿Te gustaría registrarte como nuevo cliente?\n\n"
                        "Responde *SI* para registrarte o *NO* para salir."
                    ),
                }
            ],
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

    def format_invalid_document_message(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Format message for invalid document input.

        Args:
            state: Current state with pharmacy config

        Returns:
            State update with validation error message
        """
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "El número de documento ingresado no parece válido. "
                        "Por favor ingresa tu DNI (solo números, mínimo 6 dígitos)."
                    ),
                }
            ],
            "awaiting_document_input": True,
            "is_complete": False,
            # Preserve pharmacy config
            "pharmacy_id": state.get("pharmacy_id"),
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }

    def format_document_reminder_message(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Format reminder message when user sends non-document intent while awaiting document.

        This is used when user tries to perform an action (like "pagar 5000")
        before providing their identification.

        Args:
            state: Current state with pharmacy config

        Returns:
            State update with reminder message
        """
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Entiendo que quieres realizar esa acción, pero primero necesito identificarte.\n\n"
                        "Por favor, proporcioname tu número de DNI o documento de identidad "
                        "(7-8 dígitos) para poder continuar."
                    ),
                }
            ],
            "awaiting_document_input": True,
            "is_complete": False,
            # Preserve pharmacy config
            "pharmacy_id": state.get("pharmacy_id"),
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
        }
