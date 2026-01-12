"""
Person registration service.

Handles person registration in local database after successful identification.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PersonRegistrationService:
    """
    Service for person registration operations.

    Responsibilities:
    - Register identified persons in local DB
    - Upsert registration records
    - Handle registration errors gracefully

    This service handles the database operations required to register
    a person after successful identification in the person resolution flow.
    """

    def __init__(self, db_session: AsyncSession | None = None):
        self._db_session = db_session
        self._registered_person_repo: Any = None

    async def _get_registered_person_repo(self) -> Any:
        """Get or create registered person repository."""
        if self._registered_person_repo is None:
            from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
                RegisteredPersonRepository,
            )

            if self._db_session is None:
                from app.database.async_db import create_async_session

                self._db_session = await create_async_session()
                logger.debug("Created async session for PersonRegistrationService")

            self._registered_person_repo = RegisteredPersonRepository(self._db_session)

        return self._registered_person_repo

    async def register_identified_person(
        self,
        phone: str,
        pharmacy_id: UUID,
        plex_customer: dict[str, Any],
        db_session: AsyncSession | None = None,
    ) -> Any:
        """
        Register an identified person in the local database.

        Args:
            phone: Customer phone number
            pharmacy_id: Pharmacy UUID
            plex_customer: PLEX customer data
            db_session: Optional DB session (uses instance session if None)

        Returns:
            RegisteredPerson instance or None on error
        """
        from app.models.db.tenancy.registered_person import RegisteredPerson

        documento = plex_customer.get("documento", "")
        plex_id = plex_customer.get("id")
        customer_name = plex_customer.get("nombre", "")

        if not (phone and pharmacy_id and documento and plex_id):
            logger.warning("Missing required data for person registration")
            return None

        try:
            repo = await self._get_registered_person_repo()
            if db_session:
                repo._db_session = db_session

            person = RegisteredPerson.create(
                phone_number=phone,
                pharmacy_id=pharmacy_id,
                dni=documento,
                name=customer_name,
                plex_customer_id=plex_id,
                is_self=True,
            )
            await repo.upsert(person)
            logger.info(f"Registered person {customer_name} for phone {phone}")
            return person

        except Exception as e:
            logger.warning(f"Failed to register person: {e}")
            return None

    async def complete_registration_flow(
        self,
        plex_customer: dict[str, Any],
        state_dict: dict[str, Any],
        db_session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """
        Complete identification and registration flow.

        Registers the person in local DB and generates success response state.

        Args:
            plex_customer: PLEX customer data
            state_dict: Current state dictionary
            db_session: Optional DB session

        Returns:
            Updated state dictionary with identification complete
        """
        from app.domains.pharmacy.agents.models import StatePreserver
        from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
        from app.tasks import TaskRegistry

        customer_name = plex_customer.get("nombre", "")

        # Extract phone and pharmacy_id from state
        state_service_import = __import__(
            "app.domains.pharmacy.agents.nodes.person_resolution.services.state_management_service",
            fromlist=["StateManagementService"],
        )
        state_service = state_service_import.StateManagementService()

        phone = state_service.extract_phone(state_dict)
        pharmacy_id = state_service.get_pharmacy_id(state_dict)

        # Register in local DB
        if phone and pharmacy_id:
            await self.register_identified_person(phone, pharmacy_id, plex_customer, db_session)

        # Generate success state
        preserved = StatePreserver.extract_all(state_dict)
        response_state = {**state_dict, "customer_name": customer_name}
        response_content = await generate_response(
            state=response_state,
            intent="identification_success",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_IDENTIFICATION_VERIFIED),
        )

        # IMPORTANT: **preserved must come FIRST so explicit values can override it
        # Otherwise preserved["identification_step"] would overwrite the None we set
        return {
            **preserved,
            "messages": [{"role": "assistant", "content": response_content}],
            "plex_customer_id": plex_customer.get("id"),
            "plex_customer": plex_customer,
            "customer_name": customer_name,
            "customer_identified": True,
            "is_self": True,
            "identification_step": None,  # Clear identification flow
            "plex_customer_to_confirm": None,  # Clear pending confirmation
            "name_mismatch_count": 0,  # Reset mismatch counter
            "current_menu": "main",
            "next_node": "main_menu_node",
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }


__all__ = ["PersonRegistrationService"]
