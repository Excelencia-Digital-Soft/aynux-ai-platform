# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Servicio para cargar configuraciones de farmacia/comercio desde
#              la base de datos. No hay fallback a variables de entorno.
# Tenant-Aware: Yes - carga configuracion especifica por organization_id.
# ============================================================================
"""
PharmacyConfigService - Bridge between database and pharmacy/payment modules.

Loads pharmacy merchant configurations exclusively from the database.
All pharmacy and MercadoPago settings MUST be stored in the database.

Usage:
    # In webhook handler or payment flow
    config_service = PharmacyConfigService(db_session)
    pharmacy_config = await config_service.get_config(org_id)

    # From external_reference parsing (format: customer_id:debt_id:pharmacy_id:uuid)
    pharmacy_config, ref_data = await config_service.get_config_by_external_reference(
        external_ref
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig

logger = logging.getLogger(__name__)


# Well-known test organization UUID (used for testing)
TEST_PHARMACY_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


@dataclass
class PharmacyConfig:
    """
    Pharmacy configuration loaded from the database.

    This dataclass provides a unified interface for pharmacy/merchant settings
    stored in the pharmacy_merchant_configs table.

    Attributes:
        pharmacy_id: Unique pharmacy configuration ID
        pharmacy_name: Name displayed on PDF receipts
        pharmacy_address: Address on PDF receipts
        pharmacy_phone: Phone on PDF receipts
        pharmacy_logo_path: Path to logo image for PDFs
        mp_enabled: Whether Mercado Pago is enabled
        mp_access_token: MP access token for API calls
        mp_public_key: MP public key for SDK
        mp_webhook_secret: Secret for validating webhook signatures
        mp_sandbox: Whether to use sandbox mode
        mp_timeout: Request timeout in seconds
        mp_notification_url: Webhook URL for MP notifications
        receipt_public_url_base: Base URL for PDF receipt access
        organization_id: Organization ID from database
    """

    # Pharmacy identification
    pharmacy_id: UUID
    pharmacy_name: str
    pharmacy_address: str | None
    pharmacy_phone: str | None
    pharmacy_hours: str | None
    pharmacy_logo_path: str | None

    # Mercado Pago settings
    mp_enabled: bool
    mp_access_token: str | None
    mp_public_key: str | None
    mp_webhook_secret: str | None
    mp_sandbox: bool
    mp_timeout: int
    mp_notification_url: str | None
    receipt_public_url_base: str | None

    # Organization tracking
    organization_id: UUID

    # Payment options configuration (Smart Debt Negotiation)
    payment_option_half_percent: int = 50
    payment_option_minimum_percent: int = 30
    payment_minimum_amount: int = 1000


class PharmacyConfigService:
    """
    Service for loading pharmacy/merchant configurations from the database.

    All configurations MUST be stored in the database. There is no fallback
    to environment variables.

    Features:
    - Load config from database by org_id (required)
    - Parse external_reference to extract org_id and load config
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy async session for database queries
        """
        self._db = db

    async def get_config(self, org_id: UUID) -> PharmacyConfig:
        """
        Get pharmacy configuration for an organization.

        Args:
            org_id: Organization ID (required)

        Returns:
            PharmacyConfig with settings from database

        Raises:
            ValueError: If no config found for the given org_id
        """
        db_config = await self._load_from_db(org_id)
        if db_config:
            logger.debug(f"Loaded pharmacy config from DB for org {org_id}")
            return self._db_to_config(db_config, org_id)

        raise ValueError(
            f"No pharmacy config found for organization {org_id}. "
            f"Please configure pharmacy settings in the database."
        )

    async def get_config_by_id(self, pharmacy_id: UUID) -> PharmacyConfig:
        """
        Get pharmacy configuration by pharmacy ID.

        Use this method when you need to load a specific pharmacy configuration
        (e.g., when organization has multiple pharmacies).

        Args:
            pharmacy_id: The pharmacy configuration ID

        Returns:
            PharmacyConfig with settings from database

        Raises:
            ValueError: If no config found for the given pharmacy_id
        """
        from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig

        stmt = select(PharmacyMerchantConfig).where(
            PharmacyMerchantConfig.id == pharmacy_id
        )
        result = await self._db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if not db_config:
            raise ValueError(f"No pharmacy config found with ID {pharmacy_id}")

        logger.debug(f"Loaded pharmacy config by ID: {pharmacy_id}")
        return self._db_to_config(db_config, db_config.organization_id)

    async def get_config_by_external_reference(
        self,
        external_reference: str,
    ) -> tuple[PharmacyConfig, dict]:
        """
        Get pharmacy config by parsing external_reference from MP webhook.

        Format: customer_id:debt_id:pharmacy_id:uuid (4 parts required)

        Args:
            external_reference: External reference from MP payment

        Returns:
            Tuple of (PharmacyConfig, parsed_reference_dict)

        Raises:
            ValueError: If external_reference format is invalid or missing pharmacy_id
        """
        parts = external_reference.split(":")

        if len(parts) == 4:
            customer_id, debt_id, pharmacy_id_str, unique_id = parts
            try:
                pharmacy_id = UUID(pharmacy_id_str)
            except ValueError as e:
                raise ValueError(
                    f"Invalid pharmacy_id in external_reference: {pharmacy_id_str}"
                ) from e

            config = await self.get_config_by_id(pharmacy_id)
            return config, {
                "customer_id": int(customer_id),
                "debt_id": debt_id,
                "pharmacy_id": pharmacy_id,
                "unique_id": unique_id,
            }

        raise ValueError(
            f"Invalid external_reference format: {external_reference}. "
            f"Expected format: customer_id:debt_id:pharmacy_id:uuid"
        )

    async def _load_from_db(self, org_id: UUID) -> PharmacyMerchantConfig | None:
        """Load config from database by organization_id."""
        from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig

        stmt = select(PharmacyMerchantConfig).where(
            PharmacyMerchantConfig.organization_id == org_id
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_any_active_mp_config(self) -> PharmacyConfig:
        """
        Get any pharmacy config with Mercado Pago enabled.

        Used for initial payment fetch in webhooks when org_id is not yet known.
        The actual org-specific config is loaded later from external_reference.

        Returns:
            PharmacyConfig with MP enabled and valid access token

        Raises:
            ValueError: If no active MP configuration found in database
        """
        from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig

        stmt = select(PharmacyMerchantConfig).where(
            PharmacyMerchantConfig.mp_enabled == True,  # noqa: E712
            PharmacyMerchantConfig.mp_access_token.isnot(None),
        ).limit(1)
        result = await self._db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if not db_config:
            raise ValueError(
                "No active Mercado Pago configuration found in database. "
                "Please configure at least one organization with MP credentials."
            )

        logger.debug(
            f"Using MP config from org {db_config.organization_id} for initial payment fetch"
        )
        return self._db_to_config(db_config, db_config.organization_id)

    async def get_config_by_whatsapp_phone(
        self,
        whatsapp_phone: str,
    ) -> PharmacyConfig:
        """
        Get pharmacy config by WhatsApp phone number.

        Used to identify which pharmacy a message was sent to.

        Args:
            whatsapp_phone: The WhatsApp phone number of the pharmacy
                            (stored in pharmacy_merchant_config.whatsapp_phone_number)

        Returns:
            PharmacyConfig for the matched organization

        Raises:
            ValueError: If no pharmacy found with that phone number
        """
        from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig

        stmt = select(PharmacyMerchantConfig).where(
            PharmacyMerchantConfig.whatsapp_phone_number == whatsapp_phone
        )
        result = await self._db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if not db_config:
            raise ValueError(
                f"No pharmacy found with WhatsApp number: {whatsapp_phone}. "
                f"Please configure whatsapp_phone_number in pharmacy_merchant_configs."
            )

        logger.info(
            f"Resolved pharmacy by WhatsApp phone {whatsapp_phone} → org {db_config.organization_id}"
        )
        return self._db_to_config(db_config, db_config.organization_id)

    async def list_all_pharmacies(self) -> list[dict]:
        """
        List all pharmacy configurations for UI selectors.

        Returns:
            List of dicts with pharmacy info for dropdown display
        """
        from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig

        stmt = select(PharmacyMerchantConfig).order_by(PharmacyMerchantConfig.pharmacy_name)
        result = await self._db.execute(stmt)
        configs = result.scalars().all()

        return [
            {
                "id": str(cfg.id),  # Pharmacy config ID (unique per pharmacy)
                "organization_id": str(cfg.organization_id),
                "pharmacy_name": cfg.pharmacy_name,
                "whatsapp_phone_number": cfg.whatsapp_phone_number,
                "mp_enabled": cfg.mp_enabled,
                "display_label": f"{cfg.pharmacy_name} ({cfg.whatsapp_phone_number or 'Sin número'})",
            }
            for cfg in configs
        ]

    def _db_to_config(
        self,
        db_config: PharmacyMerchantConfig,
        org_id: UUID,
    ) -> PharmacyConfig:
        """Convert DB model to PharmacyConfig dataclass."""
        return PharmacyConfig(
            pharmacy_id=db_config.id,
            pharmacy_name=db_config.pharmacy_name,
            pharmacy_address=db_config.pharmacy_address,
            pharmacy_phone=db_config.pharmacy_phone,
            pharmacy_hours=db_config.pharmacy_hours,
            pharmacy_logo_path=db_config.pharmacy_logo_path,
            mp_enabled=db_config.mp_enabled,
            mp_access_token=db_config.mp_access_token,
            mp_public_key=db_config.mp_public_key,
            mp_webhook_secret=db_config.mp_webhook_secret,
            mp_sandbox=db_config.mp_sandbox,
            mp_timeout=db_config.mp_timeout,
            mp_notification_url=db_config.mp_notification_url,
            receipt_public_url_base=db_config.receipt_public_url_base,
            organization_id=org_id,
            # Payment options configuration (Smart Debt Negotiation)
            payment_option_half_percent=db_config.payment_option_half_percent,
            payment_option_minimum_percent=db_config.payment_option_minimum_percent,
            payment_minimum_amount=db_config.payment_minimum_amount,
        )
