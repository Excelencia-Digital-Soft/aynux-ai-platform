"""Base handler for PersonResolution flow handlers."""

from __future__ import annotations

import logging
from typing import Any

from app.domains.pharmacy.agents.models import StatePreserver
from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler


class PersonResolutionBaseHandler(BasePharmacyHandler):
    """
    Base handler for person resolution flow steps.

    Extends BasePharmacyHandler with:
    - Pydantic-based state preservation via StatePreserver
    - Common state update formatting
    - Pharmacy config and context field preservation
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _preserve_all(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Preserve all context fields using Pydantic-based StatePreserver.

        This method uses the PreservedContext Pydantic model to extract
        and validate fields that must be preserved across handler transitions.

        Preserved fields include:
        - Payment context: payment_amount, is_partial_payment, etc.
        - Intent context: pharmacy_intent_type, extracted_entities
        - Auto-flow flags: auto_proceed_to_invoice, auto_return_to_query
        - Pharmacy config: pharmacy_id, pharmacy_name, pharmacy_phone

        Args:
            state_dict: Current state dictionary

        Returns:
            Dictionary with all preserved fields (non-None only)
        """
        return StatePreserver.extract_all(state_dict)

    def _preserve_pharmacy_config(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Extract only pharmacy configuration fields.

        Use _preserve_all() for complete preservation including payment context.

        Args:
            state_dict: Current state dictionary

        Returns:
            Dictionary with pharmacy config fields (non-None only)
        """
        return StatePreserver.extract_pharmacy_config(state_dict)

    def _preserve_payment_context(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Extract only payment-related preserved fields.

        Use _preserve_all() for complete preservation including pharmacy config.

        Args:
            state_dict: Current state dictionary

        Returns:
            Dictionary with payment context fields (non-None only)
        """
        return StatePreserver.extract_payment_context(state_dict)

    def _validate_required_context(
        self,
        state_dict: dict[str, Any],
        required_fields: list[str],
    ) -> tuple[bool, list[str]]:
        """
        Validate that required context fields are present.

        Useful for debugging missing state issues.

        Args:
            state_dict: Current state dictionary
            required_fields: List of field names that must have non-None values

        Returns:
            Tuple of (is_valid, missing_fields)
        """
        return StatePreserver.validate_required(state_dict, required_fields)

    async def _match_confirmation_pattern(
        self,
        message: str,
        intent_key: str,
        state: dict[str, Any],
    ) -> bool:
        """
        Check if message matches confirmation patterns for an intent.

        Loads patterns from domain_intent_cache (DB-driven, not hardcoded).

        Args:
            message: User message (should be lowercase, stripped)
            intent_key: Intent key to match against (e.g., 'welcome_existing_client')
            state: State dict with organization_id

        Returns:
            True if message matches any pattern (exact or contains)
        """
        from uuid import UUID

        from app.core.cache.domain_intent_cache import domain_intent_cache
        from app.database.async_db import get_async_db_context

        org_id = state.get("organization_id")
        if not org_id:
            self.logger.warning("No organization_id in state for pattern matching")
            return False

        try:
            # Convert to UUID if string
            if isinstance(org_id, str):
                org_id = UUID(org_id)

            async with get_async_db_context() as db:
                patterns = await domain_intent_cache.get_patterns(db, org_id, "pharmacy")

            confirmation = patterns.get("confirmation_patterns", {}).get(intent_key, {})
            exact_patterns = confirmation.get("exact", set())
            contains_patterns = confirmation.get("contains", set())

            # Check exact match
            if message in exact_patterns:
                return True

            # Check contains match
            for pattern in contains_patterns:
                if pattern in message:
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error matching confirmation pattern: {e}")
            return False


__all__ = ["PersonResolutionBaseHandler"]
