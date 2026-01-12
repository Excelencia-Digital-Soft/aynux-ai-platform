"""
Person Selection Node - Select from Registered Persons.

Shows a numbered list of registered persons and handles user selection.
Allows selection by:
- Number (1, 2, 3...)
- DNI (partial or full)
- Name (fuzzy matching with LLM)

Also offers option to add a new person.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.agents import BaseAgent
from app.domains.pharmacy.agents.utils.name_matcher import LLMNameMatcher
from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
from app.tasks import TaskRegistry
from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
    get_response_generator,
)
from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
    RegisteredPersonRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)


class PersonSelectionNode(BaseAgent):
    """
    Node for selecting from a list of registered persons.

    Flow:
    1. Display numbered list of persons (name + masked DNI)
    2. Wait for user to select by number, DNI, or name
    3. Validate selection and proceed to debt check
    4. Offer option to add new person
    """

    # Keywords indicating user wants to add a new person
    ADD_NEW_KEYWORDS = [
        "agregar",
        "nueva",
        "nuevo",
        "otra",
        "otro",
        "diferente",
        "registrar",
        "no esta",
        "no está",
        "ninguno",
        "ninguna",
    ]

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        db_session: AsyncSession | None = None,
        config: dict[str, Any] | None = None,
        response_generator: PharmacyResponseGenerator | None = None,
        name_matcher: LLMNameMatcher | None = None,
    ):
        """
        Initialize person selection node.

        Args:
            plex_client: PlexClient instance (not used, for factory compatibility)
            db_session: SQLAlchemy async session for DB access
            config: Node configuration
            response_generator: PharmacyResponseGenerator for LLM-driven responses
            name_matcher: LLMNameMatcher for fuzzy name matching
        """
        super().__init__("person_selection_node", config or {})
        self._plex_client = plex_client  # Stored for potential future use
        self._db_session = db_session
        self._response_generator = response_generator
        self._name_matcher = name_matcher
        self._registered_person_repo: RegisteredPersonRepository | None = None

    def _get_response_generator(self) -> PharmacyResponseGenerator:
        """Get or create response generator."""
        if self._response_generator is None:
            self._response_generator = get_response_generator()
        return self._response_generator

    def _get_name_matcher(self) -> LLMNameMatcher:
        """Get or create name matcher."""
        if self._name_matcher is None:
            self._name_matcher = LLMNameMatcher()
        return self._name_matcher

    async def _get_registered_person_repo(self) -> RegisteredPersonRepository:
        """Get or create registered person repository."""
        if self._registered_person_repo is None:
            if self._db_session is None:
                from app.database.async_db import create_async_session

                self._db_session = await create_async_session()
            self._registered_person_repo = RegisteredPersonRepository(self._db_session)
        return self._registered_person_repo

    def _get_pharmacy_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """Extract pharmacy_id from state."""
        pharmacy_id = state_dict.get("pharmacy_id")
        if pharmacy_id is None:
            return None
        if isinstance(pharmacy_id, UUID):
            return pharmacy_id
        try:
            return UUID(str(pharmacy_id))
        except (ValueError, TypeError):
            return None

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle person selection workflow.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            # First entry - show the list
            if not state_dict.get("selection_list_shown"):
                return await self._format_selection_list(state_dict)

            # Handle user selection
            return await self._handle_selection(message, state_dict)

        except Exception as e:
            logger.error(f"Error in person selection: {e}", exc_info=True)
            return await self._handle_error(str(e), state_dict)

    async def _format_selection_list(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Format the person selection list.

        Args:
            state_dict: Current state

        Returns:
            State updates with formatted list
        """
        registered_persons = state_dict.get("registered_persons", [])
        self_plex_customer = state_dict.get("self_plex_customer")
        include_self = state_dict.get("include_self_in_list", False)

        # Build the list for display
        lines = []
        option_number = 1
        options_map = {}  # Maps option number to person data

        # Add self if applicable
        if include_self and self_plex_customer:
            name = self_plex_customer.get("nombre", "Titular")
            dni_masked = self._mask_dni(self_plex_customer.get("documento", ""))
            lines.append(f"{option_number}. {name} (DNI: {dni_masked}) - Titular")
            options_map[option_number] = {
                "type": "self",
                "plex_customer": self_plex_customer,
            }
            option_number += 1

        # Add registered persons
        for person in registered_persons:
            # Skip self if already added
            if include_self and person.get("is_self"):
                continue

            name = person.get("name", "Sin nombre")
            dni_masked = person.get("dni_masked", "****")
            lines.append(f"{option_number}. {name} (DNI: {dni_masked})")
            options_map[option_number] = {
                "type": "registered",
                "person": person,
            }
            option_number += 1

        # Add option to add new person
        lines.append(f"\n{option_number}. Agregar otra persona")
        options_map[option_number] = {"type": "add_new"}

        # Build state with person_list for LLM
        response_state = {
            **state_dict,
            "person_list": "\n".join(lines),
        }

        response_content = await generate_response(


            state=response_state,


            intent="person_list",


            user_message="",


            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_ACCOUNT_SELECTION),


        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "selection_list_shown": True,
            "awaiting_person_selection": True,
            "selection_options_map": options_map,
            "registered_persons": registered_persons,
            "self_plex_customer": self_plex_customer,
        }

    async def _handle_selection(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle user selection from the list.

        Args:
            message: User message
            state_dict: Current state

        Returns:
            State updates
        """
        options_map = state_dict.get("selection_options_map", {})

        # Check for "add new person" intent
        if self._is_add_new_intent(message):
            return await self._route_to_add_new(state_dict)

        # Try to match by number
        if selection := self._parse_number_selection(message, options_map):
            return await self._process_selection(selection, state_dict)

        # Try to match by DNI
        if dni := self._extract_dni(message):
            if selection := self._find_by_dni(dni, options_map, state_dict):
                return await self._process_selection(selection, state_dict)

        # Try to match by name (LLM fuzzy)
        if selection := await self._match_by_name(message, options_map, state_dict):
            return await self._process_selection(selection, state_dict)

        # Could not match - ask for clarification
        return await self._request_clear_selection(options_map)

    def _is_add_new_intent(self, message: str) -> bool:
        """Check if user wants to add a new person."""
        message_lower = message.lower().strip()
        return any(kw in message_lower for kw in self.ADD_NEW_KEYWORDS)

    def _parse_number_selection(
        self,
        message: str,
        options_map: dict,
    ) -> dict | None:
        """
        Parse number selection from message.

        Args:
            message: User message
            options_map: Mapping of option numbers to data

        Returns:
            Selected option dict or None
        """
        message_stripped = message.strip()

        # Try to extract a number
        match = re.match(r"^(\d+)$", message_stripped)
        if match:
            number = int(match.group(1))
            # Convert string keys to int if needed
            for key, value in options_map.items():
                if int(key) == number:
                    return value

        return None

    def _extract_dni(self, message: str) -> str | None:
        """Extract DNI from message."""
        # Look for 7-8 digit number
        match = re.search(r"\b(\d{7,8})\b", message)
        if match:
            return match.group(1)
        return None

    def _find_by_dni(
        self,
        dni: str,
        options_map: dict,
        state_dict: dict[str, Any],
    ) -> dict | None:
        """
        Find option by DNI.

        Args:
            dni: DNI to search for
            options_map: Mapping of option numbers to data
            state_dict: Current state

        Returns:
            Matching option dict or None
        """
        # Check in registered persons
        for option in options_map.values():
            if option.get("type") == "registered":
                person = option.get("person", {})
                person_dni = person.get("dni", "")
                if person_dni == dni or person_dni.endswith(dni[-4:]):
                    return option

            elif option.get("type") == "self":
                plex_customer = option.get("plex_customer", {})
                customer_dni = plex_customer.get("documento", "")
                if customer_dni == dni or customer_dni.endswith(dni[-4:]):
                    return option

        return None

    async def _match_by_name(
        self,
        message: str,
        options_map: dict,
        state_dict: dict[str, Any],
    ) -> dict | None:
        """
        Match by name using LLM fuzzy matching.

        Args:
            message: User message (potential name)
            options_map: Mapping of option numbers to data
            state_dict: Current state

        Returns:
            Best matching option dict or None
        """
        # Build list of candidates with names
        candidates = []
        for option in options_map.values():
            if option.get("type") == "registered":
                person = option.get("person", {})
                candidates.append({
                    "name": person.get("name", ""),
                    "option": option,
                })
            elif option.get("type") == "self":
                plex_customer = option.get("plex_customer", {})
                candidates.append({
                    "name": plex_customer.get("nombre", ""),
                    "option": option,
                })

        if not candidates:
            return None

        # Use name matcher to find best match
        name_matcher = self._get_name_matcher()
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            result = await name_matcher.compare(message, candidate["name"])
            if result.score > best_score:
                best_score = result.score
                best_match = candidate["option"]

        # Return if above threshold
        if best_score >= 0.7:
            logger.info(f"Name match found with score {best_score:.2f}")
            return best_match

        return None

    async def _process_selection(
        self,
        selection: dict,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process the selected option.

        Args:
            selection: Selected option dict
            state_dict: Current state

        Returns:
            State updates
        """
        selection_type = selection.get("type")

        if selection_type == "add_new":
            return await self._route_to_add_new(state_dict)

        elif selection_type == "self":
            plex_customer = selection.get("plex_customer", {})
            return await self._proceed_with_customer(plex_customer, state_dict, is_self=True)

        elif selection_type == "registered":
            person = selection.get("person", {})
            return await self._proceed_with_registered_person(person, state_dict)

        else:
            logger.warning(f"Unknown selection type: {selection_type}")
            return await self._request_clear_selection(state_dict.get("selection_options_map", {}))

    async def _route_to_add_new(
        self, state_dict: dict[str, Any]  # noqa: ARG002
    ) -> dict[str, Any]:
        """Route to person validation to add a new person."""
        response_content = await generate_response(

            state={},

            intent="add_new_person",

            user_message="",

            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_START_REGISTRATION),

        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "validation_step": "dni",
            "is_new_person_flow": True,
            "awaiting_person_selection": False,
            "selection_list_shown": False,
            "next_node": "person_validation_node",
        }

    async def _proceed_with_customer(
        self,
        plex_customer: dict,
        state_dict: dict[str, Any],
        is_self: bool = False,
    ) -> dict[str, Any]:
        """Proceed with selected PLEX customer to debt check."""
        customer_name = plex_customer.get("nombre", "")

        response_state = {
            **state_dict,
            "customer_name": customer_name,
        }
        response_content = await generate_response(

            state=response_state,

            intent="selection_confirmed",

            user_message="",

            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_ACCOUNT_SELECTED),

        )

        return {
            "plex_customer_id": plex_customer.get("id"),
            "plex_customer": plex_customer,
            "customer_name": customer_name,
            "customer_identified": True,
            "is_self": is_self,
            "awaiting_person_selection": False,
            "selection_list_shown": False,
            "next_node": "debt_check_node",
            "messages": [{"role": "assistant", "content": response_content}],
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }

    async def _proceed_with_registered_person(
        self,
        person: dict,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Proceed with selected registered person.

        Also marks the registration as used (renewing expiration).

        Args:
            person: Registered person dict
            state_dict: Current state

        Returns:
            State updates
        """
        customer_name = person.get("name", "")
        plex_customer_id = person.get("plex_customer_id")
        registration_id = person.get("id")

        # Mark as used (renew expiration)
        if registration_id:
            try:
                repo = await self._get_registered_person_repo()
                await repo.mark_used(UUID(registration_id))
                logger.info(f"Marked registration {registration_id} as used")
            except Exception as e:
                logger.warning(f"Failed to mark registration as used: {e}")

        # Generate response using LLM
        response_state = {
            **state_dict,
            "customer_name": customer_name,
        }
        response_content = await generate_response(

            state=response_state,

            intent="selection_confirmed",

            user_message="",

            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_ACCOUNT_SELECTED),

        )

        return {
            "plex_customer_id": plex_customer_id,
            "plex_customer": {
                "id": plex_customer_id,
                "nombre": customer_name,
                "documento": person.get("dni"),
            },
            "customer_name": customer_name,
            "customer_identified": True,
            "is_self": person.get("is_self", False),
            "active_registered_person_id": registration_id,
            "awaiting_person_selection": False,
            "selection_list_shown": False,
            "next_node": "debt_check_node",
            "messages": [{"role": "assistant", "content": response_content}],
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }

    async def _request_clear_selection(self, options_map: dict) -> dict[str, Any]:
        """Request clearer selection from user."""
        # Build list of valid options
        max_option = max(int(k) for k in options_map.keys()) if options_map else 0

        response_content = await generate_response(


            state={"max_option": str(max_option)},


            intent="unclear_selection",


            user_message="",


            current_task=await get_current_task(TaskRegistry.PHARMACY_PERSON_ACCOUNT_UNCLEAR),


        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "awaiting_person_selection": True,
        }

    def _mask_dni(self, dni: str | None) -> str:
        """Mask DNI for privacy."""
        if not dni:
            return "****"
        return f"***{dni[-4:]}" if len(dni) >= 4 else "****"

    async def _handle_error(
        self, error: str, state_dict: dict[str, Any]  # noqa: ARG002
    ) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Person selection error: {error}")

        response_content = await generate_response(


            state={},


            intent="generic_error",


            user_message="",


            current_task=await get_current_task(TaskRegistry.PHARMACY_ERROR_RETRY),


        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "awaiting_person_selection": True,
        }


__all__ = ["PersonSelectionNode"]
