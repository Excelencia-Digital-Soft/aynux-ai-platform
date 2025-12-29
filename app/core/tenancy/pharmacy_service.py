# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Business logic service for pharmacy configurations.
#              Orchestrates repository operations and bypass rule sync.
# Tenant-Aware: Yes - operations scoped to user's organization memberships.
# ============================================================================
"""Business logic service for pharmacy configurations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.api.schemas.pharmacy_config import PharmacyConfigCreate, PharmacyConfigUpdate
from app.core.tenancy.pharmacy_bypass_service import PharmacyBypassService
from app.core.tenancy.pharmacy_repository import PharmacyRepository
from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig


@dataclass
class PharmacyListResult:
    """Result of listing pharmacies."""

    pharmacies: list[PharmacyMerchantConfig]
    total: int
    page: int
    page_size: int


class PharmacyService:
    """
    Business logic for pharmacy configuration operations.

    Handles CRUD operations with bypass rule synchronization.
    Uses PharmacyRepository for database access and PharmacyBypassService
    for maintaining bypass rules linked to pharmacies.
    """

    def __init__(
        self,
        repository: PharmacyRepository,
        bypass_service: PharmacyBypassService,
    ):
        """
        Initialize the service.

        Args:
            repository: PharmacyRepository for database operations
            bypass_service: PharmacyBypassService for bypass rule management
        """
        self._repo = repository
        self._bypass = bypass_service

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        is_system_admin: bool,
        *,
        search: str | None = None,
        mp_enabled: bool | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> PharmacyListResult:
        """
        List pharmacies visible to a user.

        System admins see all pharmacies. Regular users see only
        pharmacies in organizations they belong to.

        Args:
            user_id: UUID of the requesting user
            is_system_admin: Whether the user is a system admin
            search: Optional search string for name/phone/whatsapp
            mp_enabled: Optional filter for Mercado Pago status
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            PharmacyListResult with pharmacies and pagination info
        """
        org_ids = None
        if not is_system_admin:
            org_ids = await self._repo.get_user_org_ids(user_id)
            if not org_ids:
                return PharmacyListResult([], 0, page, page_size)

        pharmacies, total = await self._repo.list_pharmacies(
            org_ids=org_ids,
            search=search,
            mp_enabled=mp_enabled,
            page=page,
            page_size=page_size,
        )
        return PharmacyListResult(pharmacies, total, page, page_size)

    async def create(
        self,
        data: PharmacyConfigCreate,
        org_id: uuid.UUID,
    ) -> PharmacyMerchantConfig:
        """
        Create a new pharmacy configuration.

        Automatically creates a bypass rule if the pharmacy has
        a whatsapp_phone_number configured.

        Args:
            data: PharmacyConfigCreate with pharmacy data
            org_id: UUID of the organization

        Returns:
            Created PharmacyMerchantConfig
        """
        config = PharmacyMerchantConfig(
            id=uuid.uuid4(),
            organization_id=org_id,
            pharmacy_name=data.pharmacy_name,
            pharmacy_address=data.pharmacy_address,
            pharmacy_phone=data.pharmacy_phone,
            pharmacy_logo_path=data.pharmacy_logo_path,
            mp_enabled=data.mp_enabled,
            mp_access_token=data.mp_access_token,
            mp_public_key=data.mp_public_key,
            mp_webhook_secret=data.mp_webhook_secret,
            mp_sandbox=data.mp_sandbox,
            mp_timeout=data.mp_timeout,
            mp_notification_url=data.mp_notification_url,
            receipt_public_url_base=data.receipt_public_url_base,
            whatsapp_phone_number=data.whatsapp_phone_number,
        )
        await self._repo.create(config)
        await self._bypass.create_bypass_rule_for_pharmacy(config)
        await self._repo.commit()
        await self._repo.refresh(config)
        return config

    async def update(
        self,
        config: PharmacyMerchantConfig,
        data: PharmacyConfigUpdate,
    ) -> PharmacyMerchantConfig:
        """
        Update a pharmacy configuration.

        Automatically syncs bypass rule if whatsapp_phone_number changes:
        - Added: Creates new bypass rule
        - Changed: Updates bypass rule phone_number_id
        - Removed: Deletes bypass rule

        Args:
            config: Existing PharmacyMerchantConfig to update
            data: PharmacyConfigUpdate with partial data

        Returns:
            Updated PharmacyMerchantConfig
        """
        old_whatsapp = config.whatsapp_phone_number
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(config, field, value)
        config.updated_at = datetime.now(UTC)

        # Sync bypass rule if whatsapp changed
        if "whatsapp_phone_number" in update_data:
            await self._bypass.update_bypass_rule_for_pharmacy(config, old_whatsapp)

        await self._repo.commit()
        await self._repo.refresh(config)
        return config

    async def delete(self, config: PharmacyMerchantConfig) -> None:
        """
        Delete a pharmacy configuration.

        Also deletes any associated bypass rule.

        Args:
            config: PharmacyMerchantConfig to delete
        """
        await self._bypass.delete_bypass_rule_for_pharmacy(config.id)
        await self._repo.delete(config)
        await self._repo.commit()
