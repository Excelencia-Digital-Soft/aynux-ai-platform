"""
Pharmacy Info Service

Loads and transforms pharmacy information from the database.
Single responsibility: pharmacy data access and transformation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from app.core.tenancy.pharmacy_repository import PharmacyRepository

logger = logging.getLogger(__name__)


class PharmacyInfoService:
    """
    Service for loading pharmacy information.

    Responsibility: Load and transform pharmacy data from the repository.
    """

    def __init__(self, repository: PharmacyRepository | None = None):
        """
        Initialize the service.

        Args:
            repository: Optional PharmacyRepository instance.
                       If not provided, will be created on demand.
        """
        self._repository = repository

    async def get_pharmacy_info(self, pharmacy_id: str | None) -> dict[str, Any] | None:
        """
        Load pharmacy information from database.

        Args:
            pharmacy_id: UUID string of the pharmacy config

        Returns:
            Dictionary with pharmacy info or None if not found
        """
        if not pharmacy_id:
            logger.warning("No pharmacy_id provided for info query")
            return None

        try:
            pharmacy_uuid = UUID(str(pharmacy_id))
        except ValueError as e:
            logger.error(f"Invalid pharmacy_id format: {e}")
            return None

        try:
            config = await self._load_config(pharmacy_uuid)
            if not config:
                logger.warning(f"Pharmacy config not found: {pharmacy_uuid}")
                return None

            return self._transform_config_to_dict(config)

        except Exception as e:
            logger.error(f"Error loading pharmacy info: {e}", exc_info=True)
            return None

    async def _load_config(self, pharmacy_id: UUID) -> Any | None:
        """
        Load pharmacy configuration from repository.

        Args:
            pharmacy_id: UUID of the pharmacy

        Returns:
            Pharmacy configuration model or None
        """
        # Import here to avoid circular imports and allow lazy loading
        from app.core.tenancy.pharmacy_repository import PharmacyRepository
        from app.database.async_db import get_async_db_context

        async with get_async_db_context() as session:
            repo = self._repository or PharmacyRepository(session)
            return await repo.get_by_id(pharmacy_id)

    @staticmethod
    def _transform_config_to_dict(config: Any) -> dict[str, Any]:
        """
        Transform pharmacy config model to dictionary.

        Args:
            config: Pharmacy configuration model

        Returns:
            Dictionary with pharmacy info
        """
        return {
            "name": config.pharmacy_name,
            "address": config.pharmacy_address,
            "phone": config.pharmacy_phone,
            "email": config.pharmacy_email,
            "website": config.pharmacy_website,
            "hours": config.pharmacy_hours,
            "is_24h": config.pharmacy_is_24h,
        }

    async def get_pharmacy_name(self, pharmacy_id: str | None) -> str:
        """
        Get only the pharmacy name.

        Args:
            pharmacy_id: UUID string of the pharmacy

        Returns:
            Pharmacy name or "la farmacia" as default
        """
        info = await self.get_pharmacy_info(pharmacy_id)
        if info:
            return info.get("name", "la farmacia")
        return "la farmacia"

    async def get_contact_info(self, pharmacy_id: str | None) -> dict[str, str | None]:
        """
        Get only contact information (phone, email, address).

        Args:
            pharmacy_id: UUID string of the pharmacy

        Returns:
            Dict with contact info fields
        """
        info = await self.get_pharmacy_info(pharmacy_id)
        if not info:
            return {"phone": None, "email": None, "address": None}

        return {
            "phone": info.get("phone"),
            "email": info.get("email"),
            "address": info.get("address"),
        }
