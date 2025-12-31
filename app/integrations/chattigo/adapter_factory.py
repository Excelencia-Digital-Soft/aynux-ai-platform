# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Factory para obtener ChattigoAdapter por DID con cache de tokens.
#              Soporta multiples numeros WhatsApp con sus propias credenciales.
# Tenant-Aware: Yes - credentials are per-DID, linked to organizations.
# ============================================================================
"""
Chattigo Adapter Factory.

Single Responsibility: Create and configure adapter instances for specific DIDs.

Usage:
    factory = ChattigoAdapterFactory()
    adapter = await factory.get_adapter(db, did="5492644710400")
    await adapter.send_message(msisdn, message)

Components (extracted to separate modules for SRP):
- exceptions.py: ChattigoTokenError, ChattigoSendError
- token_cache.py: ChattigoTokenCache
- http_client.py: ChattigoHttpClient (with retry 401)
- payload_builder.py: ChattigoPayloadBuilder
- multi_did_adapter.py: ChattigoMultiDIDAdapter
"""

from typing import TYPE_CHECKING

from app.core.tenancy import (
    ChattigoCredentialService,
    get_chattigo_credential_service,
)

# Import from refactored modules
from .exceptions import ChattigoTokenError
from .multi_did_adapter import ChattigoMultiDIDAdapter
from .token_cache import ChattigoTokenCache

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Re-export for backward compatibility
__all__ = [
    "ChattigoAdapterFactory",
    "ChattigoTokenCache",
    "ChattigoTokenError",
    "ChattigoMultiDIDAdapter",
    "get_chattigo_adapter_factory",
]


class ChattigoAdapterFactory:
    """
    Factory for obtaining ChattigoAdapter instances configured for specific DIDs.

    Single Responsibility: Create and configure adapter instances.

    Uses credential service to fetch per-DID credentials and token cache
    for efficient token management.
    """

    def __init__(
        self,
        credential_service: ChattigoCredentialService | None = None,
        token_cache: ChattigoTokenCache | None = None,
    ) -> None:
        """
        Initialize adapter factory.

        Args:
            credential_service: Optional credential service (uses singleton if None)
            token_cache: Optional token cache (creates new if None)
        """
        self._credential_service = credential_service or get_chattigo_credential_service()
        self._token_cache = token_cache or ChattigoTokenCache()

    @property
    def token_cache(self) -> ChattigoTokenCache:
        """Access token cache for monitoring or manual operations."""
        return self._token_cache

    async def get_adapter(
        self, db: "AsyncSession", did: str
    ) -> ChattigoMultiDIDAdapter:
        """
        Get adapter configured for a specific DID.

        Args:
            db: Database session
            did: WhatsApp Business phone number (DID)

        Returns:
            ChattigoMultiDIDAdapter configured for the DID

        Raises:
            CredentialNotFoundError: If no credentials exist for DID
        """
        credentials = await self._credential_service.get_credentials_by_did(db, did)

        return ChattigoMultiDIDAdapter(
            credentials=credentials,
            token_cache=self._token_cache,
        )

    async def get_adapter_for_webhook(
        self, db: "AsyncSession", chattigo_context: dict
    ) -> ChattigoMultiDIDAdapter:
        """
        Get adapter using DID from webhook context.

        Args:
            db: Database session
            chattigo_context: Webhook context containing "did" key

        Returns:
            ChattigoMultiDIDAdapter configured for the context's DID

        Raises:
            ValueError: If no DID in context
            CredentialNotFoundError: If no credentials exist for DID
        """
        did = chattigo_context.get("did")
        if not did:
            raise ValueError("No DID in chattigo_context")

        return await self.get_adapter(db, did)

    async def close(self) -> None:
        """Close factory resources."""
        await self._token_cache.close()


# Singleton factory instance
_adapter_factory: ChattigoAdapterFactory | None = None


def get_chattigo_adapter_factory() -> ChattigoAdapterFactory:
    """Get singleton adapter factory instance."""
    global _adapter_factory
    if _adapter_factory is None:
        _adapter_factory = ChattigoAdapterFactory()
    return _adapter_factory
