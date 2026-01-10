"""
PersonResolutionNode - Thin Orchestrator.

Coordinates the person resolution workflow by delegating
to specialized services and handlers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    STEP_AWAITING_IDENTIFIER,
    STEP_AWAITING_WELCOME,
    STEP_NAME,
)
from app.domains.pharmacy.agents.nodes.person_resolution.factory import (
    PersonResolutionFactory,
)
from app.domains.pharmacy.agents.utils.db_helpers import generate_response
from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
    RegisteredPersonRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.clients.plex_client import PlexClient
    from app.models.db.tenancy.registered_person import RegisteredPerson

logger = logging.getLogger(__name__)


class PersonResolutionNode(BaseAgent):
    """
    Entry node that orchestrates person resolution workflow.

    This is a thin coordinator that delegates to:
    - Services: identification, state management, payment state
    - Handlers: welcome, identifier, name verification, own/other, escalation
    """

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        db_session: AsyncSession | None = None,
        config: dict[str, Any] | None = None,
        factory: PersonResolutionFactory | None = None,
    ):
        """
        Initialize person resolution node.

        Args:
            plex_client: PlexClient instance for API calls
            db_session: SQLAlchemy async session for DB access
            config: Node configuration
            factory: Optional factory with pre-configured dependencies
        """
        super().__init__("person_resolution_node", config or {})
        self._db_session = db_session
        self._factory = factory or PersonResolutionFactory(
            plex_client=plex_client,
            db_session=db_session,
            config=config,
        )
        self._registered_person_repo: RegisteredPersonRepository | None = None

    async def _get_registered_person_repo(self) -> RegisteredPersonRepository:
        """Get or create registered person repository."""
        if self._registered_person_repo is None:
            if self._db_session is None:
                from app.database.async_db import get_async_db

                self._db_session = await anext(get_async_db())
            self._registered_person_repo = RegisteredPersonRepository(self._db_session)
        return self._registered_person_repo

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Orchestrate person resolution workflow.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            # Get services
            state_service = self._factory.get_state_service()
            payment_service = self._factory.get_payment_service()

            # Load pharmacy config
            state_dict = await state_service.ensure_pharmacy_config(state_dict)

            # Check zombie payment
            zombie_result = await payment_service.check_zombie_payment(state_dict)
            if zombie_result:
                return zombie_result

            # Already identified?
            if state_dict.get("customer_identified") and state_dict.get("plex_customer_id"):
                logger.debug("Customer already identified, passing through")
                return self._pass_through_identified(state_dict)

            # Route to person selection if waiting
            if state_dict.get("awaiting_person_selection"):
                return {"awaiting_person_selection": True, "next_node": "person_selection_node"}

            # Route to validation if waiting (legacy)
            if self._is_legacy_validation_step(state_dict):
                return self._route_to_legacy_validation(state_dict)

            # Handle identification flow states
            identification_step = state_dict.get("identification_step")

            if identification_step == STEP_AWAITING_WELCOME:
                return await self._handle_welcome_response(message, state_dict)

            if identification_step == STEP_AWAITING_IDENTIFIER:
                return await self._handle_identifier_input(message, state_dict)

            if identification_step == STEP_NAME:
                return await self._handle_name_verification(message, state_dict)

            # Handle own/other decision
            if state_dict.get("awaiting_own_or_other"):
                return await self._handle_own_or_other(message, state_dict)

            # Initial resolution
            return await self._initial_resolution(message, state_dict)

        except Exception as e:
            logger.error(f"Error in person resolution: {e}", exc_info=True)
            return await self._factory.get_error_handler().handle_error(str(e), state_dict)

    # =========================================================================
    # Delegation Methods
    # =========================================================================

    async def _handle_welcome_response(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Delegate welcome response handling to WelcomeFlowHandler."""
        handler = self._factory.get_welcome_handler()
        return await handler.handle_response(message, state_dict)

    async def _handle_identifier_input(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Delegate identifier input handling to IdentifierFlowHandler."""
        handler = self._factory.get_identifier_handler()
        result = await handler.handle(message, state_dict)

        # Check for escalation
        if result.get("identification_failed"):
            escalation = self._factory.get_escalation_handler()
            return await escalation.escalate_identification_failure(
                state_dict, result.get("identification_retries", 0)
            )

        return result

    async def _handle_name_verification(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Delegate name verification to NameVerificationHandler."""
        handler = self._factory.get_name_handler()
        result = await handler.handle(message, state_dict)

        # Check for escalation
        if result.get("name_verification_failed"):
            escalation = self._factory.get_escalation_handler()
            return await escalation.escalate_name_verification_failure(
                state_dict, result.get("name_mismatch_count", 0)
            )

        # Complete identification
        if result.get("identification_complete"):
            return await self._complete_identification(
                result.get("plex_customer_verified", {}), state_dict
            )

        return result

    async def _handle_own_or_other(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Delegate own/other handling to OwnOrOtherHandler."""
        handler = self._factory.get_own_other_handler()
        result = await handler.handle_response(message, state_dict)

        if result.get("decision") == "own":
            plex_customer = result.get("self_plex_customer", {})
            return await self._proceed_with_customer(plex_customer, state_dict, is_self=True)

        if result.get("decision") == "other":
            return await self._route_to_validation(state_dict, is_for_other=True)

        return result

    async def _initial_resolution(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform initial person resolution."""
        state_service = self._factory.get_state_service()
        id_service = self._factory.get_identification_service()

        phone = state_service.extract_phone(state_dict)
        pharmacy_id = state_service.get_pharmacy_id(state_dict)

        if not phone:
            return await self._factory.get_error_handler().handle_no_phone(message, state_dict)

        if not pharmacy_id:
            return await self._factory.get_error_handler().handle_no_pharmacy(message, state_dict)

        logger.info(f"Resolving person for phone: {phone}, pharmacy: {pharmacy_id}")

        # Check local DB
        repo = await self._get_registered_person_repo()
        registered_persons = await repo.get_valid_by_phone(phone, pharmacy_id)

        # Check PLEX
        plex_customer = await id_service.search_by_phone(phone)

        has_plex_match = plex_customer is not None
        has_registrations = len(registered_persons) > 0

        logger.info(
            f"Resolution status: plex_match={has_plex_match}, registrations={len(registered_persons)}"
        )

        if has_plex_match:
            self_registration = id_service.find_self_registration(registered_persons, plex_customer)

            if has_registrations and not id_service.only_self_registered(
                registered_persons, self_registration
            ):
                return self._route_to_person_selection(registered_persons, plex_customer, state_dict)
            else:
                handler = self._factory.get_own_other_handler()
                return await handler.ask(plex_customer, state_dict)

        elif has_registrations:
            return self._route_to_person_selection(registered_persons, None, state_dict)

        else:
            handler = self._factory.get_welcome_handler()
            return await handler.show_welcome_message(state_dict)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _pass_through_identified(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Return pass-through state for already identified customers."""
        return {
            "customer_identified": True,
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }

    def _is_legacy_validation_step(self, state_dict: dict[str, Any]) -> bool:
        """Check if state has a legacy validation step."""
        step = state_dict.get("validation_step")
        return step is not None and step not in [
            STEP_AWAITING_WELCOME,
            STEP_AWAITING_IDENTIFIER,
            STEP_NAME,
        ]

    def _route_to_legacy_validation(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Route to legacy person validation node."""
        return {
            "validation_step": state_dict.get("validation_step"),
            "next_node": "person_validation_node",
        }

    def _route_to_person_selection(
        self,
        registrations: list[RegisteredPerson],
        plex_customer: dict[str, Any] | None,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Route to person selection node."""
        return {
            "registered_persons": [r.to_dict() for r in registrations],
            "self_plex_customer": plex_customer,
            "include_self_in_list": plex_customer is not None,
            "awaiting_person_selection": True,
            "next_node": "person_selection_node",
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }

    async def _route_to_validation(
        self,
        state_dict: dict[str, Any],
        is_for_other: bool = False,
    ) -> dict[str, Any]:
        """Route to person validation node."""
        if is_for_other:
            intent = "request_dni_for_other"
            task = "Solicita el DNI de la otra persona para verificar sus datos."
        else:
            intent = "request_dni_welcome"
            task = "Da la bienvenida y solicita el DNI para verificar identidad."

        response_content = await generate_response(
            state=state_dict, intent=intent, user_message="", current_task=task
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "validation_step": "dni",
            "is_querying_for_other": is_for_other,
            "next_node": "person_validation_node",
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }

    async def _proceed_with_customer(
        self,
        plex_customer: dict[str, Any],
        state_dict: dict[str, Any],
        is_self: bool = False,
    ) -> dict[str, Any]:
        """Proceed with identified customer to debt check."""
        customer_name = plex_customer.get("nombre", "")

        response_state = {**state_dict, "customer_name": customer_name}
        response_content = await generate_response(
            state=response_state,
            intent="proceed_with_customer",
            user_message="",
            current_task="Confirma al cliente seleccionado y procede a consultar su deuda.",
        )

        return {
            "plex_customer_id": plex_customer.get("id"),
            "plex_customer": plex_customer,
            "customer_name": customer_name,
            "customer_identified": True,
            "is_self": is_self,
            "awaiting_own_or_other": False,
            "next_node": "debt_check_node",
            "messages": [{"role": "assistant", "content": response_content}],
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }

    async def _complete_identification(
        self,
        plex_customer: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Complete identification and register the person."""
        state_service = self._factory.get_state_service()

        customer_name = plex_customer.get("nombre", "")
        phone = state_service.extract_phone(state_dict)
        pharmacy_id = state_service.get_pharmacy_id(state_dict)
        documento = plex_customer.get("documento", "")
        plex_id = plex_customer.get("id")

        # Register in local DB
        if phone and pharmacy_id and documento and plex_id:
            try:
                from app.models.db.tenancy.registered_person import RegisteredPerson

                repo = await self._get_registered_person_repo()
                person = RegisteredPerson(
                    phone_number=phone,
                    pharmacy_id=pharmacy_id,
                    dni=documento,
                    name=customer_name,
                    plex_customer_id=plex_id,
                    is_self=True,
                )
                await repo.upsert(person)
                logger.info(f"Registered person {customer_name} for phone {phone}")
            except Exception as e:
                logger.warning(f"Failed to register person: {e}")

        # Generate success message
        response_state = {**state_dict, "customer_name": customer_name}
        response_content = await generate_response(
            state=response_state,
            intent="identification_success",
            user_message="",
            current_task="Confirma identificación exitosa y muestra menú principal.",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "plex_customer_id": plex_customer.get("id"),
            "plex_customer": plex_customer,
            "customer_name": customer_name,
            "customer_identified": True,
            "is_self": True,
            "identification_step": None,
            "current_menu": "main",
            "next_node": "main_menu_node",
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }


__all__ = ["PersonResolutionNode"]
