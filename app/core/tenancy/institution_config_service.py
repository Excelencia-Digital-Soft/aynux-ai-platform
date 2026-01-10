# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Servicio para cargar configuraciones de instituciones
#              desde la base de datos. Soporta múltiples instituciones por org.
# Tenant-Aware: Yes - carga configuración específica por organization_id.
# ============================================================================
"""
InstitutionConfigService - Bridge between database and domain agents.

Loads institution configurations exclusively from the database.
All service URLs, scheduler settings, and institution config MUST be stored in the database.

Generic service that can be used for any institution type:
- Medical appointments (patologia_digestiva, mercedario)
- Pharmacies
- Clinics
- Any other per-tenant service configuration

Usage:
    # In agent or scheduler
    config_service = InstitutionConfigService(db_session)
    institution_config = await config_service.get_config_by_key("patologia_digestiva")

    # From WhatsApp phone number ID (bypass routing)
    institution_config = await config_service.get_config_by_whatsapp_phone(
        phone_number_id
    )

    # Access typed settings
    settings = institution_config.get_settings()
    base_url = settings.connection.base_url
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.core.tenancy.schemas import InstitutionSettings
    from app.models.db.tenancy.tenant_institution_config import TenantInstitutionConfig

logger = logging.getLogger(__name__)


# System organization UUID (used for generic mode)
SYSTEM_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")


@dataclass
class InstitutionConfig:
    """
    Institution configuration loaded from the database.

    This dataclass provides a unified interface for institution settings
    stored in the tenant_institution_configs table with flexible JSONB settings.

    Attributes:
        institution_id: Unique configuration ID
        institution_key: Key like "patologia_digestiva" or "mercedario"
        institution_name: Human-readable name
        institution_type: Category type (medical, pharmacy, generic, etc.)
        enabled: Whether this institution is active

        settings: Validated InstitutionSettings from JSONB
        settings_dict: Raw settings dictionary for direct access

        organization_id: Organization ID from database
    """

    # Institution identification
    institution_id: UUID
    institution_key: str
    institution_name: str
    institution_type: str
    enabled: bool

    # Settings (validated Pydantic model)
    settings: "InstitutionSettings"
    settings_dict: dict[str, Any] = field(default_factory=dict)

    # Organization tracking
    organization_id: UUID = field(default=SYSTEM_ORG_ID)

    # Description
    description: str | None = None

    # ==========================================================================
    # Convenience Properties (delegated to settings)
    # ==========================================================================

    @property
    def base_url(self) -> str:
        """Get connection base URL."""
        return self.settings.connection.base_url

    @property
    def connection_type(self) -> str:
        """Get connection type (soap, rest, graphql)."""
        return self.settings.connection.type.value

    @property
    def timeout_seconds(self) -> int:
        """Get connection timeout in seconds."""
        return self.settings.connection.timeout_seconds

    @property
    def auth_type(self) -> str:
        """Get authentication type."""
        return self.settings.auth.type

    @property
    def scheduler_enabled(self) -> bool:
        """Check if scheduler is enabled."""
        return self.settings.scheduler.enabled

    @property
    def timezone(self) -> str:
        """Get scheduler timezone."""
        return self.settings.scheduler.timezone

    @property
    def morning_hour(self) -> int:
        """Get morning reminder hour."""
        return self.settings.scheduler.morning_hour

    @property
    def evening_hour(self) -> int:
        """Get evening reminder hour."""
        return self.settings.scheduler.evening_hour

    @property
    def whatsapp_phone_number_id(self) -> str | None:
        """Get WhatsApp phone number ID."""
        return self.settings.whatsapp.phone_number_id

    @property
    def branding_address(self) -> str | None:
        """Get institution address."""
        return self.settings.branding.address

    @property
    def branding_phone(self) -> str | None:
        """Get institution phone."""
        return self.settings.branding.phone

    @property
    def branding_email(self) -> str | None:
        """Get institution email."""
        return self.settings.branding.email

    @property
    def branding_website(self) -> str | None:
        """Get institution website."""
        return self.settings.branding.website

    # ==========================================================================
    # Legacy Compatibility Properties
    # ==========================================================================

    @property
    def soap_url(self) -> str | None:
        """Legacy: Get SOAP URL (alias for base_url when connection type is soap)."""
        return self.base_url if self.connection_type == "soap" else None

    @property
    def soap_timeout(self) -> int:
        """Legacy: Get SOAP timeout (alias for timeout_seconds)."""
        return self.timeout_seconds

    @property
    def api_type(self) -> str:
        """Legacy: Get API type (alias for connection_type)."""
        return self.connection_type

    @property
    def reminder_enabled(self) -> bool:
        """Legacy: Get reminder enabled (alias for scheduler_enabled)."""
        return self.scheduler_enabled

    @property
    def reminder_timezone(self) -> str:
        """Legacy: Get reminder timezone (alias for timezone)."""
        return self.timezone

    @property
    def reminder_morning_hour(self) -> int:
        """Legacy: Get reminder morning hour (alias for morning_hour)."""
        return self.morning_hour

    @property
    def reminder_evening_hour(self) -> int:
        """Legacy: Get reminder evening hour (alias for evening_hour)."""
        return self.evening_hour

    @property
    def institution_address(self) -> str | None:
        """Legacy: Get institution address."""
        return self.branding_address

    @property
    def institution_phone(self) -> str | None:
        """Legacy: Get institution phone."""
        return self.branding_phone

    @property
    def institution_email(self) -> str | None:
        """Legacy: Get institution email."""
        return self.branding_email

    @property
    def institution_website(self) -> str | None:
        """Legacy: Get institution website."""
        return self.branding_website

    @property
    def institution_logo_path(self) -> str | None:
        """Legacy: Get institution logo path."""
        return self.settings.branding.logo_path

    @property
    def config(self) -> dict[str, Any]:
        """Legacy: Get custom config dict."""
        return self.settings.custom

    # ==========================================================================
    # Methods
    # ==========================================================================

    def get_settings(self) -> "InstitutionSettings":
        """Get the validated InstitutionSettings object."""
        return self.settings

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a value from the custom config.

        Args:
            key: Key to look up in custom settings.
            default: Default value if key not found.

        Returns:
            Value from custom config or default.
        """
        return self.settings.get_custom_value(key, default)

    def get_setting_value(self, path: str, default: Any = None) -> Any:
        """Get a value from settings using dot notation path.

        Args:
            path: Dot-separated path (e.g., "connection.base_url", "auth.type")
            default: Default value if path not found.

        Returns:
            Value at path or default.
        """
        parts = path.split(".")
        current: Any = self.settings_dict

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    @property
    def is_soap(self) -> bool:
        """Check if this institution uses SOAP API."""
        return self.connection_type == "soap"

    @property
    def is_rest(self) -> bool:
        """Check if this institution uses REST API."""
        return self.connection_type == "rest"


