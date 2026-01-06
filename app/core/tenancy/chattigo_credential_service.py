# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Servicio para gestionar credenciales Chattigo (multi-DID).
#              Múltiples registros por organización, indexados por DID.
# Tenant-Aware: Yes - cada DID está asociado a una organization_id.
# ============================================================================
"""
Chattigo Credential Service - Multi-DID credential management.

This service provides:
- Encrypted credential management for Chattigo ISV integration
- Multi-DID support (multiple WhatsApp Business numbers per organization)
- Type-safe credential DTOs with configuration options

Security:
- Uses CredentialEncryptionService for pgcrypto encryption
- Never exposes encrypted values - only returns decrypted DTOs

Usage:
    service = get_chattigo_credential_service()

    # Get credentials (decrypted)
    creds = await service.get_credentials_by_did(db, "5491112345678")
    all_creds = await service.get_all_credentials(db, org_id)

    # Create/Update credentials (encrypts automatically)
    await service.create_credentials(db, ChattigoCredentialCreateRequest(...))
    await service.update_credentials(db, did, ChattigoCredentialUpdateRequest(...))
"""

import logging
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.tenancy.chattigo_credentials import (
    ChattigoCredentials as ChattigoCredentialsModel,
)

from .credential_models import (
    ChattigoCredentialCreateRequest,
    ChattigoCredentials,
    ChattigoCredentialUpdateRequest,
)
from .encryption_service import (
    CredentialEncryptionError,
    CredentialEncryptionService,
    get_encryption_service,
)

logger = logging.getLogger(__name__)


class ChattigoNotFoundError(Exception):
    """Raised when Chattigo credentials are not found for a DID."""

    pass


