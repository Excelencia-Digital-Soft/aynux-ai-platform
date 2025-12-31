# ============================================================================
# SCOPE: INFRASTRUCTURE
# Description: Servicio de encriptación/desencriptación con pgcrypto.
#              Infraestructura compartida para todos los servicios de credenciales.
# ============================================================================
"""
Credential Encryption Service - pgcrypto-based encryption infrastructure.

This service provides:
- Symmetric encryption/decryption using PostgreSQL pgcrypto extension
- AES-256 encryption with pgp_sym_encrypt/pgp_sym_decrypt
- Environment-based key management

Security:
- Encryption key stored in CREDENTIAL_ENCRYPTION_KEY environment variable
- Never exposes encryption key in logs or error messages

Usage:
    service = CredentialEncryptionService()
    encrypted = await service.encrypt_value(db, "sensitive_data")
    decrypted = await service.decrypt_value(db, encrypted)
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class CredentialEncryptionError(Exception):
    """Raised when encryption/decryption fails."""

    pass


class CredentialEncryptionService:
    """
    Service for encrypting and decrypting credential values using pgcrypto.

    Uses PostgreSQL pgcrypto extension for symmetric AES-256 encryption.
    All values are base64-encoded for storage.
    """

    def __init__(self) -> None:
        """Initialize the encryption service."""
        self._encryption_key: str | None = None

    @property
    def encryption_key(self) -> str:
        """Get the encryption key from settings.

        Raises:
            CredentialEncryptionError: If key is not configured.
        """
        if self._encryption_key is None:
            settings = get_settings()
            key = settings.CREDENTIAL_ENCRYPTION_KEY
            if not key:
                raise CredentialEncryptionError(
                    "Missing CREDENTIAL_ENCRYPTION_KEY in settings. "
                    'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
                )
            self._encryption_key = key
        return self._encryption_key

    async def encrypt_value(self, db: AsyncSession, value: str) -> str:
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
        except CredentialEncryptionError:
            raise
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise CredentialEncryptionError(f"Failed to encrypt value: {e}") from e

    async def decrypt_value(self, db: AsyncSession, encrypted: str) -> str:
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
        except CredentialEncryptionError:
            raise
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise CredentialEncryptionError(f"Failed to decrypt value: {e}") from e


# Singleton instance
_encryption_service: CredentialEncryptionService | None = None


def get_encryption_service() -> CredentialEncryptionService:
    """Get the singleton encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = CredentialEncryptionService()
    return _encryption_service
