"""State extraction and management service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from app.domains.pharmacy.services.pharmacy_config_service import (
        PharmacyConfigService,
    )

logger = logging.getLogger(__name__)


class StateManagementService:
    """
    Service for state extraction and management.

    Responsibilities:
    - Extract phone/organization_id/pharmacy_id from state
    - Ensure pharmacy config is loaded
    """

    def __init__(self, config_service: PharmacyConfigService | None = None):
        self._config_service = config_service

    def _get_config_service(self) -> PharmacyConfigService:
        """Get or create config service."""
        if self._config_service is None:
            from app.domains.pharmacy.services.pharmacy_config_service import (
                PharmacyConfigService,
            )

            self._config_service = PharmacyConfigService()
        return self._config_service

    def extract_phone(self, state_dict: dict[str, Any]) -> str | None:
        """
        Extract phone number from state.

        Args:
            state_dict: Current state dictionary

        Returns:
            Phone number or None if not found
        """
        return (
            state_dict.get("customer_id")
            or state_dict.get("user_id")
            or state_dict.get("user_phone")
            or state_dict.get("sender")
        )

    def get_organization_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """
        Extract organization_id from state.

        Args:
            state_dict: Current state dictionary

        Returns:
            Organization UUID or None if not found/invalid
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

    def get_pharmacy_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """
        Extract pharmacy_id from state.

        Args:
            state_dict: Current state dictionary

        Returns:
            Pharmacy UUID or None if not found/invalid
        """
        pharmacy_id = state_dict.get("pharmacy_id")
        if pharmacy_id is None:
            return None
        if isinstance(pharmacy_id, UUID):
            return pharmacy_id
        try:
            return UUID(str(pharmacy_id))
        except (ValueError, TypeError):
            logger.warning(f"Invalid pharmacy_id in state: {pharmacy_id}")
            return None

    async def ensure_pharmacy_config(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ensure pharmacy config is loaded into state.

        If pharmacy_name is missing but pharmacy_id is present,
        loads the config from the database.

        Args:
            state_dict: Current state dictionary

        Returns:
            Updated state dictionary with pharmacy config
        """
        pharmacy_id = state_dict.get("pharmacy_id")
        pharmacy_name = state_dict.get("pharmacy_name")

        if not pharmacy_name and pharmacy_id:
            logger.info(f"Loading pharmacy config for pharmacy_id={pharmacy_id}")
            config = await self._get_config_service().get_config_dict(pharmacy_id)
            logger.info(f"Loaded pharmacy config: {config}")
            return {**state_dict, **config}

        return state_dict


__all__ = ["StateManagementService"]
