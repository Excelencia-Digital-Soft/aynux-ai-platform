# ============================================================================
# SCOPE: GLOBAL
# Description: Adaptador para comunicación con Chattigo API.
#              Maneja autenticación y envío de mensajes.
# Tenant-Aware: No - Chattigo maneja autenticación por ISV.
# ============================================================================
"""
Chattigo API Adapter.

Handles authentication and message sending via Chattigo's API.
Based on DECSA implementation with Aynux Clean Architecture patterns.

Usage:
    adapter = ChattigoAdapter(settings)
    await adapter.initialize()
    await adapter.send_message(msisdn, did, id_chat, message)
    await adapter.close()
"""

import logging
import time
from typing import Any

import httpx

from app.config.settings import Settings

from .models import ChattigoLoginRequest, ChattigoLoginResponse

logger = logging.getLogger(__name__)


class ChattigoError(Exception):
    """Base exception for Chattigo errors."""

    pass


class ChattigoAuthError(ChattigoError):
    """Authentication error with Chattigo API."""

    pass


class ChattigoSendError(ChattigoError):
    """Error sending message via Chattigo."""

    pass


class ChattigoAdapter:
    """
    Adapter for Chattigo WhatsApp API.

    Responsibilities:
    - Authentication with Chattigo API
    - Token management and refresh
    - Message sending (text, documents, images)

    Usage:
        async with ChattigoAdapter(settings) as adapter:
            await adapter.send_message(msisdn, did, id_chat, "Hello!")
    """

    DEFAULT_TIMEOUT = 30.0
    TOKEN_REFRESH_BUFFER = 60  # Refresh token 60 seconds before expiry

    def __init__(self, settings: Settings):
        """
        Initialize Chattigo adapter.

        Args:
            settings: Application settings containing Chattigo configuration
        """
        self._settings = settings
        self._base_url = settings.CHATTIGO_BASE_URL
        self._username = settings.CHATTIGO_USERNAME
        self._password = settings.CHATTIGO_PASSWORD
        self._channel_id = settings.CHATTIGO_CHANNEL_ID
        self._campaign_id = settings.CHATTIGO_CAMPAIGN_ID
        self._bot_name = settings.CHATTIGO_BOT_NAME

        self._token: str | None = None
        self._token_expiry: float = 0
        self._client: httpx.AsyncClient | None = None

        logger.info(f"Initializing ChattigoAdapter for user: {self._username}")

    async def initialize(self) -> None:
        """Initialize HTTP client and authenticate."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT)
        await self._ensure_token()

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("ChattigoAdapter closed")

    async def __aenter__(self) -> "ChattigoAdapter":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # =========================================================================
    # Authentication
    # =========================================================================

    async def _ensure_token(self) -> None:
        """Ensure we have a valid token, refreshing if necessary."""
        if self._token and time.time() < (self._token_expiry - self.TOKEN_REFRESH_BUFFER):
            return

        await self._refresh_token()

    async def _refresh_token(self) -> None:
        """Obtain new authentication token from Chattigo."""
        logger.debug(f"Obtaining token for {self._username}")

        if not self._client:
            raise ChattigoError("Client not initialized. Call initialize() first.")

        try:
            payload = ChattigoLoginRequest(
                username=self._username,
                password=self._password,
            )

            response = await self._client.post(
                f"{self._base_url}/login",
                json=payload.model_dump(),
            )
            response.raise_for_status()

            data = ChattigoLoginResponse(**response.json())
            self._token = data.access_token
            # Default to 1 hour if expires_in not provided
            self._token_expiry = time.time() + (data.expires_in or 3600)

            logger.info("Chattigo token obtained successfully")

        except httpx.HTTPError as e:
            logger.error(f"Chattigo authentication failed: {e}")
            raise ChattigoAuthError(f"Authentication failed: {e}") from e

    def _get_headers(self) -> dict[str, str]:
        """Get headers with authorization token."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # =========================================================================
    # Message Sending
    # =========================================================================

    async def send_message(
        self,
        msisdn: str,
        did: str,
        id_chat: int,
        message: str,
    ) -> dict[str, Any]:
        """
        Send text message via Chattigo.

        Args:
            msisdn: Recipient phone number
            did: Bot's phone number (destination ID)
            id_chat: Chat/conversation ID
            message: Message content

        Returns:
            API response dict

        Raises:
            ChattigoSendError: If message sending fails
        """
        await self._ensure_token()

        if not self._client:
            raise ChattigoError("Client not initialized")

        unique_message_id = str(int(time.time() * 1000))

        payload = {
            "id": unique_message_id,
            "idChat": id_chat,
            "chatType": "OUTBOUND",
            "did": did,
            "msisdn": msisdn,
            "type": "Text",
            "channel": "WHATSAPP",
            "channelId": self._channel_id,
            "channelProvider": "APICLOUDBSP",
            "content": message,
            "name": self._bot_name,
            "idCampaign": self._campaign_id,
            "isAttachment": False,
            "stateAgent": "BOT",
        }

        try:
            logger.debug(f"Sending message to {msisdn}: {message[:50]}...")

            response = await self._client.post(
                f"{self._base_url}/webhooks/inbound",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Message sent to {msisdn}: {result}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(f"Failed to send message: {e}")
            raise ChattigoSendError(f"Failed to send message: {e}") from e

    async def send_document(
        self,
        msisdn: str,
        did: str,
        id_chat: int,
        document_url: str,
        filename: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """
        Send document via Chattigo.

        Args:
            msisdn: Recipient phone number
            did: Bot's phone number
            id_chat: Chat/conversation ID
            document_url: Public URL of the document
            filename: Document filename
            caption: Optional caption

        Returns:
            API response dict
        """
        await self._ensure_token()

        if not self._client:
            raise ChattigoError("Client not initialized")

        unique_message_id = str(int(time.time() * 1000))

        payload = {
            "id": unique_message_id,
            "idChat": id_chat,
            "chatType": "OUTBOUND",
            "did": did,
            "msisdn": msisdn,
            "type": "Document",
            "channel": "WHATSAPP",
            "channelId": self._channel_id,
            "channelProvider": "APICLOUDBSP",
            "content": caption or "",
            "name": self._bot_name,
            "idCampaign": self._campaign_id,
            "isAttachment": True,
            "stateAgent": "BOT",
            "attachment": {
                "url": document_url,
                "filename": filename,
            },
        }

        try:
            logger.debug(f"Sending document to {msisdn}: {filename}")

            response = await self._client.post(
                f"{self._base_url}/webhooks/inbound",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Document sent to {msisdn}: {result}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(f"Failed to send document: {e}")
            raise ChattigoSendError(f"Failed to send document: {e}") from e

    async def send_image(
        self,
        msisdn: str,
        did: str,
        id_chat: int,
        image_url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """
        Send image via Chattigo.

        Args:
            msisdn: Recipient phone number
            did: Bot's phone number
            id_chat: Chat/conversation ID
            image_url: Public URL of the image
            caption: Optional caption

        Returns:
            API response dict
        """
        await self._ensure_token()

        if not self._client:
            raise ChattigoError("Client not initialized")

        unique_message_id = str(int(time.time() * 1000))

        payload = {
            "id": unique_message_id,
            "idChat": id_chat,
            "chatType": "OUTBOUND",
            "did": did,
            "msisdn": msisdn,
            "type": "Image",
            "channel": "WHATSAPP",
            "channelId": self._channel_id,
            "channelProvider": "APICLOUDBSP",
            "content": caption or "",
            "name": self._bot_name,
            "idCampaign": self._campaign_id,
            "isAttachment": True,
            "stateAgent": "BOT",
            "attachment": {
                "url": image_url,
            },
        }

        try:
            logger.debug(f"Sending image to {msisdn}")

            response = await self._client.post(
                f"{self._base_url}/webhooks/inbound",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Image sent to {msisdn}: {result}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(f"Failed to send image: {e}")
            raise ChattigoSendError(f"Failed to send image: {e}") from e

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Check Chattigo API connectivity and authentication.

        Returns:
            Health status dict with token validity

        Raises:
            ChattigoError: If health check fails
        """
        try:
            await self._ensure_token()
            return {
                "status": "healthy",
                "authenticated": True,
                "channel_id": self._channel_id,
                "username": self._username,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "authenticated": False,
                "error": str(e),
            }
