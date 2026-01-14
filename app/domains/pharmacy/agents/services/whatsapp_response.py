"""
WhatsApp Response Service - Sends formatted responses via WhatsApp.

This service reads the response formatting from state (set by ResponseFormatter)
and sends the appropriate message type via WhatsApp API.

Supports:
- Text messages
- Interactive Reply Buttons (max 3)
- Interactive Lists (up to 10 items)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2
    from app.integrations.whatsapp.messenger import WhatsAppMessenger

logger = logging.getLogger(__name__)


class WhatsAppResponseService:
    """
    Service for sending WhatsApp messages based on state formatting.

    Reads response_type, response_buttons, and response_list_items from
    state and sends the appropriate message type.

    Usage:
        service = WhatsAppResponseService(messenger)
        await service.send_response(state, phone_number)
    """

    def __init__(self, messenger: "WhatsAppMessenger") -> None:
        """
        Initialize service with WhatsApp messenger.

        Args:
            messenger: WhatsAppMessenger instance for sending messages
        """
        self._messenger = messenger

    async def send_response(
        self,
        state: "PharmacyStateV2",
        phone: str,
    ) -> dict[str, Any]:
        """
        Send formatted response based on state.

        Reads response_type from state and calls appropriate send method.

        Args:
            state: Current conversation state with formatting
            phone: Recipient phone number

        Returns:
            WhatsApp API response
        """
        response_type = state.get("response_type", "text")
        body = state.get("_formatted_body", "")
        title = state.get("_formatted_title", "")

        if not body:
            logger.warning("No formatted body in state, skipping send")
            return {"success": False, "error": "No message body"}

        try:
            if response_type == "buttons":
                return await self._send_buttons(state, phone, title, body)
            elif response_type == "list":
                return await self._send_list(state, phone, title, body)
            else:
                return await self._send_text(phone, body)

        except Exception as e:
            logger.error(f"Error sending WhatsApp response: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _send_text(
        self,
        phone: str,
        body: str,
    ) -> dict[str, Any]:
        """Send simple text message."""
        logger.info(f"Sending text message to {phone}")
        return await self._messenger.send_text(numero=phone, mensaje=body)

    async def _send_buttons(
        self,
        state: "PharmacyStateV2",
        phone: str,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        """
        Send interactive buttons message.

        WhatsApp allows max 3 buttons, each with:
        - id: unique identifier (returned on click)
        - title: button text (max 20 chars)

        Args:
            state: State containing response_buttons
            phone: Recipient phone number
            title: Message header
            body: Message body

        Returns:
            WhatsApp API response
        """
        buttons = state.get("response_buttons") or []

        if not buttons:
            logger.warning("No buttons in state, falling back to text")
            return await self._send_text(phone, body)

        # Ensure max 3 buttons
        if len(buttons) > 3:
            logger.warning(f"Too many buttons ({len(buttons)}), truncating to 3")
            buttons = buttons[:3]

        # Format buttons for WhatsApp API
        formatted_buttons = [
            {
                "id": btn.get("id", f"btn_{i}"),
                "titulo": str(btn.get("titulo", ""))[:20],  # Max 20 chars
            }
            for i, btn in enumerate(buttons)
        ]

        logger.info(f"Sending buttons message to {phone}: {len(formatted_buttons)} buttons")

        return await self._messenger.send_buttons(
            numero=phone,
            titulo=title or "Opciones",
            cuerpo=body,
            botones=formatted_buttons,
        )

    async def _send_list(
        self,
        state: "PharmacyStateV2",
        phone: str,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        """
        Send interactive list message.

        WhatsApp allows up to 10 list items, each with:
        - id: unique identifier (returned on selection)
        - title: item title (max 24 chars)
        - description: optional description (max 72 chars)

        Args:
            state: State containing response_list_items
            phone: Recipient phone number
            title: Message header
            body: Message body

        Returns:
            WhatsApp API response
        """
        items = state.get("response_list_items") or []

        if not items:
            logger.warning("No list items in state, falling back to text")
            return await self._send_text(phone, body)

        # Ensure max 10 items
        if len(items) > 10:
            logger.warning(f"Too many list items ({len(items)}), truncating to 10")
            items = items[:10]

        # Format items for WhatsApp API
        formatted_items = [
            {
                "id": item.get("id", f"item_{i}"),
                "titulo": str(item.get("titulo", ""))[:24],  # Max 24 chars
                "descripcion": str(item.get("descripcion", ""))[:72],  # Max 72 chars
            }
            for i, item in enumerate(items)
        ]

        logger.info(f"Sending list message to {phone}: {len(formatted_items)} items")

        return await self._messenger.send_list(
            numero=phone,
            titulo=title or "Selecciona una opcion",
            cuerpo=body,
            opciones=formatted_items,
        )


async def send_formatted_response(
    messenger: "WhatsAppMessenger",
    state: "PharmacyStateV2",
    phone: str,
) -> dict[str, Any]:
    """
    Convenience function to send formatted response.

    Args:
        messenger: WhatsAppMessenger instance
        state: Current conversation state with formatting
        phone: Recipient phone number

    Returns:
        WhatsApp API response
    """
    service = WhatsAppResponseService(messenger)
    return await service.send_response(state, phone)
