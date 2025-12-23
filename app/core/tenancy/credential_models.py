# ============================================================================
# SCOPE: MULTI-TENANT
# Description: DTOs para credenciales desencriptadas. Usados por credential_service
#              para retornar credenciales listas para usar.
# Tenant-Aware: Yes - cada instancia corresponde a una organizaci贸n espec铆fica.
# ============================================================================
"""
Credential DTOs for the credential service.

These dataclasses represent decrypted credentials ready for use by integrations.
They never contain encrypted data - that stays in the database model.

Usage:
    credentials = await credential_service.get_whatsapp_credentials(db, org_id)
    # credentials is a WhatsAppCredentials instance with plain text values
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class WhatsAppCredentials:
    """
    Decrypted WhatsApp Business API credentials.

    Attributes:
        organization_id: The organization these credentials belong to
        access_token: Graph API access token (APP_USR-xxx format)
        phone_number_id: WhatsApp Business phone number ID
        verify_token: Webhook verification token

    Usage:
        creds = await credential_service.get_whatsapp_credentials(db, org_id)
        headers = {"Authorization": f"Bearer {creds.access_token}"}
    """

    organization_id: UUID
    access_token: str
    phone_number_id: str
    verify_token: str

    def __repr__(self) -> str:
        """Mask access token in repr for security."""
        masked_token = f"{self.access_token[:10]}..." if self.access_token else "None"
        return (
            f"WhatsAppCredentials("
            f"org_id={self.organization_id}, "
            f"phone_number_id={self.phone_number_id}, "
            f"access_token={masked_token})"
        )


@dataclass(frozen=True)
class DuxCredentials:
    """
    Decrypted DUX ERP API credentials.

    Attributes:
        organization_id: The organization these credentials belong to
        api_key: DUX API authentication token
        base_url: DUX API base URL

    Usage:
        creds = await credential_service.get_dux_credentials(db, org_id)
        headers = {"Authorization": f"Bearer {creds.api_key}"}
        url = f"{creds.base_url}/products"
    """

    organization_id: UUID
    api_key: str
    base_url: str

    def __repr__(self) -> str:
        """Mask API key in repr for security."""
        masked_key = f"{self.api_key[:8]}..." if self.api_key else "None"
        return (
            f"DuxCredentials("
            f"org_id={self.organization_id}, "
            f"base_url={self.base_url}, "
            f"api_key={masked_key})"
        )


@dataclass(frozen=True)
class PlexCredentials:
    """
    Decrypted Plex ERP API credentials.

    Attributes:
        organization_id: The organization these credentials belong to
        api_url: Plex ERP API URL
        username: Plex ERP username
        password: Plex ERP password

    Usage:
        creds = await credential_service.get_plex_credentials(db, org_id)
        auth = httpx.BasicAuth(creds.username, creds.password)
    """

    organization_id: UUID
    api_url: str
    username: str
    password: str

    def __repr__(self) -> str:
        """Mask password in repr for security."""
        return (
            f"PlexCredentials("
            f"org_id={self.organization_id}, "
            f"api_url={self.api_url}, "
            f"username={self.username}, "
            f"password=***)"
        )


@dataclass(frozen=True)
class CredentialUpdateRequest:
    """
    Request DTO for updating credentials via Admin API.

    All fields are optional - only provided fields will be updated.
    Encrypted fields will be encrypted before storage.
    """

    # WhatsApp
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_verify_token: str | None = None

    # DUX
    dux_api_key: str | None = None
    dux_api_base_url: str | None = None

    # Plex
    plex_api_url: str | None = None
    plex_api_user: str | None = None
    plex_api_pass: str | None = None

    def has_whatsapp_updates(self) -> bool:
        """Check if any WhatsApp fields are being updated."""
        return any([
            self.whatsapp_access_token is not None,
            self.whatsapp_phone_number_id is not None,
            self.whatsapp_verify_token is not None,
        ])

    def has_dux_updates(self) -> bool:
        """Check if any DUX fields are being updated."""
        return any([
            self.dux_api_key is not None,
            self.dux_api_base_url is not None,
        ])

    def has_plex_updates(self) -> bool:
        """Check if any Plex fields are being updated."""
        return any([
            self.plex_api_url is not None,
            self.plex_api_user is not None,
            self.plex_api_pass is not None,
        ])
