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

import json
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
        self._login_url = settings.CHATTIGO_LOGIN_URL
        self._message_url = settings.CHATTIGO_MESSAGE_URL
        self._username = settings.CHATTIGO_USERNAME
        self._password = settings.CHATTIGO_PASSWORD
        self._did = settings.CHATTIGO_DID
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

    def _safe_parse_json(self, response: httpx.Response) -> dict[str, Any]:
        """
        Safely parse JSON response, returning empty dict for empty body.

        Chattigo API may return HTTP 200 with empty body on success.

        Args:
            response: httpx Response object

        Returns:
            Parsed JSON dict or empty dict for empty responses
        """
        # Handle HTTP 204 No Content or empty response
        if response.status_code == 204 or not response.text.strip():
            return {}

        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse JSON response: {e}, body: {response.text[:100]}")
            return {}

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
                self._login_url,
                json=payload.model_dump(),
            )
            response.raise_for_status()

            # Parse JSON response safely
            json_data = self._safe_parse_json(response)
            if not json_data:
                raise ChattigoAuthError("Login returned empty response")

            data = ChattigoLoginResponse(**json_data)
            self._token = data.access_token
            # Default to 1 hour if expires_in not provided
            self._token_expiry = time.time() + (data.expires_in or 3600)

            logger.info("Chattigo token obtained successfully")

        except httpx.HTTPError as e:
            logger.error(f"Chattigo authentication failed: {e}")
            raise ChattigoAuthError(f"Authentication failed: {e}") from e
        except ValueError as e:
            logger.error(f"Chattigo login response parsing failed: {e}")
            raise ChattigoAuthError(f"Login response parsing failed: {e}") from e

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
        message: str,
        sender_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Send text message via Chattigo API.

        Args:
            msisdn: Recipient phone number
            message: Message content
            sender_name: Optional sender name (defaults to bot name)

        Returns:
            API response dict with status

        Raises:
            ChattigoSendError: If message sending fails
        """
        await self._ensure_token()

        if not self._client:
            raise ChattigoError("Client not initialized")

        # Chattigo ISV proprietary format
        # IMPORTANT: For ISV, use lowercase "text" (not "Text" like BSP)
        # Do NOT include channelProvider or stateAgent (causes 502/503)
        payload = {
            "id": str(int(time.time() * 1000)),
            "did": self._did,
            "msisdn": msisdn,
            "type": "text",  # Must be lowercase for ISV
            "channel": "WHATSAPP",
            "chatType": "OUTBOUND",  # Indicates outbound message direction
            "content": message,
            "name": sender_name or self._bot_name,
            "isAttachment": False,
        }

        try:
            logger.debug(f"Sending message to {msisdn}: {message[:50]}...")

            response = await self._client.post(
                self._message_url,
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()

            result = self._safe_parse_json(response)
            logger.info(f"Message sent to {msisdn}: status={response.status_code}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(f"Failed to send message: {e}")
            raise ChattigoSendError(f"Failed to send message: {e}") from e

    async def send_document(
        self,
        msisdn: str,
        document_url: str,
        filename: str,
        mime_type: str = "application/pdf",
        caption: str | None = None,
    ) -> dict[str, Any]:
        """
        Send document via Chattigo API.

        Args:
            msisdn: Recipient phone number
            document_url: Public URL of the document
            filename: Document filename
            mime_type: MIME type of the document
            caption: Optional caption

        Returns:
            API response dict with status
        """
        await self._ensure_token()

        if not self._client:
            raise ChattigoError("Client not initialized")

        # Chattigo ISV proprietary format for media
        payload = {
            "id": str(int(time.time() * 1000)),
            "did": self._did,
            "msisdn": msisdn,
            "type": "media",
            "channel": "WHATSAPP",
            "chatType": "OUTBOUND",
            "content": caption or "Documento adjunto.",
            "name": self._bot_name,
            "isAttachment": True,
            "attachment": {
                "mediaUrl": document_url,
                "mimeType": mime_type,
                "fileName": filename,
            },
        }

        try:
            logger.debug(f"Sending document to {msisdn}: {filename}")

            response = await self._client.post(
                self._message_url,
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()

            result = self._safe_parse_json(response)
            logger.info(f"Document sent to {msisdn}: status={response.status_code}")
            return {"status": "ok", "data": result}

        except httpx.HTTPError as e:
            logger.error(f"Failed to send document: {e}")
            raise ChattigoSendError(f"Failed to send document: {e}") from e

    async def send_image(
        self,
        msisdn: str,
        image_url: str,
        caption: str | None = None,
        mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """
        Send image via Chattigo API.

        Args:
            msisdn: Recipient phone number
            image_url: Public URL of the image
            caption: Optional caption
            mime_type: MIME type of the image

        Returns:
            API response dict with status
        """
        await self._ensure_token()

        if not self._client:
            raise ChattigoError("Client not initialized")

        # Chattigo ISV proprietary format for media
        payload = {
            "id": str(int(time.time() * 1000)),
            "did": self._did,
            "msisdn": msisdn,
            "type": "media",
            "channel": "WHATSAPP",
            "chatType": "OUTBOUND",
            "content": caption or "",
            "name": self._bot_name,
            "isAttachment": True,
            "attachment": {
                "mediaUrl": image_url,
                "mimeType": mime_type,
            },
        }

        try:
            logger.debug(f"Sending image to {msisdn}")

            response = await self._client.post(
                self._message_url,
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()

            result = self._safe_parse_json(response)
            logger.info(f"Image sent to {msisdn}: status={response.status_code}")
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
                "did": self._did,
                "username": self._username,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "authenticated": False,
                "error": str(e),
            }
