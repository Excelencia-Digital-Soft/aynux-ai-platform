# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Pydantic schemas for institution settings validation.
# Tenant-Aware: Yes - defines structure for tenant-specific institution config.
# ============================================================================
"""
Institution Settings Pydantic Schemas.

Provides type-safe validation for JSONB settings stored in tenant_institution_configs.
Supports multiple connection types (SOAP, REST, GraphQL) and authentication methods
(API Key, Basic Auth, OAuth2, SOAP-WSS).

Usage:
    # Validate settings from database
    settings = InstitutionSettings.model_validate(db_record.settings)

    # Access typed fields
    base_url = settings.connection.base_url
    auth_type = settings.auth.type

    # Serialize back to JSON
    json_data = settings.model_dump()
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# Connection Settings
# =============================================================================


class ConnectionType(str, Enum):
    """Type of external service connection."""

    SOAP = "soap"
    REST = "rest"
    GRAPHQL = "graphql"


class ConnectionSettings(BaseModel):
    """External service connection configuration.

    Attributes:
        type: Connection protocol type (soap, rest, graphql).
        base_url: Base URL for the service endpoint.
        timeout_seconds: Request timeout in seconds.
        retry_count: Number of retry attempts on failure.
        verify_ssl: Whether to verify SSL certificates.
    """

    type: ConnectionType = ConnectionType.REST
    base_url: str = ""
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_count: int = Field(default=3, ge=0, le=10)
    verify_ssl: bool = True

    model_config = {"extra": "allow"}


# =============================================================================
# Authentication Settings
# =============================================================================


class NoAuth(BaseModel):
    """No authentication required."""

    type: Literal["none"] = "none"

    model_config = {"extra": "forbid"}


class ApiKeyAuth(BaseModel):
    """API Key authentication.

    The actual API key value should be stored in encrypted_secrets column,
    not in this settings JSONB.

    Attributes:
        type: Authentication type identifier.
        header_name: HTTP header name for the API key.
        query_param: Query parameter name (alternative to header).
        prefix: Prefix to add before the key (e.g., "Bearer ").
    """

    type: Literal["api_key"] = "api_key"
    header_name: str = "X-API-Key"
    query_param: str | None = None
    prefix: str = ""

    model_config = {"extra": "forbid"}


class BasicAuth(BaseModel):
    """HTTP Basic authentication.

    The password should be stored in encrypted_secrets column.

    Attributes:
        type: Authentication type identifier.
        username: Username for authentication.
    """

    type: Literal["basic"] = "basic"
    username: str = ""

    model_config = {"extra": "forbid"}


class OAuth2Auth(BaseModel):
    """OAuth2 authentication.

    The client_secret should be stored in encrypted_secrets column.

    Attributes:
        type: Authentication type identifier.
        token_url: OAuth2 token endpoint URL.
        client_id: OAuth2 client ID.
        scopes: List of OAuth2 scopes to request.
        grant_type: OAuth2 grant type.
    """

    type: Literal["oauth2"] = "oauth2"
    token_url: str = ""
    client_id: str = ""
    scopes: list[str] = Field(default_factory=list)
    grant_type: str = "client_credentials"

    model_config = {"extra": "forbid"}


class SoapWssAuth(BaseModel):
    """SOAP WS-Security authentication.

    The password should be stored in encrypted_secrets column.

    Attributes:
        type: Authentication type identifier.
        username: Username for WS-Security header.
        password_type: Password digest type.
        must_understand: WS-Security mustUnderstand attribute.
    """

    type: Literal["soap_wss"] = "soap_wss"
    username: str = ""
    password_type: str = "PasswordText"
    must_understand: bool = True

    model_config = {"extra": "forbid"}


# Union type for all authentication configs
AuthConfig = Annotated[
    NoAuth | ApiKeyAuth | BasicAuth | OAuth2Auth | SoapWssAuth,
    Field(discriminator="type"),
]


# =============================================================================
# Scheduler Settings
# =============================================================================


class SchedulerSettings(BaseModel):
    """Background task scheduler configuration.

    Used for reminders, notifications, and periodic tasks.

    Attributes:
        enabled: Whether scheduler tasks are active.
        timezone: Timezone for scheduling (IANA format).
        morning_hour: Hour for morning tasks (0-23).
        evening_hour: Hour for evening tasks (0-23).
        reminder_days_before: Days before appointment to send reminder.
    """

    enabled: bool = True
    timezone: str = "America/Argentina/San_Juan"
    morning_hour: int = Field(default=9, ge=0, le=23)
    evening_hour: int = Field(default=20, ge=0, le=23)
    reminder_days_before: int = Field(default=1, ge=0, le=30)

    model_config = {"extra": "allow"}


# =============================================================================
# Branding Settings
# =============================================================================


class BrandingSettings(BaseModel):
    """Institution branding and contact information.

    Attributes:
        address: Physical address.
        phone: Contact phone number.
        email: Contact email address.
        website: Website URL.
        logo_path: Path to logo image file.
        display_name: Name to display in messages (if different from institution_name).
    """

    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    logo_path: str | None = None
    display_name: str | None = None

    model_config = {"extra": "allow"}


# =============================================================================
# WhatsApp Settings
# =============================================================================


class WhatsAppSettings(BaseModel):
    """WhatsApp Business API integration settings.

    Attributes:
        phone_number_id: WhatsApp Business phone number ID for routing.
        business_account_id: WhatsApp Business Account ID.
        verify_token: Webhook verification token.
    """

    phone_number_id: str | None = None
    business_account_id: str | None = None
    verify_token: str | None = None

    model_config = {"extra": "allow"}


# =============================================================================
# Root Settings Schema
# =============================================================================


class InstitutionSettings(BaseModel):
    """Root schema for institution configuration.

    This is the main schema that validates the entire `settings` JSONB column
    in the tenant_institution_configs table.

    Example:
        ```python
        settings = InstitutionSettings(
            connection=ConnectionSettings(
                type=ConnectionType.SOAP,
                base_url="http://service.example.com/api",
                timeout_seconds=30,
            ),
            auth=ApiKeyAuth(header_name="Authorization", prefix="Bearer "),
            scheduler=SchedulerSettings(enabled=True, timezone="UTC"),
            branding=BrandingSettings(phone="+1234567890"),
            whatsapp=WhatsAppSettings(phone_number_id="123456789"),
            custom={"specialty_ids": ["1", "2", "3"]},
        )
        ```

    Attributes:
        connection: External service connection configuration.
        auth: Authentication configuration (discriminated union).
        scheduler: Background task scheduler settings.
        branding: Institution branding and contact info.
        whatsapp: WhatsApp Business API settings.
        custom: Arbitrary key-value pairs for institution-specific config.
    """

    connection: ConnectionSettings = Field(default_factory=ConnectionSettings)
    auth: AuthConfig = Field(default_factory=NoAuth)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    branding: BrandingSettings = Field(default_factory=BrandingSettings)
    whatsapp: WhatsAppSettings = Field(default_factory=WhatsAppSettings)
    custom: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    def get_custom_value(self, key: str, default: Any = None) -> Any:
        """Get a value from the custom dict.

        Args:
            key: Key to look up.
            default: Default value if key not found.

        Returns:
            Value from custom dict or default.
        """
        return self.custom.get(key, default)

    @classmethod
    def from_legacy_columns(
        cls,
        *,
        soap_url: str | None = None,
        soap_timeout: int = 30,
        api_type: str = "soap",
        reminder_enabled: bool = True,
        reminder_timezone: str = "America/Argentina/San_Juan",
        reminder_morning_hour: int = 9,
        reminder_evening_hour: int = 20,
        institution_address: str | None = None,
        institution_phone: str | None = None,
        institution_email: str | None = None,
        institution_website: str | None = None,
        institution_logo_path: str | None = None,
        whatsapp_phone_number_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> "InstitutionSettings":
        """Create InstitutionSettings from legacy column values.

        Used during migration to convert fixed columns to JSONB structure.

        Args:
            soap_url: Legacy soap_url column.
            soap_timeout: Legacy soap_timeout column.
            api_type: Legacy api_type column ("soap" or "rest").
            reminder_enabled: Legacy reminder_enabled column.
            reminder_timezone: Legacy reminder_timezone column.
            reminder_morning_hour: Legacy reminder_morning_hour column.
            reminder_evening_hour: Legacy reminder_evening_hour column.
            institution_address: Legacy institution_address column.
            institution_phone: Legacy institution_phone column.
            institution_email: Legacy institution_email column.
            institution_website: Legacy institution_website column.
            institution_logo_path: Legacy institution_logo_path column.
            whatsapp_phone_number_id: Legacy whatsapp_phone_number_id column.
            config: Legacy config JSONB column (merged into custom).

        Returns:
            New InstitutionSettings instance.
        """
        # Map api_type to ConnectionType
        conn_type = ConnectionType.SOAP if api_type == "soap" else ConnectionType.REST

        return cls(
            connection=ConnectionSettings(
                type=conn_type,
                base_url=soap_url or "",
                timeout_seconds=soap_timeout,
            ),
            auth=NoAuth(),  # Default to no auth, can be configured later
            scheduler=SchedulerSettings(
                enabled=reminder_enabled,
                timezone=reminder_timezone,
                morning_hour=reminder_morning_hour,
                evening_hour=reminder_evening_hour,
            ),
            branding=BrandingSettings(
                address=institution_address,
                phone=institution_phone,
                email=institution_email,
                website=institution_website,
                logo_path=institution_logo_path,
            ),
            whatsapp=WhatsAppSettings(
                phone_number_id=whatsapp_phone_number_id,
            ),
            custom=config or {},
        )
