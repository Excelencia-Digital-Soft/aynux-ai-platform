"""
Response builder service.

Builds response states with preserved context for person resolution flow.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ResponseBuilder:
    """
    Service for building response states with proper context preservation.

    Responsibilities:
    - Generate response states with preserved context
    - Build states for node transitions
    - Handle pharmacy config preservation
    - Generate responses using ResponseGenerator

    This service centralizes response state building logic, ensuring
    consistent state preservation across the person resolution flow.
    """

    def __init__(self, db_session: AsyncSession | None = None):
        self._db_session = db_session

    async def build_success_state(
        self,
        state_dict: dict[str, Any],
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build a success response state with preserved context.

        Args:
            state_dict: Current state dictionary
            updates: Additional state updates to apply

        Returns:
            Complete response state with preserved context
        """
        from app.domains.pharmacy.agents.models import StatePreserver

        preserved = StatePreserver.extract_all(state_dict)
        return {
            **updates,
            **preserved,
        }

    async def build_proceed_with_customer_state(
        self,
        plex_customer: dict[str, Any],
        state_dict: dict[str, Any],
        is_self: bool = False,
    ) -> dict[str, Any]:
        """
        Build state to proceed with identified customer to debt check.

        Args:
            plex_customer: PLEX customer data
            state_dict: Current state dictionary
            is_self: Whether customer is the self user

        Returns:
            Complete state for proceeding to debt check node
        """
        from app.domains.pharmacy.agents.models import StatePreserver
        from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
        from app.tasks import TaskRegistry

        preserved = StatePreserver.extract_all(state_dict)
        customer_name = plex_customer.get("nombre", "")

        response_state = {**state_dict, "customer_name": customer_name}
        response_content = await generate_response(
            state=response_state,
            intent="proceed_with_customer",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_ACCOUNT_SELECTED),
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
            **preserved,
        }

    async def build_validation_request_state(
        self,
        state_dict: dict[str, Any],
        is_for_other: bool = False,
    ) -> dict[str, Any]:
        """
        Build state to request DNI validation.

        Args:
            state_dict: Current state dictionary
            is_for_other: Whether querying for another person

        Returns:
            Complete state for validation request
        """
        from app.domains.pharmacy.agents.models import StatePreserver
        from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
        from app.tasks import TaskRegistry

        preserved = StatePreserver.extract_all(state_dict)

        if is_for_other:
            intent = "request_dni_for_other"
            task = await get_current_task(TaskRegistry.PHARMACY_PERSON_REQUEST_OTHER_DNI)
        else:
            intent = "request_dni_welcome"
            task = await get_current_task(TaskRegistry.PHARMACY_IDENTIFICATION_REQUEST_IDENTIFIER)

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
            **preserved,
        }

    async def build_identifier_request_state(
        self,
        state_dict: dict[str, Any],
        pending_flow: str | None = None,
    ) -> dict[str, Any]:
        """
        Build state to request identifier (DNI + name).

        Args:
            state_dict: Current state dictionary
            pending_flow: Optional pending flow to remember

        Returns:
            Complete state for identifier request
        """
        from app.domains.pharmacy.agents.models import StatePreserver
        from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
        from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
            STEP_AWAITING_IDENTIFIER,
        )
        from app.tasks import TaskRegistry

        response_content = await generate_response(
            state=state_dict,
            intent="request_identifier",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_REQUEST_IDENTIFIER),
        )

        result = {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_IDENTIFIER,
            "identification_retries": 0,
            **StatePreserver.extract_all(state_dict),
        }

        if pending_flow:
            result["pending_flow"] = pending_flow

        return result

    async def build_info_query_state(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build state to route info queries without identification.

        Args:
            state_dict: Current state dictionary

        Returns:
            Complete state for info query routing
        """
        from app.domains.pharmacy.agents.models import StatePreserver

        return {
            "pharmacy_intent_type": "info_query",
            "next_node": "router",
            **StatePreserver.extract_all(state_dict),
        }

    async def build_welcome_request_state(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build state to show welcome message to new users.

        Args:
            state_dict: Current state dictionary

        Returns:
            Complete state for welcome message
        """
        from app.domains.pharmacy.agents.models import StatePreserver

        return {
            **StatePreserver.extract_all(state_dict),
        }


__all__ = ["ResponseBuilder"]
