# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Factory para obtener ChattigoAdapter por DID con cache de tokens.
#              Soporta multiples numeros WhatsApp con sus propias credenciales.
# Tenant-Aware: Yes - credentials are per-DID, linked to organizations.
# ============================================================================
"""
Chattigo Adapter Factory with Token Cache.

Provides:
- ChattigoTokenCache: In-memory JWT token cache with auto-refresh per DID
- ChattigoAdapterFactory: Factory to get configured adapters for specific DIDs

Token Management:
- Tokens expire after 8 hours (per Chattigo ISV spec)
- Auto-refresh occurs at configurable intervals (default: 7 hours)
- Tokens are cached in memory per DID
- Token invalidation on 401 errors

Usage:
    factory = ChattigoAdapterFactory(credential_service)
    adapter = await factory.get_adapter(db, did="5492644710400")
    await adapter.send_message(msisdn, message)
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import httpx

from app.core.tenancy import (
    ChattigoCredentialService,
    ChattigoCredentials,
    get_chattigo_credential_service,
)

from .models import ChattigoLoginRequest, ChattigoLoginResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ChattigoTokenError(Exception):
    """Error obtaining or refreshing Chattigo token."""

    pass


class ChattigoTokenCache:
    """
    In-memory cache for Chattigo JWT tokens with auto-refresh per DID.

    Each DID maintains its own token with independent refresh timing.
    Tokens are refreshed before expiration based on token_refresh_hours setting.

    Thread-safe via asyncio.Lock per DID operation.
    """

    # Token TTL: 8 hours (per Chattigo ISV spec)
    TOKEN_TTL_HOURS = 8

    def __init__(self) -> None:
        """Initialize token cache."""
        # {did: (token, expiry_timestamp)}
        self._tokens: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for token requests."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client and clear cache."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._tokens.clear()

    async def get_token(
        self, did: str, credentials: ChattigoCredentials
    ) -> str:
        """
        Get valid token for DID, refreshing if needed.

        Token refresh occurs at (TTL - (TTL - refresh_hours)) from expiry,
        which means refresh happens `refresh_hours` after token was obtained.

        Args:
            did: WhatsApp Business phone number (DID)
            credentials: Decrypted Chattigo credentials

        Returns:
            Valid JWT token string

        Raises:
            ChattigoTokenError: If token cannot be obtained
        """
        async with self._lock:
            cached = self._tokens.get(did)

            if cached:
                token, expiry = cached
                # Calculate when to refresh: refresh_hours after token was obtained
                # Token was obtained at: expiry - TTL_HOURS * 3600
                token_obtained_at = expiry - (self.TOKEN_TTL_HOURS * 3600)
                refresh_at = token_obtained_at + (credentials.token_refresh_hours * 3600)

                if time.time() < refresh_at:
                    return token  # Token still valid

                logger.info(f"Token for DID {did} needs refresh (age > {credentials.token_refresh_hours}h)")

            # Need to obtain/refresh token
            return await self._refresh_token(did, credentials)

    async def _refresh_token(
        self, did: str, credentials: ChattigoCredentials
    ) -> str:
        """
        Obtain new token from Chattigo ISV.

        Args:
            did: WhatsApp Business phone number (DID)
            credentials: Decrypted Chattigo credentials

        Returns:
            New JWT token string

        Raises:
            ChattigoTokenError: If authentication fails
        """
        client = await self._get_client()

        try:
            payload = ChattigoLoginRequest(
                username=credentials.username,
                password=credentials.password,
            )

            logger.debug(f"Obtaining token for DID {did} from {credentials.login_url}")

            response = await client.post(
                credentials.login_url,
                json=payload.model_dump(),
            )
            response.raise_for_status()

            # Parse response
            json_data = response.json()
            if not json_data:
                raise ChattigoTokenError(f"Login returned empty response for DID {did}")

            data = ChattigoLoginResponse(**json_data)
            token = data.access_token

            # Store with expiry (8 hours from now)
            expiry = time.time() + (self.TOKEN_TTL_HOURS * 3600)
            self._tokens[did] = (token, expiry)

            logger.info(
                f"Token obtained for DID {did}, "
                f"next refresh in {credentials.token_refresh_hours}h"
            )

            return token

        except httpx.HTTPError as e:
            logger.error(f"Failed to obtain token for DID {did}: {e}")
            raise ChattigoTokenError(f"Authentication failed for DID {did}: {e}") from e
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse login response for DID {did}: {e}")
            raise ChattigoTokenError(f"Login response parsing failed for DID {did}: {e}") from e

    def invalidate(self, did: str) -> None:
        """
        Invalidate cached token for DID.

        Call this after receiving 401 errors to force token refresh.

        Args:
            did: WhatsApp Business phone number (DID)
        """
        if did in self._tokens:
            del self._tokens[did]
            logger.info(f"Token invalidated for DID {did}")

    def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        now = time.time()
        dids_list: list[dict] = []
        for did, (_, expiry) in self._tokens.items():
            remaining = max(0, expiry - now)
            dids_list.append({
                "did": did,
                "expires_in_seconds": int(remaining),
                "expires_in_hours": round(remaining / 3600, 2),
            })
        return {
            "total_cached": len(self._tokens),
            "dids": dids_list,
        }


class ChattigoAdapterFactory:
    """
    Factory for obtaining ChattigoAdapter instances configured for specific DIDs.

    Uses credential service to fetch per-DID credentials and token cache
    for efficient token management.

    Usage:
        factory = ChattigoAdapterFactory()
        adapter = await factory.get_adapter(db, "5492644710400")
        await adapter.send_message(msisdn, message)
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
    ) -> "ChattigoMultiDIDAdapter":
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
    ) -> "ChattigoMultiDIDAdapter":
        """
        Get adapter using DID from webhook context.

        Extracts DID from chattigo_context and returns configured adapter.

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


class ChattigoMultiDIDAdapter:
    """
    Chattigo adapter for multi-DID support.

    Uses credentials from database and shared token cache.
    This is a lightweight adapter created per-request that shares
    the token cache across all instances.
    """

    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        credentials: ChattigoCredentials,
        token_cache: ChattigoTokenCache,
    ) -> None:
        """
        Initialize adapter with credentials and token cache.

        Args:
            credentials: Decrypted Chattigo credentials for this DID
            token_cache: Shared token cache
        """
        self._credentials = credentials
        self._token_cache = token_cache
        self._client: httpx.AsyncClient | None = None

    @property
    def did(self) -> str:
        """Get the DID this adapter is configured for."""
        return self._credentials.did

    @property
    def credentials(self) -> ChattigoCredentials:
        """Get the credentials (for inspection, not modification)."""
        return self._credentials

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT)

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "ChattigoMultiDIDAdapter":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            await self.initialize()
        return self._client  # type: ignore

    async def _get_token(self) -> str:
        """Get valid token for this adapter's DID."""
        return await self._token_cache.get_token(
            self._credentials.did,
            self._credentials,
        )

    def _get_headers(self, token: str) -> dict[str, str]:
        """Get request headers with authorization."""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def send_message(
        self,
        msisdn: str,
        message: str,
        sender_name: str | None = None,
    ) -> dict:
        """
        Send text message via Chattigo API.

        Args:
            msisdn: Recipient phone number
            message: Message content
            sender_name: Optional sender name (defaults to bot_name)

        Returns:
            API response dict

        Raises:
            ChattigoTokenError: If authentication fails
            httpx.HTTPError: If request fails
        """
        client = await self._ensure_client()
        token = await self._get_token()

        payload = {
            "id": str(int(time.time() * 1000)),
            "did": self._credentials.did,
            "msisdn": msisdn,
            "type": "text",
            "channel": "WHATSAPP",
            "chatType": "OUTBOUND",
            "content": message,
            "name": sender_name or self._credentials.bot_name,
            "isAttachment": False,
        }

        try:
            response = await client.post(
                self._credentials.message_url,
                headers=self._get_headers(token),
                json=payload,
            )

            # Handle 401 by invalidating token and retrying once
            if response.status_code == 401:
                logger.warning(f"Token expired for DID {self._credentials.did}, refreshing...")
                self._token_cache.invalidate(self._credentials.did)
                token = await self._get_token()
                response = await client.post(
                    self._credentials.message_url,
                    headers=self._get_headers(token),
                    json=payload,
                )

            response.raise_for_status()

            result = response.json() if response.text.strip() else {}
            logger.info(f"Message sent via DID {self._credentials.did} to {msisdn}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(f"Failed to send message via DID {self._credentials.did}: {e}")
            raise

    async def send_document(
        self,
        msisdn: str,
        document_url: str,
        filename: str,
        mime_type: str = "application/pdf",
        caption: str | None = None,
    ) -> dict:
        """
        Send document via Chattigo API.

        Args:
            msisdn: Recipient phone number
            document_url: Public URL of the document
            filename: Document filename
            mime_type: MIME type
            caption: Optional caption

        Returns:
            API response dict
        """
        client = await self._ensure_client()
        token = await self._get_token()

        payload = {
            "id": str(int(time.time() * 1000)),
            "did": self._credentials.did,
            "msisdn": msisdn,
            "type": "media",
            "channel": "WHATSAPP",
            "chatType": "OUTBOUND",
            "content": caption or "Documento adjunto.",
            "name": self._credentials.bot_name,
            "isAttachment": True,
            "attachment": {
                "mediaUrl": document_url,
                "mimeType": mime_type,
                "fileName": filename,
            },
        }

        try:
            response = await client.post(
                self._credentials.message_url,
                headers=self._get_headers(token),
                json=payload,
            )

            if response.status_code == 401:
                self._token_cache.invalidate(self._credentials.did)
                token = await self._get_token()
                response = await client.post(
                    self._credentials.message_url,
                    headers=self._get_headers(token),
                    json=payload,
                )

            response.raise_for_status()

            result = response.json() if response.text.strip() else {}
            logger.info(f"Document sent via DID {self._credentials.did} to {msisdn}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(f"Failed to send document via DID {self._credentials.did}: {e}")
            raise

    async def send_image(
        self,
        msisdn: str,
        image_url: str,
        caption: str | None = None,
        mime_type: str = "image/jpeg",
    ) -> dict:
        """
        Send image via Chattigo API.

        Args:
            msisdn: Recipient phone number
            image_url: Public URL of the image
            caption: Optional caption
            mime_type: MIME type

        Returns:
            API response dict
        """
        client = await self._ensure_client()
        token = await self._get_token()

        payload = {
            "id": str(int(time.time() * 1000)),
            "did": self._credentials.did,
            "msisdn": msisdn,
            "type": "media",
            "channel": "WHATSAPP",
            "chatType": "OUTBOUND",
            "content": caption or "",
            "name": self._credentials.bot_name,
            "isAttachment": True,
            "attachment": {
                "mediaUrl": image_url,
                "mimeType": mime_type,
            },
        }

        try:
            response = await client.post(
                self._credentials.message_url,
                headers=self._get_headers(token),
                json=payload,
            )

            if response.status_code == 401:
                self._token_cache.invalidate(self._credentials.did)
                token = await self._get_token()
                response = await client.post(
                    self._credentials.message_url,
                    headers=self._get_headers(token),
                    json=payload,
                )

            response.raise_for_status()

            result = response.json() if response.text.strip() else {}
            logger.info(f"Image sent via DID {self._credentials.did} to {msisdn}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(f"Failed to send image via DID {self._credentials.did}: {e}")
            raise

    async def health_check(self) -> dict:
        """
        Check connectivity and authentication.

        Returns:
            Health status dict
        """
        try:
            token = await self._get_token()
            return {
                "status": "healthy",
                "authenticated": True,
                "did": self._credentials.did,
                "name": self._credentials.name,
                "token_preview": f"{token[:20]}..." if len(token) > 20 else "***",
            }
        except Exception as e:
            logger.error(f"Health check failed for DID {self._credentials.did}: {e}")
            return {
                "status": "unhealthy",
                "authenticated": False,
                "did": self._credentials.did,
                "name": self._credentials.name,
                "error": str(e),
            }


# Singleton factory instance
_adapter_factory: ChattigoAdapterFactory | None = None


def get_chattigo_adapter_factory() -> ChattigoAdapterFactory:
    """Get singleton adapter factory instance."""
    global _adapter_factory
    if _adapter_factory is None:
        _adapter_factory = ChattigoAdapterFactory()
    return _adapter_factory
