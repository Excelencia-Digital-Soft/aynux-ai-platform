# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Configuración de instituciones por tenant con esquema flexible.
#              Usa JSONB para configuración dinámica y validación Pydantic.
# Tenant-Aware: Yes - cada registro pertenece a una organización específica.
# ============================================================================
"""
TenantInstitutionConfig model - Per-tenant institution configuration.

Flexible configuration table for institutions/services per organization.
Uses JSONB for dynamic settings with Pydantic validation in Python.

Supports multiple connection types:
- SOAP (HCWeb)
- REST (Mercedario, generic APIs)
- GraphQL

Supports multiple authentication methods:
- None (no auth)
- API Key
- Basic Auth
- OAuth2
- SOAP WS-Security

Usage:
    # Get validated settings
    settings = config.get_settings()

    # Access typed fields
    base_url = settings.connection.base_url
    auth_type = settings.auth.type

    # Update settings
    config.set_settings(new_settings)
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA

if TYPE_CHECKING:
    from app.core.tenancy.schemas import InstitutionSettings

    from .organization import Organization

logger = logging.getLogger(__name__)


class TenantInstitutionConfig(Base, TimestampMixin):
    """
    Per-tenant institution configuration with flexible JSONB settings.

    This table stores configuration for external services per organization.
    Many-to-one relationship with Organization (one org can have multiple institutions).

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations
        institution_key: Unique key for the institution (e.g., "patologia_digestiva")
        institution_name: Human-readable name
        institution_type: Type category (e.g., "medical", "pharmacy", "generic")
        enabled: Whether this institution is active

        settings: JSONB containing all dynamic configuration:
            - connection: base_url, timeout, connection type
            - auth: authentication config (api_key, basic, oauth2, etc.)
            - scheduler: reminder settings
            - branding: contact info, logo
            - whatsapp: phone number IDs
            - custom: arbitrary key-value pairs

        encrypted_secrets: Encrypted sensitive values (API keys, passwords)
        description: Description or notes
    """

    __tablename__ = "tenant_institution_configs"

    # Primary identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique configuration identifier",
    )

    # Foreign key (many-to-one with organization)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this config belongs to",
    )

    # Institution identification
    institution_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Unique key for the institution (e.g., 'patologia_digestiva', 'mercedario')",
    )

    institution_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable institution name",
    )

    institution_type: Mapped[str] = mapped_column(
        String(50),
        default="generic",
        nullable=False,
        index=True,
        comment="Institution type category (medical, pharmacy, generic, etc.)",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether this institution configuration is active",
    )

    # Dynamic Configuration (JSONB) - validated by Pydantic InstitutionSettings
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Dynamic configuration: connection, auth, scheduler, branding, whatsapp, custom",
    )

    # Encrypted secrets (API keys, passwords) - separate from settings for security
    encrypted_secrets: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment="Encrypted sensitive values (API keys, passwords)",
    )

    # Description/Notes
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description or notes about this institution",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="tenant_institution_configs",
    )

    # Table configuration
    __table_args__ = (
        UniqueConstraint("organization_id", "institution_key", name="uq_tenant_org_institution_key"),
        Index("idx_tenant_institution_configs_org", "organization_id"),
        Index("idx_tenant_institution_configs_key", "institution_key"),
        Index("idx_tenant_institution_configs_type", "institution_type"),
        # GIN index for JSONB queries
        Index(
            "idx_tenant_institution_configs_settings_gin",
            "settings",
            postgresql_using="gin",
        ),
        # Functional index for WhatsApp phone number lookup
        Index(
            "idx_tenant_institution_configs_wa_phone",
            settings["whatsapp"]["phone_number_id"].astext,
            postgresql_using="btree",
        ),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<TenantInstitutionConfig(org_id='{self.organization_id}', key='{self.institution_key}')>"

    # =========================================================================
    # Settings Validation Methods
    # =========================================================================

    def get_settings(self) -> "InstitutionSettings":
        """Get validated settings as Pydantic model.

        Returns:
            InstitutionSettings instance with validated data.

        Raises:
            ValidationError: If settings don't match schema.
        """
        from app.core.tenancy.schemas import InstitutionSettings

        return InstitutionSettings.model_validate(self.settings or {})

    def set_settings(self, settings: "InstitutionSettings") -> None:
        """Set settings from Pydantic model.

        Args:
            settings: InstitutionSettings instance to store.
        """
        self.settings = settings.model_dump(mode="json")

    def update_settings(self, **kwargs: Any) -> "InstitutionSettings":
        """Update specific settings fields.

        Args:
            **kwargs: Fields to update (e.g., connection=..., auth=...)

        Returns:
            Updated InstitutionSettings instance.
        """
        current = self.get_settings()
        updated_data = current.model_dump()

        for key, value in kwargs.items():
            if hasattr(value, "model_dump"):
                updated_data[key] = value.model_dump()
            else:
                updated_data[key] = value

        from app.core.tenancy.schemas import InstitutionSettings

        updated = InstitutionSettings.model_validate(updated_data)
        self.set_settings(updated)
        return updated

    # =========================================================================
    # Convenience Properties
    # =========================================================================

    @property
    def base_url(self) -> str:
        """Get connection base URL from settings."""
        return self.get_setting_value("connection.base_url", "")

    @property
    def connection_type(self) -> str:
        """Get connection type from settings."""
        return self.get_setting_value("connection.type", "rest")

    @property
    def auth_type(self) -> str:
        """Get authentication type from settings."""
        return self.get_setting_value("auth.type", "none")

    @property
    def whatsapp_phone_number_id(self) -> str | None:
        """Get WhatsApp phone number ID from settings."""
        return self.get_setting_value("whatsapp.phone_number_id")

    @property
    def scheduler_enabled(self) -> bool:
        """Check if scheduler is enabled."""
        return self.get_setting_value("scheduler.enabled", True)

    @property
    def timezone(self) -> str:
        """Get scheduler timezone."""
        return self.get_setting_value("scheduler.timezone", "America/Argentina/San_Juan")

    # =========================================================================
    # JSONB Access Methods
    # =========================================================================

    def get_setting_value(self, path: str, default: Any = None) -> Any:
        """Get a value from settings using dot notation path.

        Args:
            path: Dot-separated path (e.g., "connection.base_url", "auth.type")
            default: Default value if path not found.

        Returns:
            Value at path or default.

        Example:
            url = config.get_setting_value("connection.base_url", "")
            auth_type = config.get_setting_value("auth.type", "none")
        """
        if self.settings is None:
            return default

        parts = path.split(".")
        current = self.settings

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    def set_setting_value(self, path: str, value: Any) -> None:
        """Set a value in settings using dot notation path.

        Args:
            path: Dot-separated path (e.g., "connection.base_url")
            value: Value to set.

        Example:
            config.set_setting_value("connection.base_url", "https://api.example.com")
            config.set_setting_value("custom.specialty_ids", ["1", "2", "3"])
        """
        if self.settings is None:
            self.settings = {}

        parts = path.split(".")
        current = self.settings

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def get_custom_value(self, key: str, default: Any = None) -> Any:
        """Get a value from the custom settings dict.

        Args:
            key: Key to look up in custom settings.
            default: Default value if key not found.

        Returns:
            Value from custom or default.
        """
        return self.get_setting_value(f"custom.{key}", default)

    def set_custom_value(self, key: str, value: Any) -> None:
        """Set a value in the custom settings dict.

        Args:
            key: Key to set.
            value: Value to set.
        """
        self.set_setting_value(f"custom.{key}", value)

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "institution_key": self.institution_key,
            "institution_name": self.institution_name,
            "institution_type": self.institution_type,
            "enabled": self.enabled,
            "settings": self.settings,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary for list views."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "institution_key": self.institution_key,
            "institution_name": self.institution_name,
            "institution_type": self.institution_type,
            "enabled": self.enabled,
            "connection_type": self.connection_type,
            "auth_type": self.auth_type,
            "whatsapp_phone_number_id": self.whatsapp_phone_number_id,
            "display_label": f"{self.institution_name} ({self.connection_type.upper()})",
        }

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def create_medical_institution(
        cls,
        organization_id: uuid.UUID,
        institution_key: str,
        institution_name: str,
        base_url: str,
        connection_type: str = "soap",
        whatsapp_phone_number_id: str | None = None,
        timezone: str = "America/Argentina/San_Juan",
        **custom_settings: Any,
    ) -> "TenantInstitutionConfig":
        """Factory method to create a medical institution configuration.

        Args:
            organization_id: Organization UUID.
            institution_key: Unique key (e.g., "patologia_digestiva").
            institution_name: Human-readable name.
            base_url: Service endpoint URL.
            connection_type: "soap" or "rest".
            whatsapp_phone_number_id: Optional WhatsApp phone number ID.
            timezone: Timezone for scheduling.
            **custom_settings: Additional custom settings.

        Returns:
            Configured TenantInstitutionConfig instance.
        """
        settings = {
            "connection": {
                "type": connection_type,
                "base_url": base_url,
                "timeout_seconds": 30,
                "retry_count": 3,
            },
            "auth": {"type": "none"},
            "scheduler": {
                "enabled": True,
                "timezone": timezone,
                "morning_hour": 9,
                "evening_hour": 20,
            },
            "branding": {},
            "whatsapp": {
                "phone_number_id": whatsapp_phone_number_id,
            },
            "custom": custom_settings,
        }

        return cls(
            organization_id=organization_id,
            institution_key=institution_key,
            institution_name=institution_name,
            institution_type="medical",
            enabled=True,
            settings=settings,
        )
