"""Handler for account selection flow.

Handles selection of existing registered accounts or new account registration
for returning users who already have validated DNIs associated with their phone.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    STEP_AWAITING_ACCOUNT_SELECTION,
    STEP_AWAITING_IDENTIFIER,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.base_handler import (
    PersonResolutionBaseHandler,
)
from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
from app.tasks import TaskRegistry

if TYPE_CHECKING:
    from app.models.db.tenancy.registered_person import RegisteredPerson


class AccountSelectionHandler(PersonResolutionBaseHandler):
    """
    Handler for account selection when user has existing registrations.

    Responsibilities:
    - Show list of existing accounts (names only, no DNI for privacy)
    - Handle selection of existing account
    - Route to new account registration if requested
    """

    async def offer_accounts(
        self,
        registrations: list[RegisteredPerson],
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Show list of existing accounts for selection.

        Args:
            registrations: List of valid RegisteredPerson entities
            state_dict: Current state

        Returns:
            State updates with account list message
        """
        # Build account list showing only names (no DNI for privacy)
        account_lines = []
        for i, reg in enumerate(registrations, start=1):
            account_lines.append(f"{i}) {reg.name}")

        # Add option for new account
        new_option_num = len(registrations) + 1
        account_lines.append(f"{new_option_num}) Usar otra cuenta")

        account_list = "\n".join(account_lines)

        # Generate response with account list
        response_state = {
            **state_dict,
            "account_list": account_list,
        }

        response_content = await generate_response(
            state=response_state,
            intent="offer_existing_accounts",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_OFFER_EXISTING_ACCOUNTS),
        )

        return {
            **self._preserve_all(state_dict),
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_ACCOUNT_SELECTION,
            "registered_accounts_for_selection": [r.to_dict() for r in registrations],
            "account_count": len(registrations),
        }

    async def handle_selection(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process user's account selection.

        Uses database-driven patterns for selection detection.

        Args:
            message: User's selection (number or "nueva")
            state_dict: Current state

        Returns:
            State updates based on selection
        """
        message_clean = message.strip().lower()
        registrations_data = state_dict.get("registered_accounts_for_selection", [])
        account_count = state_dict.get("account_count", 0)

        if not registrations_data:
            self.logger.warning("No registrations in state for selection")
            return await self._route_to_identifier(state_dict)

        # Check for "nueva" or "new" option (DB-driven patterns)
        if await self._match_confirmation_pattern(
            message_clean, "account_selection_new", state_dict
        ):
            return await self._route_to_identifier(state_dict)

        # Check for "existing account" keywords (DB-driven patterns)
        if await self._match_confirmation_pattern(
            message_clean, "account_selection_existing", state_dict
        ):
            selected_reg = registrations_data[0]
            return await self._select_existing_account(selected_reg, state_dict)

        # Try to extract number selection
        selection = self._extract_number_selection(message_clean)

        if selection is not None:
            # Check if it's the "new account" option
            new_option_num = account_count + 1
            if selection == new_option_num:
                return await self._route_to_identifier(state_dict)

            # Check if valid existing account selection
            if 1 <= selection <= account_count:
                selected_reg = registrations_data[selection - 1]
                return await self._select_existing_account(selected_reg, state_dict)

        # Check for name match
        name_match = self._find_by_name(message_clean, registrations_data)
        if name_match:
            return await self._select_existing_account(name_match, state_dict)

        # If only one account and user gives affirmative response (DB-driven)
        if account_count == 1 and await self._match_confirmation_pattern(
            message_clean, "affirmative_response", state_dict
        ):
            selected_reg = registrations_data[0]
            return await self._select_existing_account(selected_reg, state_dict)

        # Invalid selection
        return await self._invalid_selection(state_dict)

    def _extract_number_selection(self, message: str) -> int | None:
        """Extract number from message if present."""
        # Try direct number
        if message.isdigit():
            return int(message)

        # Try to find number in text like "opcion 2" or "el 2"
        match = re.search(r"\b(\d+)\b", message)
        if match:
            return int(match.group(1))

        return None

    def _find_by_name(
        self,
        message: str,
        registrations: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Find registration by name match."""
        message_normalized = message.lower().strip()

        for reg in registrations:
            reg_name = reg.get("name", "").lower()
            # Check if message contains significant part of the name
            name_parts = reg_name.split()
            for part in name_parts:
                if len(part) >= 3 and part in message_normalized:
                    return reg

        return None

    async def _select_existing_account(
        self,
        registration: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Complete selection with existing account.

        Goes directly to debt check without re-validation.

        Args:
            registration: Selected registration data
            state_dict: Current state

        Returns:
            State updates to proceed with selected account
        """
        customer_name = registration.get("name", "")
        plex_customer_id = registration.get("plex_customer_id")

        self.logger.info(
            f"Selected existing account: {customer_name} (plex_id={plex_customer_id})"
        )

        # Generate confirmation message
        response_state = {**state_dict, "customer_name": customer_name}
        response_content = await generate_response(
            state=response_state,
            intent="proceed_with_customer",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_ACCOUNT_SELECTED),
        )

        return {
            **self._preserve_all(state_dict),
            "messages": [{"role": "assistant", "content": response_content}],
            "plex_customer_id": plex_customer_id,
            "plex_customer": {
                "id": plex_customer_id,
                "nombre": customer_name,
                "documento": registration.get("dni"),
            },
            "customer_name": customer_name,
            "customer_identified": True,
            "is_self": registration.get("is_self", False),
            "identification_step": None,
            "registered_accounts_for_selection": None,
            "account_count": None,
            "next_node": "debt_check_node",
            # Internal field for node to renew expiration
            "_selected_registration_id": registration.get("id"),
        }

    async def _route_to_identifier(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Route to identifier input for new account registration.

        Args:
            state_dict: Current state

        Returns:
            State updates to request identifier
        """
        response_content = await generate_response(
            state=state_dict,
            intent="request_identifier",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_REQUEST_IDENTIFIER),
        )

        return {
            **self._preserve_all(state_dict),
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_IDENTIFIER,
            "identification_retries": 0,
            "registered_accounts_for_selection": None,
            "account_count": None,
        }

    async def _invalid_selection(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle invalid selection response.

        Args:
            state_dict: Current state

        Returns:
            State updates asking for valid selection
        """
        response_content = await generate_response(
            state=state_dict,
            intent="invalid_account_selection",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_ACCOUNT_INVALID),
        )

        return {
            **self._preserve_all(state_dict),
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_ACCOUNT_SELECTION,
            # Preserve account selection fields (not in StatePreserver since they're temporary)
            "registered_accounts_for_selection": state_dict.get("registered_accounts_for_selection"),
            "account_count": state_dict.get("account_count"),
        }


__all__ = ["AccountSelectionHandler"]
