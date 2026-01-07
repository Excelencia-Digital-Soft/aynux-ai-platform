"""
Pharmacy Config Service

Loads pharmacy configuration (name, phone) from the database.
Single responsibility: pharmacy config access for identification flow.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class PharmacyConfigResult:
    """Result of pharmacy configuration lookup."""

    pharmacy_name: str | None = None
    pharmacy_phone: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for state merging."""
        return {
            "pharmacy_name": self.pharmacy_name,
            "pharmacy_phone": self.pharmacy_phone,
        }


class PharmacyConfigService:
    """
    Service for loading pharmacy configuration.

    Single responsibility: Load pharmacy name and phone from database
    for the customer identification flow.
    """

    async def get_config(self, pharmacy_id: str | None) -> PharmacyConfigResult:
        """
        Load pharmacy name and phone from database.

        Args:
            pharmacy_id: UUID string of the pharmacy config

        Returns:
            PharmacyConfigResult with pharmacy_name and pharmacy_phone
        """
        if not pharmacy_id:
            return PharmacyConfigResult()

        try:
            pharmacy_uuid = UUID(str(pharmacy_id))
        except ValueError as e:
            logger.warning(f"Invalid pharmacy_id format: {e}")
            return PharmacyConfigResult()

        try:
            config = await self._load_config(pharmacy_uuid)
            if config:
                return PharmacyConfigResult(
                    pharmacy_name=config.pharmacy_name,
                    pharmacy_phone=config.pharmacy_phone,
                )
        except Exception as e:
            logger.warning(f"Failed to load pharmacy config: {e}")

        return PharmacyConfigResult()

    async def get_config_dict(self, pharmacy_id: str | None) -> dict[str, Any]:
        """
        Load pharmacy config as dictionary for state merging.

        Args:
            pharmacy_id: UUID string of the pharmacy config

        Returns:
            Dictionary with pharmacy_name and pharmacy_phone
        """
        result = await self.get_config(pharmacy_id)
        return result.to_dict()

    async def _load_config(self, pharmacy_id: UUID) -> Any | None:
        """
        Load pharmacy configuration from repository.

        Args:
            pharmacy_id: UUID of the pharmacy

        Returns:
            Pharmacy configuration model or None
        """
        from app.core.tenancy.pharmacy_repository import PharmacyRepository
        from app.database.async_db import get_async_db_context

        async with get_async_db_context() as session:
            repo = PharmacyRepository(session)
            return await repo.get_by_id(pharmacy_id)