class InstitutionConfigService:
    """
    Service for loading institution configurations from the database.

    All configurations MUST be stored in the database. There is no fallback
    to environment variables.

    Features:
    - Load config by institution_key (e.g., "patologia_digestiva")
    - Load config by WhatsApp phone number ID (for bypass routing)
    - Load config by config ID
    - List all institutions for an organization
    - List all enabled institutions (for scheduler)
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy async session for database queries
        """
        self._db = db

    async def get_config_by_key(
        self,
        institution_key: str,
        org_id: UUID | None = None,
    ) -> InstitutionConfig:
        """
        Get institution configuration by key.

        Args:
            institution_key: Institution key (e.g., "patologia_digestiva")
            org_id: Optional organization ID filter (uses system org if not provided)

        Returns:
            InstitutionConfig with settings from database

        Raises:
            ValueError: If no config found for the given key
        """
        from app.models.db.tenancy.tenant_institution_config import TenantInstitutionConfig

        stmt = select(TenantInstitutionConfig).where(
            TenantInstitutionConfig.institution_key == institution_key,
            TenantInstitutionConfig.enabled == True,  # noqa: E712
        )

        if org_id is not None:
            stmt = stmt.where(TenantInstitutionConfig.organization_id == org_id)

        result = await self._db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if not db_config:
            raise ValueError(
                f"No institution config found for key '{institution_key}'. "
                f"Please configure the institution in the database."
            )

        logger.debug(f"Loaded institution config: {institution_key}")
        return self._db_to_config(db_config)

    async def get_config_by_id(self, config_id: UUID) -> InstitutionConfig:
        """
        Get institution configuration by ID.

        Args:
            config_id: The configuration ID

        Returns:
            InstitutionConfig with settings from database

        Raises:
            ValueError: If no config found for the given ID
        """
        from app.models.db.tenancy.tenant_institution_config import TenantInstitutionConfig

        stmt = select(TenantInstitutionConfig).where(
            TenantInstitutionConfig.id == config_id
        )
        result = await self._db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if not db_config:
            raise ValueError(f"No institution config found with ID {config_id}")

        logger.debug(f"Loaded institution config by ID: {config_id}")
        return self._db_to_config(db_config)

    async def get_config_by_whatsapp_phone(
        self,
        whatsapp_phone_number_id: str,
    ) -> InstitutionConfig:
        """
        Get institution config by WhatsApp phone number ID.

        Used for bypass routing - identifies which institution a message was sent to.

        Args:
            whatsapp_phone_number_id: The WhatsApp Business phone number ID

        Returns:
            InstitutionConfig for the matched institution

        Raises:
            ValueError: If no institution found with that phone number ID
        """
        from app.models.db.tenancy.tenant_institution_config import TenantInstitutionConfig

        # Query using JSONB path
        stmt = select(TenantInstitutionConfig).where(
            TenantInstitutionConfig.settings["whatsapp"]["phone_number_id"].astext
            == whatsapp_phone_number_id,
            TenantInstitutionConfig.enabled == True,  # noqa: E712
        )
        result = await self._db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if not db_config:
            raise ValueError(
                f"No institution found with WhatsApp phone number ID: {whatsapp_phone_number_id}. "
                f"Please configure whatsapp.phone_number_id in settings."
            )

        logger.info(
            f"Resolved institution by WhatsApp ID {whatsapp_phone_number_id} → {db_config.institution_key}"
        )
        return self._db_to_config(db_config)

    async def get_config_for_organization(
        self,
        org_id: UUID,
        include_disabled: bool = False,
    ) -> list[InstitutionConfig]:
        """
        Get all institution configs for an organization.

        Args:
            org_id: Organization ID
            include_disabled: Whether to include disabled institutions

        Returns:
            List of InstitutionConfig for the organization
        """
        from app.models.db.tenancy.tenant_institution_config import TenantInstitutionConfig

        stmt = select(TenantInstitutionConfig).where(
            TenantInstitutionConfig.organization_id == org_id
        )

        if not include_disabled:
            stmt = stmt.where(TenantInstitutionConfig.enabled == True)  # noqa: E712

        stmt = stmt.order_by(TenantInstitutionConfig.institution_name)

        result = await self._db.execute(stmt)
        db_configs = result.scalars().all()

        return [self._db_to_config(cfg) for cfg in db_configs]

    async def get_all_enabled_institutions(
        self,
        institution_type: str | None = None,
    ) -> list[InstitutionConfig]:
        """
        Get all enabled institutions across all organizations.

        Used by the reminder scheduler to send reminders for all institutions.

        Args:
            institution_type: Optional filter by institution type (e.g., "medical")

        Returns:
            List of all enabled InstitutionConfig
        """
        from app.models.db.tenancy.tenant_institution_config import TenantInstitutionConfig

        stmt = select(TenantInstitutionConfig).where(
            TenantInstitutionConfig.enabled == True,  # noqa: E712
        )

        if institution_type:
            stmt = stmt.where(TenantInstitutionConfig.institution_type == institution_type)

        # Filter by scheduler enabled using JSONB
        stmt = stmt.where(
            TenantInstitutionConfig.settings["scheduler"]["enabled"].astext == "true"
        )

        stmt = stmt.order_by(TenantInstitutionConfig.institution_name)

        result = await self._db.execute(stmt)
        db_configs = result.scalars().all()

        logger.debug(f"Found {len(db_configs)} enabled institutions for reminders")
        return [self._db_to_config(cfg) for cfg in db_configs]

    async def list_all_institutions(self) -> list[dict]:
        """
        List all institution configurations for UI selectors.

        Returns:
            List of dicts with institution info for dropdown display
        """
        from app.models.db.tenancy.tenant_institution_config import TenantInstitutionConfig

        stmt = select(TenantInstitutionConfig).order_by(
            TenantInstitutionConfig.institution_name
        )
        result = await self._db.execute(stmt)
        configs = result.scalars().all()

        return [cfg.to_summary_dict() for cfg in configs]

    async def create_or_update_config(
        self,
        org_id: UUID,
        institution_key: str,
        institution_name: str,
        institution_type: str = "generic",
        settings: dict[str, Any] | None = None,
    ) -> InstitutionConfig:
        """
        Create or update an institution configuration.

        Args:
            org_id: Organization ID
            institution_key: Unique key for the institution
            institution_name: Human-readable name
            institution_type: Institution type category
            settings: JSONB settings dictionary

        Returns:
            The created or updated InstitutionConfig
        """
        from app.core.tenancy.schemas import InstitutionSettings
        from app.models.db.tenancy.tenant_institution_config import TenantInstitutionConfig

        # Validate settings with Pydantic
        if settings:
            validated = InstitutionSettings.model_validate(settings)
            settings = validated.model_dump(mode="json")
        else:
            settings = InstitutionSettings().model_dump(mode="json")

        # Check if exists
        stmt = select(TenantInstitutionConfig).where(
            TenantInstitutionConfig.organization_id == org_id,
            TenantInstitutionConfig.institution_key == institution_key,
        )
        result = await self._db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if db_config:
            # Update existing
            db_config.institution_name = institution_name
            db_config.institution_type = institution_type
            db_config.settings = settings
            logger.info(f"Updated institution config: {institution_key}")
        else:
            # Create new
            db_config = TenantInstitutionConfig(
                organization_id=org_id,
                institution_key=institution_key,
                institution_name=institution_name,
                institution_type=institution_type,
                settings=settings,
            )
            self._db.add(db_config)
            logger.info(f"Created institution config: {institution_key}")

        await self._db.commit()
        await self._db.refresh(db_config)

        return self._db_to_config(db_config)

    def _db_to_config(
        self,
        db_config: "TenantInstitutionConfig",
    ) -> InstitutionConfig:
        """Convert DB model to InstitutionConfig dataclass."""
        from app.core.tenancy.schemas import InstitutionSettings

        # Get validated settings
        settings = db_config.get_settings()

        return InstitutionConfig(
            institution_id=db_config.id,
            institution_key=db_config.institution_key,
            institution_name=db_config.institution_name,
            institution_type=db_config.institution_type,
            enabled=db_config.enabled,
            settings=settings,
            settings_dict=db_config.settings or {},
            organization_id=db_config.organization_id,
            description=db_config.description,
        )
