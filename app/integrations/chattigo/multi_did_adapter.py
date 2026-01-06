# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Adapter Chattigo para soporte multi-DID con WhatsApp Cloud API.
# ============================================================================
"""
Chattigo Multi-DID Adapter.

Single Responsibility: Orchestrate message sending using composed services.

URL Format: {base_url}/v15.0/{did}/messages
Body Format: WhatsApp Cloud API standard
"""

import logging

import httpx

from app.core.tenancy import ChattigoCredentials

from .http_client import ChattigoHttpClient
from .payload_builder import ChattigoPayloadBuilder
from .token_cache import ChattigoTokenCache

logger = logging.getLogger(__name__)


class ChattigoMultiDIDAdapter:
    """
    Chattigo adapter for multi-DID support with WhatsApp Cloud API format.

    Single Responsibility: Orchestrate message sending.

    Delegates to:
    - ChattigoHttpClient: HTTP communication with retry
    - ChattigoPayloadBuilder: WhatsApp Cloud API payload construction
    - ChattigoTokenCache: Token management (via http_client)
    """

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
        self._payload_builder = ChattigoPayloadBuilder()
        self._http_client: ChattigoHttpClient | None = None

    @property
    def did(self) -> str:
        """Get the DID this adapter is configured for."""
        return self._credentials.did

    @property
    def credentials(self) -> ChattigoCredentials:
        """Get the credentials (for inspection, not modification)."""
        return self._credentials

    def _build_message_url(self) -> str:
        """
        Build the message URL with DID as path parameter.

        URL Format: {base_url}/v15.0/{did}/messages

        Returns:
            Full URL for sending messages
        """
        base = self._credentials.base_url.rstrip("/")
        return f"{base}/v15.0/{self._credentials.did}/messages"

    def _get_http_client(self) -> ChattigoHttpClient:
        """Get or create HTTP client with token management."""
        if self._http_client is None:
            self._http_client = ChattigoHttpClient(
                token_provider=lambda: self._token_cache.get_token(
                    self._credentials.did, self._credentials
                ),
                token_invalidator=lambda: self._token_cache.invalidate(
                    self._credentials.did
                ),
            )
        return self._http_client

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        client = self._get_http_client()
        await client.initialize()

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.close()
            self._http_client = None

    async def __aenter__(self) -> "ChattigoMultiDIDAdapter":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def send_message(
        self,
        msisdn: str,
        message: str,
        sender_name: str | None = None,
    ) -> dict:
        """
        Send text message via WhatsApp Cloud API.

        Args:
            msisdn: Recipient phone number
            message: Message content
            sender_name: Deprecated - not used in Cloud API (kept for compatibility)

        Returns:
            API response dict

        Raises:
            ChattigoTokenError: If authentication fails
            httpx.HTTPError: If request fails
        """
        payload = self._payload_builder.build_text_payload(
            to=msisdn,
            message=message,
        )

        try:
            client = self._get_http_client()
            result = await client.post_with_retry(
                url=self._build_message_url(),
                payload=payload,
            )
            logger.info(f"Message sent via DID {self._credentials.did} to {msisdn}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(
                f"Failed to send message via DID {self._credentials.did}: {e}"
            )
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
        Send document via WhatsApp Cloud API.

        Args:
            msisdn: Recipient phone number
            document_url: Public URL of the document
            filename: Document filename
            mime_type: Deprecated - not used in Cloud API (kept for compatibility)
            caption: Optional caption

        Returns:
            API response dict
        """
        payload = self._payload_builder.build_document_payload(
            to=msisdn,
            document_url=document_url,
            filename=filename,
            caption=caption,
        )

        try:
            client = self._get_http_client()
            result = await client.post_with_retry(
                url=self._build_message_url(),
                payload=payload,
            )
            logger.info(f"Document sent via DID {self._credentials.did} to {msisdn}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(
                f"Failed to send document via DID {self._credentials.did}: {e}"
            )
            raise

    async def send_image(
        self,
        msisdn: str,
        image_url: str,
        caption: str | None = None,
        mime_type: str = "image/jpeg",
    ) -> dict:
        """
        Send image via WhatsApp Cloud API.

        Args:
            msisdn: Recipient phone number
            image_url: Public URL of the image
            caption: Optional caption
            mime_type: Deprecated - not used in Cloud API (kept for compatibility)

        Returns:
            API response dict
        """
        payload = self._payload_builder.build_image_payload(
            to=msisdn,
            image_url=image_url,
            caption=caption,
        )

        try:
            client = self._get_http_client()
            result = await client.post_with_retry(
                url=self._build_message_url(),
                payload=payload,
            )
            logger.info(f"Image sent via DID {self._credentials.did} to {msisdn}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(
                f"Failed to send image via DID {self._credentials.did}: {e}"
            )
            raise

    async def health_check(self) -> dict:
        """
        Check connectivity and authentication.

        Returns:
            Health status dict
        """
        try:
            token = await self._token_cache.get_token(
                self._credentials.did, self._credentials
            )
            return {
                "status": "healthy",
                "authenticated": True,
                "did": self._credentials.did,
                "name": self._credentials.name,
                "token_preview": f"{token[:20]}..." if len(token) > 20 else "***",
            }
        except Exception as e:
            logger.error(
                f"Health check failed for DID {self._credentials.did}: {e}"
            )
            return {
                "status": "unhealthy",
                "authenticated": False,
                "did": self._credentials.did,
                "name": self._credentials.name,
                "error": str(e),
            }
