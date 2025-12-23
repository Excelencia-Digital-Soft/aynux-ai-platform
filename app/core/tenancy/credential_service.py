# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Servicio para gestionar credenciales encriptadas por tenant.
#              Usa pgcrypto para encriptar/desencriptar en PostgreSQL.
# Tenant-Aware: Yes - todas las operaciones requieren organization_id.
# ============================================================================
"""
Tenant Credential Service - Encrypted credential management with pgcrypto.

This service provides:
- Encryption/decryption of sensitive credentials using PostgreSQL pgcrypto
- Type-safe credential DTOs for each integration (WhatsApp, DUX, Plex)
- CRUD operations for tenant credentials

Security:
- Uses pgp_sym_encrypt/pgp_sym_decrypt for AES-256 encryption
- Encryption key stored in CREDENTIAL_ENCRYPTION_KEY environment variable
- Never exposes encrypted values - only returns decrypted DTOs

Usage:
    service = TenantCredentialService()

    # Get credentials (decrypted)
    whatsapp = await service.get_whatsapp_credentials(db, org_id)
    dux = await service.get_dux_credentials(db, org_id)
    plex = await service.get_plex_credentials(db, org_id)

    # Update credentials (encrypts automatically)
    await service.update_credentials(db, org_id, CredentialUpdateRequest(...))
"""

import logging
import os
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.tenancy.tenant_credentials import TenantCredentials

from .credential_models import (
    CredentialUpdateRequest,
    DuxCredentials,
    PlexCredentials,
    WhatsAppCredentials,
)

logger = logging.getLogger(__name__)


class CredentialNotFoundError(Exception):
    """Raised when credentials are not found for an organization."""

    pass


class CredentialEncryptionError(Exception):
    """Raised when encryption/decryption fails."""

    pass


