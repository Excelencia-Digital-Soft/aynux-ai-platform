"""
Customer Registration Node

Pharmacy domain node for registering new customers in Plex ERP.
Uses LLM-driven ResponseGenerator for natural language responses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.agents.utils.db_helpers import generate_response
from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
    get_response_generator,
)
from app.domains.pharmacy.application.use_cases.register_customer import (
    RegisterCustomerRequest,
    RegisterCustomerUseCase,
    RegistrationData,
    RegistrationStatus,
    RegistrationStep,
)

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient
    from app.domains.pharmacy.domain.entities.plex_customer import PlexCustomer

logger = logging.getLogger(__name__)

# Validation patterns - single source of truth
YES_RESPONSES: frozenset[str] = frozenset({"SI", "SÍ", "YES", "S"})
NO_RESPONSES: frozenset[str] = frozenset({"NO", "N", "CANCELAR", "SALIR"})


class CustomerRegistrationNode(BaseAgent):
    """Node for registering new customers in Plex ERP."""

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        config: dict[str, Any] | None = None,
        response_generator: PharmacyResponseGenerator | None = None,
    ):
        super().__init__("customer_registration_node", config or {})
        self._plex_client = plex_client
        self._response_generator = response_generator
        self._use_case: RegisterCustomerUseCase | None = None

    def _get_response_generator(self) -> PharmacyResponseGenerator:
        """Get or create ResponseGenerator instance."""
        if self._response_generator is None:
            self._response_generator = get_response_generator()
        return self._response_generator

    def _get_plex_client(self) -> PlexClient:
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient

            self._plex_client = PlexClient()
        return self._plex_client

    def _get_use_case(self) -> RegisterCustomerUseCase:
        """Get or create the use case."""
        if self._use_case is None:
            self._use_case = RegisterCustomerUseCase(self._get_plex_client())
        return self._use_case

    # --- Validation helpers ---

    def _is_yes(self, message: str) -> bool:
        return message.strip().upper() in YES_RESPONSES

    def _is_no(self, message: str) -> bool:
        return message.strip().upper() in NO_RESPONSES

    # --- Response factory ---

    def _response(self, content: str, *, complete: bool = False, **updates: Any) -> dict[str, Any]:
        """Factory for standard responses."""
        return {"messages": [{"role": "assistant", "content": content}], "is_complete": complete, **updates}

    async def _get_response(self, intent: str, state: dict[str, Any], task: str = "") -> str:
        """Get response from ResponseGenerator."""
        response_content = await generate_response(

            state=state,

            intent=intent,

            user_message="",

            current_task=task,

        )
        return response_content

    # --- Main processing ---

    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process registration step."""
        try:
            if self._is_no(message):
                return await self._handle_cancellation()

            intent_type = state_dict.get("pharmacy_intent_type")
            if intent_type == "register_prompt":
                return await self._handle_registration_prompt(message, state_dict)

            reg_data = self._get_registration_data(state_dict)

            if reg_data.current_step == RegistrationStep.NOMBRE:
                return await self._process_name_step(message, state_dict)
            elif reg_data.current_step == RegistrationStep.DOCUMENTO:
                return await self._process_document_step(message, state_dict)
            elif reg_data.current_step == RegistrationStep.CONFIRMAR:
                return await self._process_confirmation_step(message, state_dict)
            else:
                return await self._start_registration(state_dict)

        except Exception as e:
            logger.error(f"Error in customer registration: {e}", exc_info=True)
            return await self._handle_error(state_dict)

    # --- Step handlers ---

    async def _handle_registration_prompt(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle response to 'Do you want to register?' prompt."""
        if self._is_yes(message):
            return await self._start_registration(state_dict)
        if self._is_no(message):
            return await self._handle_cancellation()
        response_state = {**state_dict, "action": "registrarte", "cancel_action": "salir"}
        prompt = await self._get_response(
            "registration_yes_no_validation",
            response_state,
            "Solicita confirmación SI o NO para registrarse.",
        )
        return self._response(prompt, awaiting_registration_data=True, pharmacy_intent_type="register_prompt")

    async def _start_registration(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Start the registration flow."""
        phone = state_dict.get("whatsapp_phone") or state_dict.get("customer_id")
        # Check for pre-provided document from identification flow
        pre_document = state_dict.get("registration_document")
        registration_data: dict[str, Any] = {"telefono": phone}
        if pre_document:
            registration_data["documento"] = pre_document
        prompt = await self._get_response(
            "registration_start",
            state_dict,
            "Inicia el registro solicitando el nombre completo.",
        )
        return self._response(
            prompt,
            awaiting_registration_data=True,
            registration_step=RegistrationStep.NOMBRE.value,
            registration_data=registration_data,
            pharmacy_intent_type="register",
        )

    async def _process_name_step(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process name input."""
        name = message.strip()
        if len(name) < 3:
            prompt = await self._get_response(
                "registration_name_error",
                state_dict,
                "Informa que el nombre es demasiado corto.",
            )
            return self._response(prompt, awaiting_registration_data=True)

        current_data = state_dict.get("registration_data") or {}
        new_data = {**current_data, "nombre": name.upper()}

        # If document was pre-provided, skip to confirmation step
        if new_data.get("documento"):
            response_state = {**state_dict, "nombre": name.upper(), "documento": new_data["documento"]}
            prompt = await self._get_response(
                "registration_confirm_data",
                response_state,
                "Muestra los datos para confirmación.",
            )
            return self._response(
                prompt, registration_step=RegistrationStep.CONFIRMAR.value, registration_data=new_data
            )

        # Otherwise ask for document
        prompt = await self._get_response(
            "registration_document_prompt",
            state_dict,
            "Solicita el número de documento.",
        )
        return self._response(prompt, registration_step=RegistrationStep.DOCUMENTO.value, registration_data=new_data)

    async def _process_document_step(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process document input."""
        document = "".join(c for c in message.strip() if c.isdigit())
        if len(document) < 6 or len(document) > 11:
            prompt = await self._get_response(
                "registration_document_error",
                state_dict,
                "Informa que el documento no es válido.",
            )
            return self._response(prompt, awaiting_registration_data=True)

        current_data = state_dict.get("registration_data") or {}
        new_data = {**current_data, "documento": document}
        response_state = {**state_dict, "nombre": current_data.get("nombre", ""), "documento": document}
        prompt = await self._get_response(
            "registration_confirm_data",
            response_state,
            "Muestra los datos para confirmación.",
        )
        return self._response(prompt, registration_step=RegistrationStep.CONFIRMAR.value, registration_data=new_data)

    async def _process_confirmation_step(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process confirmation - orchestrator."""
        if self._is_no(message):
            return await self._handle_cancellation()
        if not self._is_yes(message):
            response_state = {**state_dict, "action": "confirmar", "cancel_action": "cancelar"}
            prompt = await self._get_response(
                "registration_yes_no_validation",
                response_state,
                "Solicita confirmación SI o NO.",
            )
            return self._response(
                prompt, awaiting_registration_data=True, registration_step=RegistrationStep.CONFIRMAR.value
            )
        return await self._execute_registration(state_dict)

    # --- Registration execution ---

    async def _execute_registration(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Execute registration in Plex and handle outcomes."""
        current_data = state_dict.get("registration_data") or {}
        nombre, documento, telefono = (
            current_data.get("nombre"),
            current_data.get("documento"),
            current_data.get("telefono"),
        )

        if not all([nombre, documento, telefono]):
            logger.error(f"Incomplete registration data: {current_data}")
            return await self._start_registration(state_dict)

        # Type narrowing - all() check above ensures these are not None
        assert nombre is not None and documento is not None and telefono is not None
        logger.info(f"Creating customer: nombre={nombre}, doc={documento}")
        plex_client = self._get_plex_client()
        use_case = self._get_use_case()

        async with plex_client:
            response = await use_case.execute(
                RegisterCustomerRequest(nombre=nombre, documento=documento, telefono=telefono)
            )

        match response.status:
            case RegistrationStatus.REGISTERED:
                return await self._handle_success(response.customer)
            case RegistrationStatus.DUPLICATE:
                return await self._handle_duplicate(response.customer)
            case RegistrationStatus.NOT_SUPPORTED:
                return await self._handle_not_supported()
            case _:
                return await self._handle_registration_error(response.error)

    # --- Outcome handlers ---

    async def _handle_success(self, customer: PlexCustomer | None) -> dict[str, Any]:
        """Handle successful registration."""
        if not customer:
            return await self._handle_registration_error("No customer data returned")

        response_state = {"customer_name": customer.display_name}
        prompt = await self._get_response(
            "registration_success",
            response_state,
            "Confirma el registro exitoso.",
        )
        return self._response(
            prompt,
            plex_customer_id=customer.id,
            plex_customer=customer.to_dict(),
            customer_name=customer.display_name,
            customer_identified=True,
            awaiting_registration_data=False,
            registration_step=None,
            registration_data=None,
            workflow_step="identified",
        )

    async def _handle_duplicate(self, customer: PlexCustomer | None) -> dict[str, Any]:
        """Handle duplicate customer."""
        if customer:
            response_state = {"customer_name": customer.display_name}
            prompt = await self._get_response(
                "registration_duplicate_with_name",
                response_state,
                "Informa que el cliente ya existe.",
            )
            return self._response(
                prompt,
                plex_customer_id=customer.id,
                plex_customer=customer.to_dict(),
                customer_name=customer.display_name,
                customer_identified=True,
                awaiting_registration_data=False,
                registration_step=None,
                registration_data=None,
                workflow_step="identified",
            )
        prompt = await self._get_response(
            "registration_duplicate_no_name",
            {},
            "Informa que el documento ya está registrado.",
        )
        return self._response(
            prompt, complete=True, awaiting_registration_data=False, registration_step=None, registration_data=None
        )

    async def _handle_not_supported(self) -> dict[str, Any]:
        """Handle registration not supported."""
        prompt = await self._get_response(
            "registration_not_supported",
            {},
            "Informa que el registro no está disponible.",
        )
        return self._response(prompt, complete=True, awaiting_registration_data=False)

    async def _handle_registration_error(self, error: str | None) -> dict[str, Any]:
        """Handle registration error."""
        error_msg = error or "Error desconocido"
        logger.error(f"Registration failed: {error_msg}")
        prompt = await self._get_response(
            "registration_error",
            {"error": error_msg},
            "Informa del error en el registro.",
        )
        return self._response(prompt, complete=True, awaiting_registration_data=False, requires_human=True)

    # --- Helper methods ---

    def _get_registration_data(self, state_dict: dict[str, Any]) -> RegistrationData:
        """Get or create registration data from state."""
        data = state_dict.get("registration_data") or {}
        step_str = state_dict.get("registration_step", "nombre")
        try:
            step = RegistrationStep(step_str)
        except ValueError:
            step = RegistrationStep.NOMBRE
        return RegistrationData(
            nombre=data.get("nombre"),
            documento=data.get("documento"),
            telefono=data.get("telefono"),
            email=data.get("email"),
            direccion=data.get("direccion"),
            current_step=step,
        )

    async def _handle_cancellation(self) -> dict[str, Any]:
        """Handle registration cancellation."""
        prompt = await self._get_response(
            "registration_cancelled",
            {},
            "Confirma la cancelación del registro.",
        )
        return self._response(
            prompt,
            complete=True,
            awaiting_registration_data=False,
            registration_step=None,
            registration_data=None,
            pharmacy_intent_type=None,
        )

    async def _handle_error(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        error_count = state_dict.get("error_count", 0) + 1
        prompt = await self._get_response(
            "registration_exception",
            state_dict,
            "Informa del error y sugiere intentar de nuevo.",
        )
        return self._response(prompt, error_count=error_count)
