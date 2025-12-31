# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Servicio para gestionar credenciales de tenant (WhatsApp, DUX, Plex).
#              Un registro de credenciales por organización.
# Tenant-Aware: Yes - todas las operaciones requieren organization_id.
# ============================================================================
"""
Tenant Credential Service - Organization-level credential management.

This service provides:
- Encrypted credential management for WhatsApp, DUX, and Plex integrations
- Type-safe credential DTOs for each integration type
- CRUD operations scoped to organization_id

Security:
- Uses CredentialEncryptionService for pgcrypto encryption
- Never exposes encrypted values - only returns decrypted DTOs

Usage:
    service = get_tenant_credential_service()

    # Get credentials (decrypted)
    whatsapp = await service.get_whatsapp_credentials(db, org_id)
    dux = await service.get_dux_credentials(db, org_id)
    plex = await service.get_plex_credentials(db, org_id)

    # Update credentials (encrypts automatically)
    await service.update_credentials(db, org_id, CredentialUpdateRequest(...))
"""

import logging
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.tenancy.tenant_credentials import TenantCredentials

from .credential_models import (
    CredentialUpdateRequest,
    DuxCredentials,
    PlexCredentials,
    WhatsAppCredentials,
)
from .encryption_service import CredentialEncryptionService, get_encryption_service

logger = logging.getLogger(__name__)


class CredentialNotFoundError(Exception):
    """Raised when credentials are not found for an organization."""

    pass


class TenantCredentialService:
    """
    Service for managing encrypted tenant credentials (WhatsApp, DUX, Plex).

    One credential record per organization. Uses CredentialEncryptionService
    for all encryption/decryption operations.
    """

    def __init__(self, encryption: CredentialEncryptionService | None = None) -> None:
        """Initialize the tenant credential service.

        Args:
            encryption: Optional encryption service. Uses singleton if not provided.
        """
        self._encryption = encryption or get_encryption_service()

    # =========================================================================
    # Private Helpers
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

    # =========================================================================
    # Get Credentials (Decrypted)
    # =========================================================================

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

        access_token = await self._encryption.decrypt_value(
            db, cast(str, creds.whatsapp_access_token_encrypted)
        )
        verify_token = await self._encryption.decrypt_value(
            db, cast(str, creds.whatsapp_verify_token_encrypted)
        )

        return WhatsAppCredentials(
            organization_id=organization_id,
            access_token=access_token,
            phone_number_id=cast(str, creds.whatsapp_phone_number_id),
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

        api_key = await self._encryption.decrypt_value(
            db, cast(str, creds.dux_api_key_encrypted)
        )

        return DuxCredentials(
            organization_id=organization_id,
            api_key=api_key,
            base_url=cast(str, creds.dux_api_base_url),
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

        password = await self._encryption.decrypt_value(
            db, cast(str, creds.plex_api_pass_encrypted)
        )

        return PlexCredentials(
            organization_id=organization_id,
            api_url=cast(str, creds.plex_api_url),
            username=cast(str, creds.plex_api_user),
            password=password,
        )

    # =========================================================================
    # Check Credentials Exist
    # =========================================================================

    async def has_credentials(self, db: AsyncSession, organization_id: UUID) -> bool:
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
    # Create/Update/Delete Credentials
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
        # Note: SQLAlchemy Column types are correctly handled at runtime
        if update.whatsapp_access_token is not None:
            creds.whatsapp_access_token_encrypted = await self._encryption.encrypt_value(  # type: ignore[assignment]
                db, update.whatsapp_access_token
            )
        if update.whatsapp_phone_number_id is not None:
            creds.whatsapp_phone_number_id = update.whatsapp_phone_number_id  # type: ignore[assignment]
        if update.whatsapp_verify_token is not None:
            creds.whatsapp_verify_token_encrypted = await self._encryption.encrypt_value(  # type: ignore[assignment]
                db, update.whatsapp_verify_token
            )

        # Update DUX fields
        if update.dux_api_key is not None:
            creds.dux_api_key_encrypted = await self._encryption.encrypt_value(  # type: ignore[assignment]
                db, update.dux_api_key
            )
        if update.dux_api_base_url is not None:
            creds.dux_api_base_url = update.dux_api_base_url  # type: ignore[assignment]

        # Update Plex fields
        if update.plex_api_url is not None:
            creds.plex_api_url = update.plex_api_url  # type: ignore[assignment]
        if update.plex_api_user is not None:
            creds.plex_api_user = update.plex_api_user  # type: ignore[assignment]
        if update.plex_api_pass is not None:
            creds.plex_api_pass_encrypted = await self._encryption.encrypt_value(  # type: ignore[assignment]
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


# Singleton instance
_tenant_credential_service: TenantCredentialService | None = None


def get_tenant_credential_service() -> TenantCredentialService:
    """Get the singleton tenant credential service instance."""
    global _tenant_credential_service
    if _tenant_credential_service is None:
        _tenant_credential_service = TenantCredentialService()
    return _tenant_credential_service
