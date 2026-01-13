"""
PersonResolutionNode - Thin Orchestrator.

Coordinates the person resolution workflow by delegating
to specialized services and handlers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.agents import BaseAgent
from app.domains.pharmacy.agents.models import StatePreserver
from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    STEP_AWAITING_ACCOUNT_SELECTION,
    STEP_AWAITING_IDENTIFIER,
    STEP_AWAITING_WELCOME,
    STEP_NAME,
)
from app.domains.pharmacy.agents.nodes.person_resolution.factory import (
    PersonResolutionFactory,
)
from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
    RegisteredPersonRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)


class PersonResolutionNode(BaseAgent):
    """
    Entry node that orchestrates person resolution workflow.

    This is a thin coordinator that delegates to:
    - Services: payment extraction, initial resolution, workflow orchestration,
      registration, state management, payment state
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
                from app.database.async_db import create_async_session

                self._db_session = await create_async_session()
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
            payment_amount_extractor = self._factory.get_payment_amount_extractor()  # type: ignore[reportAttributeAccessIssue]
            workflow_orchestrator = self._factory.get_workflow_orchestrator()  # type: ignore[reportAttributeAccessIssue]

            # Load pharmacy config
            state_dict = await state_service.ensure_pharmacy_config(state_dict)

            # CRITICAL: Extract payment_amount from initial message BEFORE any flow
            # This captures "quiero pagar 3000" even before identification
            extracted_amount = payment_amount_extractor.extract_if_valid(message, state_dict)
            if extracted_amount:
                state_dict["payment_amount"] = extracted_amount

            # Check zombie payment
            zombie_result = await payment_service.check_zombie_payment(state_dict)
            if zombie_result:
                return zombie_result

            # Already identified AND not in mid-identification flow?
            # CRITICAL: identification_step=None means no active flow, safe to pass through
            # If identification_step is set, user is MID-FLOW, don't bypass
            identification_step = state_dict.get("identification_step")
            if (
                state_dict.get("customer_identified")
                and state_dict.get("plex_customer_id")
                and identification_step is None
            ):
                logger.debug("Customer already identified, passing through")
                return self._pass_through_identified(state_dict)

            # SAFETY: If customer_identified=True but identification_step is set,
            # state is corrupted (e.g., old session reused). Reset identification.
            if state_dict.get("customer_identified") and identification_step is not None:
                logger.warning(
                    f"Inconsistent state: customer_identified=True but "
                    f"identification_step={identification_step}. Resetting."
                )
                state_dict["customer_identified"] = False
                state_dict["plex_customer_id"] = None
                state_dict["plex_customer"] = None

            # Orchestrate workflow using WorkflowOrchestrator
            if (
                identification_step
                or state_dict.get("awaiting_person_selection")
                or state_dict.get("awaiting_own_or_other")
            ):
                return await workflow_orchestrator.orchestrate(message, state_dict)

            # Route to validation if waiting (LEGACY - only if no new flow step)
            if self._is_legacy_validation_step(state_dict):
                return self._route_to_legacy_validation(state_dict)

            # Initial resolution
            return await self._initial_resolution(message, state_dict)

        except Exception as e:
            logger.error(f"Error in person resolution: {e}", exc_info=True)
            return await self._factory.get_error_handler().handle_error(str(e), state_dict)

    # =========================================================================
    # Delegation Methods
    # =========================================================================

    async def _initial_resolution(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform initial person resolution using InitialResolutionService."""
        state_service = self._factory.get_state_service()
        id_service = self._factory.get_identification_service()

        # Extract organization_id from state for multi-tenant support
        org_id = self._extract_organization_id(state_dict)
        initial_resolution_service = self._factory.get_initial_resolution_service(
            organization_id=org_id
        )

        handlers = {
            "error_handler": self._factory.get_error_handler(),
            "response_builder": self._factory.get_response_builder(),  # type: ignore[reportAttributeAccessIssue]
            "account_selection_handler": self._factory.get_account_selection_handler(),
            "own_other_handler": self._factory.get_own_other_handler(),
            "welcome_handler": self._factory.get_welcome_handler(),
        }

        return await initial_resolution_service.resolve(
            message, state_dict, state_service, id_service, handlers
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _extract_organization_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """Extract organization_id from state for multi-tenant support.

        Args:
            state_dict: Current state dictionary

        Returns:
            Organization UUID or None
        """
        org_id = state_dict.get("organization_id")
        if org_id is None:
            return None
        if isinstance(org_id, UUID):
            return org_id
        try:
            return UUID(str(org_id))
        except (ValueError, TypeError):
            logger.warning(f"Invalid organization_id in state: {org_id}")
            return None

    def _pass_through_identified(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Return pass-through state for already identified customers."""
        preserved = StatePreserver.extract_all(state_dict)
        return {
            "customer_identified": True,
            **preserved,  # Includes pharmacy_name, pharmacy_phone, payment_amount, etc.
        }

    def _is_legacy_validation_step(self, state_dict: dict[str, Any]) -> bool:
        """Check if state has a legacy validation step."""
        step = state_dict.get("validation_step")
        return step is not None and step not in [
            STEP_AWAITING_WELCOME,
            STEP_AWAITING_IDENTIFIER,
            STEP_NAME,
            STEP_AWAITING_ACCOUNT_SELECTION,
        ]

    def _route_to_legacy_validation(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Route to legacy person validation node."""
        return {
            "validation_step": state_dict.get("validation_step"),
            "next_node": "person_validation_node",
        }


__all__ = ["PersonResolutionNode"]