class TenantCredentialService:
    """
    Service for managing encrypted tenant credentials.

    Uses PostgreSQL pgcrypto extension for symmetric encryption.
    All sensitive data is encrypted at rest and decrypted on-demand.
    """

    ENCRYPTION_KEY_ENV = "CREDENTIAL_ENCRYPTION_KEY"

    def __init__(self) -> None:
        """Initialize the credential service."""
        self._encryption_key: str | None = None

    @property
    def encryption_key(self) -> str:
        """Get the encryption key from environment.

        Raises:
            CredentialEncryptionError: If key is not configured.
        """
        if self._encryption_key is None:
            key = os.environ.get(self.ENCRYPTION_KEY_ENV)
            if not key:
                raise CredentialEncryptionError(
                    f"Missing {self.ENCRYPTION_KEY_ENV} environment variable. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            self._encryption_key = key
        return self._encryption_key

    # =========================================================================
    # Encryption/Decryption Helpers
    # =========================================================================

    async def _encrypt_value(self, db: AsyncSession, value: str) -> str:
        """Encrypt a value using pgcrypto.

        Args:
            db: Database session
            value: Plain text value to encrypt

        Returns:
            Base64-encoded encrypted value

        Raises:
            CredentialEncryptionError: If encryption fails
        """
        try:
            result = await db.execute(
                text("SELECT encode(pgp_sym_encrypt(:value, :key), 'base64')"),
                {"value": value, "key": self.encryption_key},
            )
            encrypted = result.scalar()
            if encrypted is None:
                raise CredentialEncryptionError("pgcrypto encryption returned NULL")
            return encrypted
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise CredentialEncryptionError(f"Failed to encrypt value: {e}") from e

    async def _decrypt_value(self, db: AsyncSession, encrypted: str) -> str:
        """Decrypt a value using pgcrypto.

        Args:
            db: Database session
            encrypted: Base64-encoded encrypted value

        Returns:
            Decrypted plain text value

        Raises:
            CredentialEncryptionError: If decryption fails
        """
        try:
            result = await db.execute(
                text("SELECT pgp_sym_decrypt(decode(:encrypted, 'base64'), :key)"),
                {"encrypted": encrypted, "key": self.encryption_key},
            )
            decrypted = result.scalar()
            if decrypted is None:
                raise CredentialEncryptionError(
                    "pgcrypto decryption returned NULL - wrong key?"
                )
            return decrypted
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise CredentialEncryptionError(f"Failed to decrypt value: {e}") from e

    # =========================================================================
    # Get Credentials (Decrypted)
    # =========================================================================

    async def _get_tenant_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> TenantCredentials:
        """Get raw TenantCredentials model for an organization.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            TenantCredentials model

        Raises:
            CredentialNotFoundError: If no credentials exist
        """
        result = await db.execute(
            select(TenantCredentials).where(
                TenantCredentials.organization_id == organization_id
            )
        )
        creds = result.scalar_one_or_none()

        if creds is None:
            raise CredentialNotFoundError(
                f"No credentials found for organization {organization_id}. "
                "Use the Admin API to configure credentials."
            )

        return creds

    async def get_whatsapp_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> WhatsAppCredentials:
        """Get decrypted WhatsApp credentials for an organization.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            WhatsAppCredentials DTO with decrypted values

        Raises:
            CredentialNotFoundError: If credentials don't exist
            CredentialEncryptionError: If decryption fails
            ValueError: If required fields are missing
        """
        creds = await self._get_tenant_credentials(db, organization_id)

        if not creds.has_whatsapp_credentials():
            raise ValueError(
                f"Incomplete WhatsApp credentials for organization {organization_id}. "
                "Required: access_token, phone_number_id, verify_token"
            )

        access_token = await self._decrypt_value(
            db, creds.whatsapp_access_token_encrypted
        )
        verify_token = await self._decrypt_value(
            db, creds.whatsapp_verify_token_encrypted
        )

        return WhatsAppCredentials(
            organization_id=organization_id,
            access_token=access_token,
            phone_number_id=creds.whatsapp_phone_number_id,
            verify_token=verify_token,
        )

    async def get_dux_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> DuxCredentials:
        """Get decrypted DUX credentials for an organization.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            DuxCredentials DTO with decrypted values

        Raises:
            CredentialNotFoundError: If credentials don't exist
            CredentialEncryptionError: If decryption fails
            ValueError: If required fields are missing
        """
        creds = await self._get_tenant_credentials(db, organization_id)

        if not creds.has_dux_credentials():
            raise ValueError(
                f"Incomplete DUX credentials for organization {organization_id}. "
                "Required: api_key, base_url"
            )

        api_key = await self._decrypt_value(db, creds.dux_api_key_encrypted)

        return DuxCredentials(
            organization_id=organization_id,
            api_key=api_key,
            base_url=creds.dux_api_base_url,
        )

    async def get_plex_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> PlexCredentials:
        """Get decrypted Plex credentials for an organization.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            PlexCredentials DTO with decrypted values

        Raises:
            CredentialNotFoundError: If credentials don't exist
            CredentialEncryptionError: If decryption fails
            ValueError: If required fields are missing
        """
        creds = await self._get_tenant_credentials(db, organization_id)

        if not creds.has_plex_credentials():
            raise ValueError(
                f"Incomplete Plex credentials for organization {organization_id}. "
                "Required: api_url, username, password"
            )

        password = await self._decrypt_value(db, creds.plex_api_pass_encrypted)

        return PlexCredentials(
            organization_id=organization_id,
            api_url=creds.plex_api_url,
            username=creds.plex_api_user,
            password=password,
        )

    # =========================================================================
    # Check Credentials Exist
    # =========================================================================

    async def has_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> bool:
        """Check if any credentials exist for an organization.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            True if credentials record exists
        """
        result = await db.execute(
            select(TenantCredentials.id).where(
                TenantCredentials.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def has_whatsapp_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> bool:
        """Check if WhatsApp credentials are configured."""
        try:
            creds = await self._get_tenant_credentials(db, organization_id)
            return creds.has_whatsapp_credentials()
        except CredentialNotFoundError:
            return False

    async def has_dux_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> bool:
        """Check if DUX credentials are configured."""
        try:
            creds = await self._get_tenant_credentials(db, organization_id)
            return creds.has_dux_credentials()
        except CredentialNotFoundError:
            return False

    async def has_plex_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> bool:
        """Check if Plex credentials are configured."""
        try:
            creds = await self._get_tenant_credentials(db, organization_id)
            return creds.has_plex_credentials()
        except CredentialNotFoundError:
            return False

    # =========================================================================
    # Create/Update Credentials
    # =========================================================================

    async def create_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> TenantCredentials:
        """Create empty credentials record for an organization.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            Created TenantCredentials model
        """
        creds = TenantCredentials(organization_id=organization_id)
        db.add(creds)
        await db.flush()
        logger.info(f"Created credentials record for organization {organization_id}")
        return creds

    async def update_credentials(
        self,
        db: AsyncSession,
        organization_id: UUID,
        update: CredentialUpdateRequest,
    ) -> TenantCredentials:
        """Update credentials for an organization.

        Creates the credentials record if it doesn't exist.
        Only updates fields that are provided (not None).

        Args:
            db: Database session
            organization_id: Organization UUID
            update: CredentialUpdateRequest with fields to update

        Returns:
            Updated TenantCredentials model
        """
        # Get or create credentials
        try:
            creds = await self._get_tenant_credentials(db, organization_id)
        except CredentialNotFoundError:
            creds = await self.create_credentials(db, organization_id)

        # Update WhatsApp fields
        if update.whatsapp_access_token is not None:
            creds.whatsapp_access_token_encrypted = await self._encrypt_value(
                db, update.whatsapp_access_token
            )
        if update.whatsapp_phone_number_id is not None:
            creds.whatsapp_phone_number_id = update.whatsapp_phone_number_id
        if update.whatsapp_verify_token is not None:
            creds.whatsapp_verify_token_encrypted = await self._encrypt_value(
                db, update.whatsapp_verify_token
            )

        # Update DUX fields
        if update.dux_api_key is not None:
            creds.dux_api_key_encrypted = await self._encrypt_value(
                db, update.dux_api_key
            )
        if update.dux_api_base_url is not None:
            creds.dux_api_base_url = update.dux_api_base_url

        # Update Plex fields
        if update.plex_api_url is not None:
            creds.plex_api_url = update.plex_api_url
        if update.plex_api_user is not None:
            creds.plex_api_user = update.plex_api_user
        if update.plex_api_pass is not None:
            creds.plex_api_pass_encrypted = await self._encrypt_value(
                db, update.plex_api_pass
            )

        await db.flush()
        logger.info(f"Updated credentials for organization {organization_id}")
        return creds

    async def delete_credentials(
        self, db: AsyncSession, organization_id: UUID
    ) -> bool:
        """Delete credentials for an organization.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            creds = await self._get_tenant_credentials(db, organization_id)
            await db.delete(creds)
            await db.flush()
            logger.info(f"Deleted credentials for organization {organization_id}")
            return True
        except CredentialNotFoundError:
            return False


# Singleton instance for convenience
_credential_service: TenantCredentialService | None = None


def get_credential_service() -> TenantCredentialService:
    """Get the singleton credential service instance."""
    global _credential_service
    if _credential_service is None:
        _credential_service = TenantCredentialService()
    return _credential_service
