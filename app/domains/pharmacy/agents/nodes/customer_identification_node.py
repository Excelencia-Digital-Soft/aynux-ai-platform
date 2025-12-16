"""
Customer Identification Node

Pharmacy domain node for identifying Plex customer from WhatsApp context.
Handles the 2-step flow and disambiguation logic.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.application.use_cases.identify_customer import (
    IdentificationStatus,
    IdentifyCustomerRequest,
    IdentifyCustomerUseCase,
)
from app.domains.pharmacy.domain.entities.plex_customer import PlexCustomer

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)


class CustomerIdentificationNode(BaseAgent):
    """
    Node for identifying Plex customer from WhatsApp user.

    This is the entry point for the pharmacy workflow. It:
    1. Searches for customer by WhatsApp phone number
    2. Handles disambiguation if multiple matches found
    3. Handles document input if phone search fails
    4. Offers registration if customer not found
    """

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize customer identification node.

        Args:
            plex_client: PlexClient instance for API calls
            config: Node configuration
        """
        super().__init__("customer_identification_node", config or {})
        self._plex_client = plex_client
        self._use_case: IdentifyCustomerUseCase | None = None

    def _get_plex_client(self) -> PlexClient:
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient
            self._plex_client = PlexClient()
        return self._plex_client

    def _get_use_case(self) -> IdentifyCustomerUseCase:
        """Get or create the use case."""
        if self._use_case is None:
            self._use_case = IdentifyCustomerUseCase(self._get_plex_client())
        return self._use_case

    def _should_greet(self, state_dict: dict[str, Any]) -> bool:
        """Check if customer should be greeted (not greeted today)."""
        if state_dict.get("greeted_today"):
            last_date = state_dict.get("last_greeting_date")
            if last_date == date.today().isoformat():
                return False  # Already greeted today
        return True  # Should greet

    def _get_greeting_state(self) -> dict[str, Any]:
        """Return state updates for greeting tracking."""
        return {
            "greeted_today": True,
            "last_greeting_date": date.today().isoformat(),
        }

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process customer identification.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            # Already identified?
            if state_dict.get("customer_identified") and state_dict.get("plex_customer_id"):
                logger.debug("Customer already identified, passing through")
                return {"customer_identified": True}

            # Handling disambiguation?
            if state_dict.get("requires_disambiguation"):
                return await self._handle_disambiguation(message, state_dict)

            # Waiting for document input?
            if state_dict.get("awaiting_document_input"):
                return await self._handle_document_input(message, state_dict)

            # Initial identification attempt
            return await self._initial_identification(state_dict)

        except Exception as e:
            logger.error(f"Error in customer identification: {e}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    async def _initial_identification(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform initial customer identification by phone."""
        # Get phone from WhatsApp context
        phone = state_dict.get("customer_id") or state_dict.get("user_id")

        if not phone:
            logger.warning("No phone number available for identification")
            return self._request_document_input()

        logger.info(f"Identifying customer by phone: {phone}")
        print(f"[DEBUG] _initial_identification: phone={phone}")  # DEBUG

        plex_client = self._get_plex_client()
        print(f"[DEBUG] plex_client created: base_url={plex_client.base_url}")  # DEBUG

        async with plex_client:
            print(f"[DEBUG] Executing use case with phone={phone}")  # DEBUG
            response = await self._get_use_case().execute(
                IdentifyCustomerRequest(phone=phone)
            )
            print(f"[DEBUG] Use case response: status={response.status}, customer={response.customer}, error={response.error}")  # DEBUG

        if response.status == IdentificationStatus.IDENTIFIED:
            customer = response.customer
            if customer is None:
                return self._handle_error("Customer object is None", state_dict)

            logger.info(f"Customer identified: {customer}")
            return self._return_identified(customer, phone, state_dict)

        elif response.status == IdentificationStatus.DISAMBIGUATION_REQUIRED:
            logger.info(f"Disambiguation required: {len(response.candidates or [])} candidates")
            return self._request_disambiguation(response.candidates or [])

        elif response.status == IdentificationStatus.NOT_FOUND:
            logger.info("Customer not found by phone, requesting document")
            return self._request_document_input()

        else:
            return self._handle_error(
                response.error or "Identification failed",
                state_dict,
            )

    async def _handle_disambiguation(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle user's disambiguation selection."""
        candidates_data = state_dict.get("disambiguation_candidates", [])

        if not candidates_data:
            logger.warning("No disambiguation candidates in state")
            return self._request_document_input()

        # Reconstruct PlexCustomer objects
        candidates = [PlexCustomer.from_dict(c) for c in candidates_data]

        # Parse user selection (expecting a number)
        message_clean = message.strip().lower()

        # Try to parse as number
        try:
            selection = int(message_clean)
        except ValueError:
            # Check if user wants to provide document instead
            if any(word in message_clean for word in ["dni", "documento", "doc"]):
                return self._request_document_input_from_disambiguation()

            return {
                "messages": [{
                    "role": "assistant",
                    "content": (
                        f"Por favor ingresa el número de la opción que corresponde a tu cuenta (1 a {len(candidates)}).\n\n"
                        "O escribe 'DNI' si prefieres buscar por documento."
                    ),
                }],
            }

        # Validate selection
        if 1 <= selection <= len(candidates):
            customer = candidates[selection - 1]
            phone = state_dict.get("customer_id") or state_dict.get("user_id")
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
            }

            # Conditional greeting: only greet if not greeted today
            # Store as pending_greeting to combine with next response
            if self._should_greet(state_dict):
                greeting = f"Perfecto, {customer.display_name}."
                result["pending_greeting"] = greeting
                result.update(self._get_greeting_state())

            return result

        return {
            "messages": [{
                "role": "assistant",
                "content": f"Opción inválida. Por favor elige un número entre 1 y {len(candidates)}.",
            }],
        }

    async def _handle_document_input(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle user providing document number."""
        document = message.strip()

        # Basic validation
        cleaned_doc = "".join(c for c in document if c.isdigit())

        if not cleaned_doc or len(cleaned_doc) < 6:
            return {
                "messages": [{
                    "role": "assistant",
                    "content": (
                        "El número de documento ingresado no parece válido. "
                        "Por favor ingresa tu DNI (solo números, mínimo 6 dígitos)."
                    ),
                }],
                "awaiting_document_input": True,
                "is_complete": False,
            }

        logger.info(f"Searching customer by document: {cleaned_doc}")

        plex_client = self._get_plex_client()

        async with plex_client:
            response = await self._get_use_case().execute(
                IdentifyCustomerRequest(document=cleaned_doc)
            )

        phone = state_dict.get("customer_id") or state_dict.get("user_id")

        if response.status == IdentificationStatus.IDENTIFIED:
            customer = response.customer
            if customer is None:
                return self._offer_registration(phone)

            logger.info(f"Customer identified by document: {customer}")
            result: dict[str, Any] = {
                "plex_customer_id": customer.id,
                "plex_customer": customer.to_dict(),
                "customer_name": customer.display_name,
                "customer_identified": True,
                "awaiting_document_input": False,
                "whatsapp_phone": phone,
                "workflow_step": "identified",
            }

            # Conditional greeting: only greet if not greeted today
            # Store as pending_greeting to combine with next response
            if self._should_greet(state_dict):
                greeting = f"Te encontré, {customer.display_name}."
                result["pending_greeting"] = greeting
                result.update(self._get_greeting_state())

            return result

        elif response.status == IdentificationStatus.DISAMBIGUATION_REQUIRED:
            return self._request_disambiguation(response.candidates or [])

        else:
            # Not found - offer registration
            logger.info("Customer not found by document, offering registration")
            return self._offer_registration(phone)

    def _return_identified(
        self,
        customer: PlexCustomer,
        phone: str | None,
        state_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return state for identified customer."""
        state_dict = state_dict or {}

        result: dict[str, Any] = {
            "plex_customer_id": customer.id,
            "plex_customer": customer.to_dict(),
            "customer_name": customer.display_name,
            "customer_identified": True,
            "requires_disambiguation": False,
            "awaiting_document_input": False,
            "whatsapp_phone": phone,
            "workflow_step": "identified",
        }

        # Conditional greeting: only greet if not greeted today
        # Store as pending_greeting to combine with next response
        if self._should_greet(state_dict):
            greeting = f"Hola {customer.display_name}, bienvenido/a."
            result["pending_greeting"] = greeting
            result.update(self._get_greeting_state())

        return result

    def _request_disambiguation(
        self,
        candidates: list[PlexCustomer],
    ) -> dict[str, Any]:
        """Request user to select from multiple matches."""
        options = "\n".join([
            f"{i+1}. {c.display_name} (Doc: {c.masked_document})"
            for i, c in enumerate(candidates)
        ])

        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "Encontré varias cuentas asociadas a tu número. "
                    "Por favor indica cuál es la tuya:\n\n"
                    f"{options}\n\n"
                    "Responde con el número de opción (ej: 1)"
                ),
            }],
            "requires_disambiguation": True,
            "disambiguation_candidates": [c.to_dict() for c in candidates],
            "awaiting_document_input": False,
            "is_complete": False,
        }

    def _request_document_input(self) -> dict[str, Any]:
        """Request user to provide document number."""
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "No encontré una cuenta asociada a tu número de teléfono. "
                    "Por favor ingresa tu número de documento (DNI) para buscarte."
                ),
            }],
            "awaiting_document_input": True,
            "requires_disambiguation": False,
            "is_complete": False,
        }

    def _request_document_input_from_disambiguation(self) -> dict[str, Any]:
        """Request document when user prefers over disambiguation."""
        return {
            "messages": [{
                "role": "assistant",
                "content": "Por favor ingresa tu número de documento (DNI):",
            }],
            "awaiting_document_input": True,
            "requires_disambiguation": False,
            "disambiguation_candidates": None,
            "is_complete": False,
        }

    def _offer_registration(self, phone: str | None) -> dict[str, Any]:
        """Offer registration to new customer."""
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "No encontré una cuenta con esos datos. "
                    "¿Te gustaría registrarte como nuevo cliente?\n\n"
                    "Responde *SI* para registrarte o *NO* para salir."
                ),
            }],
            "awaiting_document_input": False,
            "awaiting_registration_data": False,
            "pharmacy_intent_type": "register_prompt",
            "whatsapp_phone": phone,
            "is_complete": False,
        }

    def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Customer identification error: {error}")
        logger.error(f"Full traceback:\n{tb}")
        print(f"[DEBUG] _handle_error called with: {error}")  # DEBUG
        print(f"[DEBUG] Traceback:\n{tb}")  # DEBUG
        error_count = state_dict.get("error_count", 0) + 1

        if error_count >= state_dict.get("max_errors", 3):
            return {
                "messages": [{
                    "role": "assistant",
                    "content": (
                        "Tuve varios problemas intentando identificarte. "
                        "Por favor contacta a la farmacia directamente."
                    ),
                }],
                "error_count": error_count,
                "is_complete": True,
                "requires_human": True,
            }

        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "Tuve un problema identificando tu cuenta. "
                    "Por favor intenta de nuevo o ingresa tu DNI."
                ),
            }],
            "error_count": error_count,
            "awaiting_document_input": True,
        }
