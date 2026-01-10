# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Pydantic schemas for tenant configuration validation.
# Tenant-Aware: Yes - schemas define structure for tenant-specific settings.
# ============================================================================
"""
Pydantic schemas for tenant configuration.

Provides type-safe validation for JSONB configuration stored in database.
"""

from .institution_settings import (
    ApiKeyAuth,
    AuthConfig,
    BasicAuth,
    BrandingSettings,
    ConnectionSettings,
    ConnectionType,
    InstitutionSettings,
    NoAuth,
    OAuth2Auth,
    SchedulerSettings,
    SoapWssAuth,
    WhatsAppSettings,
)

__all__ = [
    # Connection
    "ConnectionType",
    "ConnectionSettings",
    # Auth types
    "NoAuth",
    "ApiKeyAuth",
    "BasicAuth",
    "OAuth2Auth",
    "SoapWssAuth",
    "AuthConfig",
    # Settings sections
    "SchedulerSettings",
    "BrandingSettings",
    "WhatsAppSettings",
    # Root schema
    "InstitutionSettings",
]
