"""
Initial resolution service.

Handles initial person resolution and routing decisions for new users.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.db.tenancy.registered_person import RegisteredPerson  # noqa: F401

logger = logging.getLogger(__name__)


class InitialResolutionService:
    """
    Service for initial person resolution and routing decisions.

    Responsibilities:
    - Coordinate initial resolution flow
    - Detect info queries (non-auth required)
    - Detect service intents (auth required)
    - Check local DB and PLEX for existing users
    - Route to appropriate flow based on user state:
      - Existing registrations → account selection
      - PLEX match only → own/other decision
      - Service intent → identifier request
      - New user → welcome message

    This service handles the complex routing decisions for new users
    entering the person resolution flow.
    """

    def __init__(
        self,
        db_session: AsyncSession | None = None,
        organization_id: UUID | None = None,
    ):
        self._db_session = db_session
        self._organization_id = organization_id
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
                logger.debug("Created async session for InitialResolutionService")

            self._registered_person_repo = RegisteredPersonRepository(self._db_session)

        return self._registered_person_repo

    async def resolve(
        self,
        message: str,
        state_dict: dict[str, Any],
        state_service: Any,
        id_service: Any,
        handlers: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Perform initial person resolution and routing.

        Args:
            message: User message
            state_dict: Current state dictionary
            state_service: StateManagementService instance
            id_service: PersonIdentificationService instance
            handlers: Dictionary of flow handlers

        Returns:
            State updates with routing decision
        """
        phone = state_service.extract_phone(state_dict)
        pharmacy_id = state_service.get_pharmacy_id(state_dict)

        if not phone or not pharmacy_id:
            from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
            from app.tasks import TaskRegistry

            if not phone:
                return await handlers["error_handler"].handle_no_phone(
                    message, state_dict
                )
            return await handlers["error_handler"].handle_no_pharmacy(
                message, state_dict
            )

        logger.info(f"Resolving person for phone: {phone}, pharmacy: {pharmacy_id}")

        # PRIORITY: Check if message is an info_query (doesn't require identification)
        org_id = self._get_organization_id(state_dict)
        if await self._is_info_query(message, org_id):
            logger.info(
                f"Info query detected: '{message[:50]}...', "
                "routing to info handler without identification"
            )
            response_builder = handlers["response_builder"]
            return await response_builder.build_info_query_state(state_dict)

        # Check local DB and PLEX
        registered_persons = await self._check_existing_registrations(phone, pharmacy_id)
        plex_customer = await self._check_plex_match(phone, id_service)

        has_plex_match = plex_customer is not None
        has_registrations = len(registered_persons) > 0

        logger.info(
            f"Resolution status: plex_match={has_plex_match}, "
            f"registrations={len(registered_persons)}"
        )

        # If user has existing registrations, offer account selection directly
        if has_registrations:
            logger.info(
                f"User has {len(registered_persons)} existing registrations, "
                "offering account selection"
            )
            handler = handlers["account_selection_handler"]
            return await handler.offer_accounts(registered_persons, state_dict)

        # If phone matches a PLEX customer but no registrations, ask own/other
        if has_plex_match:
            handler = handlers["own_other_handler"]
            return await handler.ask(plex_customer, state_dict)

        # PRIORITY: Check if message is a service intent (requires identification)
        service_intent = await self._detect_service_intent(message, state_dict, org_id)
        if service_intent:
            logger.info(
                f"Service intent '{service_intent}' detected from new user, "
                "skipping welcome and requesting identifier directly"
            )
            response_builder = handlers["response_builder"]
            return await response_builder.build_identifier_request_state(
                state_dict, pending_flow=service_intent
            )

        # Check if user has a pending_flow that requires identification
        pending_flow = state_dict.get("pending_flow")
        if await self._flow_requires_auth(pending_flow, org_id):
            logger.info(
                f"New user with pending_flow='{pending_flow}', "
                "skipping welcome and requesting identifier directly"
            )
            response_builder = handlers["response_builder"]
            return await response_builder.build_identifier_request_state(state_dict)

        # New user - show welcome message
        handler = handlers["welcome_handler"]
        return await handler.show_welcome_message(state_dict)

    async def _check_existing_registrations(
        self,
        phone: str,
        pharmacy_id: UUID,
    ) -> list[RegisteredPerson]:
        """
        Check for existing registrations by phone and pharmacy.

        Args:
            phone: Phone number to search
            pharmacy_id: Pharmacy UUID

        Returns:
            List of registered persons
        """
        repo = await self._get_registered_person_repo()
        return await repo.get_valid_by_phone(phone, pharmacy_id)

    async def _check_plex_match(
        self,
        phone: str,
        id_service: Any,
    ) -> dict[str, Any] | None:
        """
        Check for PLEX customer match by phone.

        Args:
            phone: Phone number to search
            id_service: PersonIdentificationService instance

        Returns:
            PLEX customer data or None
        """
        return await id_service.search_by_phone(phone)

    async def _is_info_query(
        self,
        message: str,
        org_id: UUID | None,
    ) -> bool:
        """
        Check if message is an info query (no auth required).

        Args:
            message: User message
            org_id: Organization UUID

        Returns:
            True if message is an info query
        """
        from app.domains.pharmacy.agents.nodes.person_resolution.services import info_query_detector

        if not message:
            return False

        return await info_query_detector.is_info_query(
            message, self._db_session, org_id
        )

    async def _detect_service_intent(
        self,
        message: str,
        state_dict: dict[str, Any],
        org_id: UUID | None,
    ) -> str | None:
        """
        Detect if message contains a service intent requiring identification.

        Args:
            message: User message
            state_dict: Current state dictionary
            org_id: Organization UUID

        Returns:
            Intent key if service intent detected, None otherwise
        """
        from app.domains.pharmacy.agents.intent_analyzer import get_pharmacy_intent_analyzer
        from app.domains.pharmacy.agents.nodes.person_resolution.services import auth_requirement_service

        if not message:
            return None

        analyzer = get_pharmacy_intent_analyzer(db=self._db_session)
        result = await analyzer.analyze(
            message=message,
            context=state_dict,
            organization_id=org_id,
        )

        requires_auth = await auth_requirement_service.intent_requires_auth(
            result.intent, self._db_session, org_id
        )

        if requires_auth and result.confidence >= 0.5:
            logger.debug(
                f"Detected service intent '{result.intent}' "
                f"(confidence={result.confidence:.2f}) requires auth"
            )
            return result.intent

        return None

    async def _flow_requires_auth(
        self,
        flow: str | None,
        org_id: UUID | None,
    ) -> bool:
        """
        Check if a flow requires authentication.

        Args:
            flow: Flow name to check
            org_id: Organization UUID

        Returns:
            True if flow requires authentication
        """
        from app.domains.pharmacy.agents.nodes.person_resolution.services import auth_requirement_service

        if not flow:
            return False

        return await auth_requirement_service.flow_requires_auth(
            flow, self._db_session, org_id
        )

    def _get_organization_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """
        Extract organization_id from state.

        Args:
            state_dict: Current state dictionary

        Returns:
            Organization UUID or None
        """
        org_id = state_dict.get("organization_id")
        if org_id is None:
            return self._organization_id
        if isinstance(org_id, UUID):
            return org_id
        try:
            return UUID(str(org_id))
        except (ValueError, TypeError):
            logger.warning(f"Invalid organization_id in state: {org_id}")
            return self._organization_id


__all__ = ["InitialResolutionService"]