class ChattigoCredentialService:
    """
    Service for managing encrypted Chattigo credentials (multi-DID).

    Multiple credential records per organization, indexed by DID.
    Uses CredentialEncryptionService for all encryption/decryption operations.
    """

    def __init__(self, encryption: CredentialEncryptionService | None = None) -> None:
        """Initialize the Chattigo credential service.

        Args:
            encryption: Optional encryption service. Uses singleton if not provided.
        """
        self._encryption = encryption or get_encryption_service()

    # =========================================================================
    # Private Helpers
    # =========================================================================

    async def _get_credentials_model(
        self, db: AsyncSession, did: str
    ) -> ChattigoCredentialsModel:
        """Get raw ChattigoCredentials model for a DID.

        Args:
            db: Database session
            did: WhatsApp Business phone number (DID)

        Returns:
            ChattigoCredentialsModel from database

        Raises:
            ChattigoNotFoundError: If no credentials exist for this DID
        """
        result = await db.execute(
            select(ChattigoCredentialsModel).where(
                ChattigoCredentialsModel.did == did,
                ChattigoCredentialsModel.enabled == True,  # noqa: E712
            )
        )
        creds = result.scalar_one_or_none()

        if creds is None:
            raise ChattigoNotFoundError(
                f"No Chattigo credentials found for DID {did}. "
                "Use the Admin API to configure credentials."
            )

        return creds

    # =========================================================================
    # Get Credentials (Decrypted)
    # =========================================================================

    async def get_credentials_by_did(
        self, db: AsyncSession, did: str
    ) -> ChattigoCredentials:
        """Get decrypted Chattigo credentials for a DID.

        Args:
            db: Database session
            did: WhatsApp Business phone number (DID)

        Returns:
            ChattigoCredentials DTO with decrypted values

        Raises:
            ChattigoNotFoundError: If credentials don't exist
            CredentialEncryptionError: If decryption fails
        """
        creds = await self._get_credentials_model(db, did)

        # Decrypt username and password
        username = await self._encryption.decrypt_value(
            db, cast(str, creds.username_encrypted)
        )
        password = await self._encryption.decrypt_value(
            db, cast(str, creds.password_encrypted)
        )

        return ChattigoCredentials(
            did=cast(str, creds.did),
            name=cast(str, creds.name),
            username=username,
            password=password,
            login_url=cast(str, creds.login_url),
            base_url=cast(str, creds.base_url),
            bot_name=cast(str, creds.bot_name),
            token_refresh_hours=cast(int, creds.token_refresh_hours),
            organization_id=cast(UUID, creds.organization_id),
            bypass_rule_id=creds.bypass_rule_id,
            enabled=True,  # This method only returns enabled credentials
        )

    async def get_all_credentials(
        self,
        db: AsyncSession,
        organization_id: UUID | None = None,
        include_disabled: bool = False,
    ) -> list[ChattigoCredentials]:
        """List all Chattigo credentials, optionally filtered by organization.

        Args:
            db: Database session
            organization_id: Optional organization UUID to filter by
            include_disabled: If True, include disabled credentials (for admin listing)

        Returns:
            List of ChattigoCredentials DTOs with decrypted values
        """
        query = select(ChattigoCredentialsModel)

        # Only filter by enabled if not including disabled (for integration use)
        if not include_disabled:
            query = query.where(
                ChattigoCredentialsModel.enabled == True  # noqa: E712
            )

        if organization_id is not None:
            query = query.where(
                ChattigoCredentialsModel.organization_id == organization_id
            )

        result = await db.execute(query)
        models = result.scalars().all()

        credentials = []
        for model in models:
            try:
                username = await self._encryption.decrypt_value(
                    db, cast(str, model.username_encrypted)
                )
                password = await self._encryption.decrypt_value(
                    db, cast(str, model.password_encrypted)
                )

                credentials.append(
                    ChattigoCredentials(
                        did=cast(str, model.did),
                        name=cast(str, model.name),
                        username=username,
                        password=password,
                        login_url=cast(str, model.login_url),
                        base_url=cast(str, model.base_url),
                        bot_name=cast(str, model.bot_name),
                        token_refresh_hours=cast(int, model.token_refresh_hours),
                        organization_id=cast(UUID, model.organization_id),
                        bypass_rule_id=model.bypass_rule_id,
                        enabled=cast(bool, model.enabled),
                    )
                )
            except CredentialEncryptionError as e:
                logger.warning(
                    f"Failed to decrypt credentials for DID {model.did}: {e}"
                )
                continue

        return credentials

    # =========================================================================
    # Check Credentials Exist
    # =========================================================================

    async def has_credentials(self, db: AsyncSession, did: str) -> bool:
        """Check if Chattigo credentials exist for a DID.

        Args:
            db: Database session
            did: WhatsApp Business phone number (DID)

        Returns:
            True if enabled credentials exist
        """
        result = await db.execute(
            select(ChattigoCredentialsModel.id).where(
                ChattigoCredentialsModel.did == did,
                ChattigoCredentialsModel.enabled == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none() is not None

    # =========================================================================
    # Create/Update/Delete Credentials
    # =========================================================================

    async def create_credentials(
        self,
        db: AsyncSession,
        request: ChattigoCredentialCreateRequest,
    ) -> ChattigoCredentials:
        """Create new Chattigo credentials for a DID.

        Args:
            db: Database session
            request: ChattigoCredentialCreateRequest with credential data

        Returns:
            Created ChattigoCredentials DTO

        Raises:
            CredentialEncryptionError: If encryption fails
            ValueError: If DID already exists
        """
        # Check if DID already exists
        existing = await db.execute(
            select(ChattigoCredentialsModel.id).where(
                ChattigoCredentialsModel.did == request.did
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(
                f"Chattigo credentials for DID {request.did} already exist"
            )

        # Encrypt username and password
        username_encrypted = await self._encryption.encrypt_value(db, request.username)
        password_encrypted = await self._encryption.encrypt_value(db, request.password)

        # Create model with defaults for optional fields
        creds = ChattigoCredentialsModel(
            did=request.did,
            name=request.name,
            username_encrypted=username_encrypted,
            password_encrypted=password_encrypted,
            organization_id=request.organization_id,
            bypass_rule_id=request.bypass_rule_id,
        )

        # Apply optional overrides
        if request.login_url is not None:
            creds.login_url = request.login_url
        if request.base_url is not None:
            creds.base_url = request.base_url
        if request.bot_name is not None:
            creds.bot_name = request.bot_name
        if request.token_refresh_hours is not None:
            creds.token_refresh_hours = request.token_refresh_hours

        db.add(creds)
        await db.flush()

        logger.info(f"Created Chattigo credentials for DID {request.did}")

        return ChattigoCredentials(
            did=cast(str, creds.did),
            name=cast(str, creds.name),
            username=request.username,  # Return plaintext (not encrypted)
            password=request.password,  # Return plaintext (not encrypted)
            login_url=cast(str, creds.login_url),
            base_url=cast(str, creds.base_url),
            bot_name=cast(str, creds.bot_name),
            token_refresh_hours=cast(int, creds.token_refresh_hours),
            organization_id=cast(UUID, creds.organization_id),
            bypass_rule_id=creds.bypass_rule_id,
            enabled=True,  # New credentials are always enabled
        )

    async def update_credentials(
        self,
        db: AsyncSession,
        did: str,
        request: ChattigoCredentialUpdateRequest,
    ) -> ChattigoCredentials:
        """Update existing Chattigo credentials.

        Args:
            db: Database session
            did: WhatsApp Business phone number (DID)
            request: ChattigoCredentialUpdateRequest with fields to update

        Returns:
            Updated ChattigoCredentials DTO

        Raises:
            ChattigoNotFoundError: If credentials don't exist
            CredentialEncryptionError: If encryption fails
        """
        # Get existing credentials (ignores enabled status for updates)
        result = await db.execute(
            select(ChattigoCredentialsModel).where(ChattigoCredentialsModel.did == did)
        )
        creds = result.scalar_one_or_none()

        if creds is None:
            raise ChattigoNotFoundError(
                f"No Chattigo credentials found for DID {did}"
            )

        # Update credential fields
        if request.username is not None:
            creds.username_encrypted = await self._encryption.encrypt_value(
                db, request.username
            )
        if request.password is not None:
            creds.password_encrypted = await self._encryption.encrypt_value(
                db, request.password
            )

        # Update config fields
        if request.name is not None:
            creds.name = request.name
        if request.login_url is not None:
            creds.login_url = request.login_url
        if request.base_url is not None:
            creds.base_url = request.base_url
        if request.bot_name is not None:
            creds.bot_name = request.bot_name
        if request.token_refresh_hours is not None:
            creds.token_refresh_hours = request.token_refresh_hours
        if request.enabled is not None:
            creds.enabled = request.enabled
        if request.bypass_rule_id is not None:
            creds.bypass_rule_id = request.bypass_rule_id

        await db.flush()

        logger.info(f"Updated Chattigo credentials for DID {did}")

        # Return updated credentials (decrypt for response)
        return await self.get_credentials_by_did(db, did)

    async def delete_credentials(self, db: AsyncSession, did: str) -> bool:
        """Delete Chattigo credentials for a DID.

        Args:
            db: Database session
            did: WhatsApp Business phone number (DID)

        Returns:
            True if deleted, False if not found
        """
        result = await db.execute(
            select(ChattigoCredentialsModel).where(ChattigoCredentialsModel.did == did)
        )
        creds = result.scalar_one_or_none()

        if creds is None:
            return False

        await db.delete(creds)
        await db.flush()

        logger.info(f"Deleted Chattigo credentials for DID {did}")
        return True


# Singleton instance
_chattigo_credential_service: ChattigoCredentialService | None = None


def get_chattigo_credential_service() -> ChattigoCredentialService:
    """Get the singleton Chattigo credential service instance."""
    global _chattigo_credential_service
    if _chattigo_credential_service is None:
        _chattigo_credential_service = ChattigoCredentialService()
    return _chattigo_credential_service
