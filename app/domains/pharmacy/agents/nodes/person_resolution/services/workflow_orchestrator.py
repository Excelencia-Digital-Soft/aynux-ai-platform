"""
Workflow orchestrator service.

Orchestrates main workflow routing and state transitions for person resolution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    Service for orchestrating main workflow routing and state transitions.

    Responsibilities:
    - Coordinate main workflow steps
    - Route messages to appropriate handlers based on state
    - Handle workflow state transitions
    - Diagnose and log workflow state

    This service centralizes workflow orchestration logic, routing
    messages to appropriate handlers based on identification step state.
    """

    def __init__(self, factory: Any):
        self._factory = factory

    async def orchestrate(
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
            State updates from appropriate handler
        """
        from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
            STEP_AWAITING_ACCOUNT_SELECTION,  # noqa: F401
            STEP_AWAITING_IDENTIFIER,  # noqa: F401
            STEP_AWAITING_WELCOME,
            STEP_NAME,  # noqa: F401
        )

        # Route to person selection if waiting
        if state_dict.get("awaiting_person_selection"):
            return {
                "awaiting_person_selection": True,
                "next_node": "person_selection_node",
            }

        # Handle identification flow states (NEW FLOW - takes priority over legacy)
        identification_step = state_dict.get("identification_step")

        # Diagnose workflow state
        self._diagnose_workflow_state(state_dict)

        # Route based on identification step
        result = await self._route_based_on_identification_step(
            message, state_dict, identification_step
        )

        # Handle special case: welcome handler detected DNI and wants to process immediately
        if identification_step == STEP_AWAITING_WELCOME:
            pending_identifier = result.get("pending_identifier_message")
            if pending_identifier:
                logger.info(
                    f"[DIAG] Welcome flow detected DNI, processing immediately: "
                    f"'{pending_identifier[:20]}...'"
                )
                # Remove the pending flag and process the DNI
                result.pop("pending_identifier_message", None)
                # Merge state updates from welcome handler
                updated_state = {**state_dict, **result}
                handler = self._factory.get_identifier_handler()
                return await handler.handle(pending_identifier, updated_state)

        return result

    async def _route_based_on_identification_step(
        self,
        message: str,
        state_dict: dict[str, Any],
        identification_step: str | None,
    ) -> dict[str, Any]:
        """
        Route message to appropriate handler based on identification step.

        Args:
            message: User message
            state_dict: Current state dictionary
            identification_step: Current identification step

        Returns:
            State updates from handler
        """
        from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
            STEP_AWAITING_ACCOUNT_SELECTION,  # noqa: F401
            STEP_AWAITING_IDENTIFIER,  # noqa: F401
            STEP_AWAITING_WELCOME,
            STEP_NAME,  # noqa: F401
        )

        if identification_step == STEP_AWAITING_WELCOME:
            handler = self._factory.get_welcome_handler()
            return await handler.handle_response(message, state_dict)

        if identification_step == STEP_AWAITING_IDENTIFIER:
            return await self._handle_identifier_input(message, state_dict)

        if identification_step == STEP_NAME:
            return await self._handle_name_verification(message, state_dict)

        if identification_step == STEP_AWAITING_ACCOUNT_SELECTION:
            return await self._handle_account_selection(message, state_dict)

        # Handle own/other decision
        if state_dict.get("awaiting_own_or_other"):
            return await self._handle_own_or_other(message, state_dict)

        # Route to validation if waiting (LEGACY - only if no new flow step)
        if self._is_legacy_validation_step(state_dict):
            return self._route_to_legacy_validation(state_dict)

        # Should not reach here - initial resolution should be called first
        logger.warning("No routing decision made, returning empty state")
        return {}

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

        # Complete identification if DNI + name were provided and matched
        if result.get("identification_complete"):
            registration_service = self._factory.get_person_registration_service()
            return await registration_service.complete_registration_flow(
                result.get("plex_customer_verified", {}), state_dict
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
            registration_service = self._factory.get_person_registration_service()
            return await registration_service.complete_registration_flow(
                result.get("plex_customer_verified", {}), state_dict
            )

        return result

    async def _handle_account_selection(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Delegate account selection handling to AccountSelectionHandler."""
        handler = self._factory.get_account_selection_handler()
        result = await handler.handle_selection(message, state_dict)

        # If an existing account was selected, renew its expiration
        selected_registration_id = result.get("_selected_registration_id")
        if selected_registration_id and result.get("customer_identified"):
            try:
                from uuid import UUID

                node_import = __import__(
                    "app.domains.pharmacy.agents.nodes.person_resolution.node",
                    fromlist=["PersonResolutionNode"],
                )
                node = node_import.PersonResolutionNode.__new__(
                    node_import.PersonResolutionNode
                )
                node._db_session = self._factory._db_session

                from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
                    RegisteredPersonRepository,
                )

                db_session = self._factory._db_session
                if db_session is None:
                    raise RuntimeError("DB session not available for registration renewal.")

                from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
                    RegisteredPersonRepository,
                )

                repo = RegisteredPersonRepository(db_session)
                await repo.mark_used(UUID(str(selected_registration_id)))
                logger.info(f"Renewed expiration for registration {selected_registration_id}")
            except Exception as e:
                logger.warning(f"Failed to renew registration expiration: {e}")

        # Remove internal field before returning
        result.pop("_selected_registration_id", None)
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
            response_builder = self._factory.get_response_builder()
            plex_customer = result.get("self_plex_customer", {})
            return await response_builder.build_proceed_with_customer_state(
                plex_customer, state_dict, is_self=True
            )

        if result.get("decision") == "other":
            return await self._route_to_validation(state_dict, is_for_other=True)

        return result

    def _diagnose_workflow_state(
        self,
        state_dict: dict[str, Any],
    ) -> None:
        """
        Log diagnostic information about workflow state.

        Args:
            state_dict: Current state dictionary
        """
        logger.info(
            f"[DIAG] PersonResolution: "
            f"identification_step={state_dict.get('identification_step')}, "
            f"customer_identified={state_dict.get('customer_identified')}, "
            f"plex_customer_to_confirm={bool(state_dict.get('plex_customer_to_confirm'))}, "
            f"validation_step={state_dict.get('validation_step')}"
        )

    def _is_legacy_validation_step(self, state_dict: dict[str, Any]) -> bool:
        """
        Check if state has a legacy validation step.

        Args:
            state_dict: Current state dictionary

        Returns:
            True if legacy validation step is present
        """
        from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
            STEP_AWAITING_ACCOUNT_SELECTION,
            STEP_AWAITING_IDENTIFIER,
            STEP_AWAITING_WELCOME,
            STEP_NAME,
        )

        step = state_dict.get("validation_step")
        return step is not None and step not in [
            STEP_AWAITING_WELCOME,
            STEP_AWAITING_IDENTIFIER,
            STEP_NAME,
            STEP_AWAITING_ACCOUNT_SELECTION,
        ]

    def _route_to_legacy_validation(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Route to legacy person validation node.

        Args:
            state_dict: Current state dictionary

        Returns:
            State updates for validation routing
        """
        return {
            "validation_step": state_dict.get("validation_step"),
            "next_node": "person_validation_node",
        }

    async def _route_to_validation(
        self,
        state_dict: dict[str, Any],
        is_for_other: bool = False,
    ) -> dict[str, Any]:
        """
        Route to person validation node.

        Args:
            state_dict: Current state dictionary
            is_for_other: Whether querying for another person

        Returns:
            State updates for validation routing
        """
        response_builder = self._factory.get_response_builder()
        return await response_builder.build_validation_request_state(
            state_dict, is_for_other=is_for_other
        )


__all__ = ["WorkflowOrchestrator"]
