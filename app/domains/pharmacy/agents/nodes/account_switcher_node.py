# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Account switcher node for pharmacy V2 graph.
#              Handles selection from registered accounts and adding new persons.
# Tenant-Aware: Yes - loads templates and config per organization_id.
# ============================================================================
"""
Account Switcher Node - V2 Account Selection Node.

Handles selection from registered accounts and adding new persons.
Migrated from person_selection_node.py with simplified state management.

Uses V2 state fields: registered_accounts, current_account_id, awaiting_account_selection.

All messages and keywords are loaded from database/YAML templates (zero hardcoding).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from app.domains.pharmacy.agents.utils.account_templates import AccountTemplateKeys, AccountTemplates
from app.domains.pharmacy.agents.utils.config_loader import PharmacyConfigLoader
from app.domains.pharmacy.agents.utils.keyword_matcher import KeywordMatcher
from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor
from app.domains.pharmacy.agents.utils.name_matcher import LLMNameMatcher

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2
    from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
        RegisteredPersonRepository,
    )

logger = logging.getLogger(__name__)


class AccountSwitcherService:
    """
    Service for account switching operations.

    Responsibilities:
    - Load registered accounts for phone
    - Handle selection by number, DNI, or name
    - Manage account switching
    """

    def __init__(self, db_session: "AsyncSession | None" = None):
        self._db_session = db_session
        self._name_matcher: LLMNameMatcher | None = None
        self._repo: "RegisteredPersonRepository | None" = None

    async def _get_repo(self) -> "RegisteredPersonRepository":
        """Get or create registered person repository."""
        if self._repo is None:
            from app.database.async_db import get_async_db_context
            from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
                RegisteredPersonRepository,
            )

            if self._db_session is None:
                # Will need to create session per operation
                async with get_async_db_context() as session:
                    self._db_session = session
                    self._repo = RegisteredPersonRepository(session)
            else:
                self._repo = RegisteredPersonRepository(self._db_session)

        return self._repo

    def _get_name_matcher(self) -> LLMNameMatcher:
        """Get or create name matcher."""
        if self._name_matcher is None:
            self._name_matcher = LLMNameMatcher()
        return self._name_matcher

    async def load_registered_accounts(
        self,
        phone: str,
        pharmacy_id: str | UUID | None,
    ) -> list[dict[str, Any]]:
        """
        Load registered accounts for a phone number.

        Args:
            phone: Phone number
            pharmacy_id: Pharmacy ID

        Returns:
            List of registered account dicts
        """
        if not phone or not pharmacy_id:
            return []

        try:
            from app.database.async_db import get_async_db_context
            from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
                RegisteredPersonRepository,
            )

            pharmacy_uuid = UUID(str(pharmacy_id)) if not isinstance(pharmacy_id, UUID) else pharmacy_id

            async with get_async_db_context() as session:
                repo = RegisteredPersonRepository(session)
                accounts = await repo.get_valid_by_phone(phone, pharmacy_uuid)

            return [
                {
                    "id": str(a.id),
                    "name": a.name,
                    "dni": a.dni,
                    "dni_masked": self._mask_dni(str(a.dni) if a.dni is not None else None),
                    "plex_customer_id": a.plex_customer_id,
                    "is_self": a.is_self,
                }
                for a in accounts
            ]

        except Exception as e:
            logger.error(f"Error loading registered accounts: {e}")
            return []

    async def mark_account_used(self, account_id: str) -> None:
        """Mark an account as used (renews expiration)."""
        try:
            from app.database.async_db import get_async_db_context
            from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
                RegisteredPersonRepository,
            )

            async with get_async_db_context() as session:
                repo = RegisteredPersonRepository(session)
                await repo.mark_used(UUID(account_id))
                logger.info(f"Marked account {account_id} as used")

        except Exception as e:
            logger.warning(f"Failed to mark account as used: {e}")

    def parse_number_selection(
        self,
        message: str,
        options_count: int,
    ) -> int | None:
        """Parse number selection from message."""
        match = re.match(r"^(\d+)$", message.strip())
        if match:
            number = int(match.group(1))
            if 1 <= number <= options_count:
                return number
        return None

    def extract_dni(self, message: str) -> str | None:
        """Extract DNI from message."""
        match = re.search(r"\b(\d{7,8})\b", message)
        return match.group(1) if match else None

    async def match_by_name(
        self,
        message: str,
        accounts: list[dict[str, Any]],
        threshold: float = 0.7,
    ) -> dict[str, Any] | None:
        """
        Match account by name using LLM fuzzy matching.

        Args:
            message: User message to match
            accounts: List of accounts to search
            threshold: Minimum score for a match (loaded from DB config)

        Returns:
            Best matching account or None if no match above threshold
        """
        if not accounts:
            return None

        name_matcher = self._get_name_matcher()
        best_match = None
        best_score = 0.0

        for account in accounts:
            result = await name_matcher.compare(message, account["name"])
            if result.score > best_score:
                best_score = result.score
                best_match = account

        if best_score >= threshold:
            logger.info(f"Name match found with score {best_score:.2f} (threshold: {threshold})")
            return best_match

        return None

    @staticmethod
    def _mask_dni(dni: str | None) -> str:
        """Mask DNI for privacy."""
        if not dni:
            return "****"
        return f"***{dni[-4:]}" if len(dni) >= 4 else "****"


async def account_switcher_node(
    state: "PharmacyStateV2",
    config: RunnableConfig | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """
    Account switcher node - handles account selection.

    Flow:
    1. If awaiting_account_selection: handle selection input
    2. If no accounts loaded: load and show list
    3. Handle selection by number, DNI, or name
    4. Allow adding new person

    Args:
        state: Current conversation state
        config: Optional configuration

    Returns:
        State updates
    """
    service = AccountSwitcherService()

    # Get organization_id for multi-tenant support
    org_id_raw = state.get("organization_id")
    organization_id: UUID | None = None
    if org_id_raw and isinstance(org_id_raw, str):
        organization_id = UUID(org_id_raw)
    elif isinstance(org_id_raw, UUID):
        organization_id = org_id_raw

    # Extract message
    message = MessageExtractor.extract_last_human_message(state) or ""
    awaiting = state.get("awaiting_input")

    # Handle own/other selection
    if awaiting == "own_or_other":
        return await _handle_own_or_other(message, state, organization_id)

    # Handle account selection
    if awaiting == "account_selection" or state.get("awaiting_account_selection"):
        return await _handle_selection(message, state, service, organization_id)

    # Check if we need to show own/other question first
    accounts = state.get("registered_accounts")
    if accounts is None:
        # Load accounts
        phone = state.get("user_phone") or ""
        pharmacy_id = state.get("pharmacy_id")
        accounts = await service.load_registered_accounts(phone, pharmacy_id)

        if not accounts:
            # No registered accounts - go to auth
            template = await AccountTemplates.get(AccountTemplateKeys.NO_REGISTERED_ACCOUNTS)
            return {
                "messages": [{"role": "assistant", "content": template}],
                "current_node": "account_switcher",
                "registered_accounts": [],
                "awaiting_input": "dni",
                "next_node": "auth_plex",
            }

        # If only one account, auto-select
        if len(accounts) == 1:
            return await _select_account(accounts[0], state, service)

    # Multiple accounts - show selection
    return await _show_account_list(accounts or [], state)


async def _handle_own_or_other(
    message: str,
    state: "PharmacyStateV2",  # noqa: ARG001
    organization_id: UUID | None,
) -> dict[str, Any]:
    """Handle own/other debt selection."""
    # Check for "own" indicators using DB keywords
    if organization_id and await KeywordMatcher.matches_intent(None, organization_id, message, "account_own_selection"):
        template = await AccountTemplates.get(AccountTemplateKeys.QUERYING_OWN_DEBT)
        return {
            "messages": [{"role": "assistant", "content": template}],
            "current_node": "account_switcher",
            "is_self": True,
            "awaiting_input": None,
            "next_node": "debt_manager",
        }

    # Check for "other" indicators using DB keywords
    if organization_id and await KeywordMatcher.matches_intent(
        None, organization_id, message, "account_other_selection"
    ):
        # Show account list for other person
        return {
            "current_node": "account_switcher",
            "is_self": False,
            "awaiting_input": "account_selection",
            "awaiting_account_selection": True,
        }

    # Unclear response
    template = await AccountTemplates.get(AccountTemplateKeys.OWN_OR_OTHER_PROMPT)
    return {
        "messages": [{"role": "assistant", "content": template}],
        "current_node": "account_switcher",
        "awaiting_input": "own_or_other",
    }


async def _handle_selection(
    message: str,
    state: "PharmacyStateV2",
    service: AccountSwitcherService,
    organization_id: UUID | None,
) -> dict[str, Any]:
    """Handle account selection input."""
    accounts = state.get("registered_accounts") or []

    # Check for add new intent using DB keywords
    if organization_id and await KeywordMatcher.matches_intent(None, organization_id, message, "account_add_new"):
        template = await AccountTemplates.get(AccountTemplateKeys.ADD_PERSON_DNI_REQUEST)
        return {
            "messages": [{"role": "assistant", "content": template}],
            "current_node": "account_switcher",
            "awaiting_input": "dni",
            "awaiting_account_selection": False,
            "next_node": "auth_plex",
        }

    # Add 1 to options_count for "add new" option
    options_count = len(accounts) + 1

    # Check for "add new" selection (last option)
    if message.strip() == str(options_count):
        template = await AccountTemplates.get(AccountTemplateKeys.ADD_PERSON_DNI_REQUEST)
        return {
            "messages": [{"role": "assistant", "content": template}],
            "current_node": "account_switcher",
            "awaiting_input": "dni",
            "awaiting_account_selection": False,
            "next_node": "auth_plex",
        }

    # Try number selection
    number = service.parse_number_selection(message, len(accounts))
    if number is not None:
        account = accounts[number - 1]
        return await _select_account(account, state, service)

    # Try DNI match
    dni = service.extract_dni(message)
    if dni:
        for account in accounts:
            if account.get("dni") == dni or account.get("dni", "").endswith(dni[-4:]):
                return await _select_account(account, state, service)

    # Try name match with configurable threshold
    threshold = await PharmacyConfigLoader.get_name_match_threshold(None, organization_id) if organization_id else 0.7
    matched = await service.match_by_name(message, accounts, threshold=threshold)
    if matched:
        return await _select_account(matched, state, service)

    # No match - show list again with error
    error_template = await AccountTemplates.get(AccountTemplateKeys.ACCOUNT_SELECTION_UNCLEAR)
    return await _show_account_list(accounts, state, error_message=error_template)


async def _select_account(
    account: dict[str, Any],
    state: "PharmacyStateV2",  # noqa: ARG001
    service: AccountSwitcherService,
) -> dict[str, Any]:
    """Select an account and proceed to debt check."""
    # Mark as used
    account_id = account.get("id")
    if account_id:
        await service.mark_account_used(account_id)

    customer_name = account.get("name", "Cliente")

    # Get template and render with customer_name
    template = await AccountTemplates.get(AccountTemplateKeys.ACCOUNT_SELECTION_CONFIRMED)
    message = AccountTemplates.render(template, customer_name=customer_name)

    return {
        "messages": [{"role": "assistant", "content": message}],
        "current_node": "account_switcher",
        # Account data
        "current_account_id": account.get("id"),
        "plex_user_id": account.get("plex_customer_id"),
        "plex_customer": {
            "id": account.get("plex_customer_id"),
            "nombre": customer_name,
            "documento": account.get("dni"),
        },
        "customer_name": customer_name,
        "is_authenticated": True,
        "is_self": account.get("is_self", False),
        # Clear selection state
        "awaiting_account_selection": False,
        "awaiting_input": None,
        # Route to debt check
        "next_node": "debt_manager",
    }


async def _show_account_list(
    accounts: list[dict[str, Any]],
    state: "PharmacyStateV2",  # noqa: ARG001
    error_message: str | None = None,
) -> dict[str, Any]:
    """Show account selection list."""
    lines = []

    if error_message:
        lines.append(f"_{error_message}_\n")

    # Header from template
    header = await AccountTemplates.get(AccountTemplateKeys.ACCOUNT_LIST_HEADER)
    lines.append(f"{header}\n")

    # Account list
    for i, account in enumerate(accounts, 1):
        name = account.get("name", "Sin nombre")
        dni_masked = account.get("dni_masked", "****")
        is_self = " (Titular)" if account.get("is_self") else ""
        lines.append(f"{i}. {name} (DNI: {dni_masked}){is_self}")

    # Add option to add new from template
    add_option = await AccountTemplates.get(AccountTemplateKeys.ACCOUNT_LIST_ADD_OPTION)
    add_option_rendered = AccountTemplates.render(add_option, number=len(accounts) + 1)
    lines.append(f"\n{add_option_rendered}")

    # Footer from template
    footer = await AccountTemplates.get(AccountTemplateKeys.ACCOUNT_LIST_FOOTER)
    lines.append(f"\n{footer}")

    return {
        "messages": [{"role": "assistant", "content": "\n".join(lines)}],
        "current_node": "account_switcher",
        "registered_accounts": accounts,
        "awaiting_input": "account_selection",
        "awaiting_account_selection": True,
    }


__all__ = ["account_switcher_node", "AccountSwitcherService"]
