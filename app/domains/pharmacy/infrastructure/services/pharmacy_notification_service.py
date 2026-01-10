"""
Pharmacy Notification Service.

Sends intermediate and notification messages via WhatsApp using the Chattigo adapter.

Usage:
    from app.domains.pharmacy.infrastructure.services import PharmacyNotificationService

    async with get_async_db_context() as db:
        service = PharmacyNotificationService(db=db, did="5492646715777")
        result = await service.send_message(phone="+5492644123456", message="Hola")
        await service.close()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.integrations.chattigo import get_chattigo_adapter_factory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.integrations.chattigo.multi_did_adapter import ChattigoMultiDIDAdapter

logger = logging.getLogger(__name__)


class PharmacyNotificationService:
    """
    Service for sending pharmacy-related notifications via WhatsApp.

    Uses the global Chattigo adapter (multi-DID) for all communications.
    Credentials are stored in database (chattigo_credentials table).
    """

    def __init__(self, db: AsyncSession, did: str | None) -> None:
        """
        Initialize notification service.

        Args:
            db: Database session (for credential lookup)
            did: WhatsApp Business DID (phone number)
        """
        self._db = db
        self._did = did
        self._adapter: ChattigoMultiDIDAdapter | None = None

    async def _get_adapter(self) -> ChattigoMultiDIDAdapter:
        """Get or create Chattigo adapter for configured DID."""
        if self._adapter is None:
            if not self._did:
                msg = "DID is required to send messages"
                raise ValueError(msg)
            factory = get_chattigo_adapter_factory()
            self._adapter = await factory.get_adapter(self._db, did=self._did)
            await self._adapter.initialize()
        return self._adapter

    async def close(self) -> None:
        """Close adapter connection."""
        if self._adapter:
            await self._adapter.close()
            self._adapter = None

    async def __aenter__(self) -> PharmacyNotificationService:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def send_message(self, phone: str, message: str) -> dict[str, Any]:
        """
        Send a text message and wait for HTTP 200 confirmation.

        Args:
            phone: Recipient phone number.
            message: Message text.

        Returns:
            {"status": "ok", "data": {...}} on success
        """
        adapter = await self._get_adapter()
        result = await adapter.send_message(msisdn=phone, message=message)
        logger.info(f"Pharmacy message sent to {phone}: {message[:50]}...")
        return result

    async def send_interactive_buttons(
        self,
        phone: str,
        body: str,
        buttons: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Send interactive buttons message.

        Args:
            phone: Recipient phone number.
            body: Message body.
            buttons: List of buttons with id and title.

        Returns:
            API response dict.
        """
        adapter = await self._get_adapter()

        formatted_buttons = [
            {"id": str(btn.get("id", f"btn_{i}")), "title": str(btn.get("title", ""))[:20]}
            for i, btn in enumerate(buttons[:3])
        ]

        result = await adapter.send_interactive_buttons(
            msisdn=phone,
            body=body,
            buttons=formatted_buttons,
        )
        logger.info(f"Interactive buttons sent to {phone}")
        return result
