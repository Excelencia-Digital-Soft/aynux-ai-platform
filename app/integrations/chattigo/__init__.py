# ============================================================================
# SCOPE: GLOBAL
# Description: Chattigo integration module exports.
# ============================================================================
"""
Chattigo Integration Module.

Provides integration with Chattigo WhatsApp Business API intermediary.
Chattigo handles Meta verification and forwards messages to the application.

Usage:
    from app.integrations.chattigo import ChattigoAdapter, ChattigoWebhookPayload

    # Receiving webhooks
    @router.post("/webhook")
    async def webhook(payload: ChattigoWebhookPayload):
        ...

    # Sending messages
    async with ChattigoAdapter(settings) as adapter:
        await adapter.send_message(msisdn, did, id_chat, "Hello!")
"""

from .adapter import (
    ChattigoAdapter,
    ChattigoAuthError,
    ChattigoError,
    ChattigoSendError,
)
from .models import (
    ChattigoAttachmentMessage,
    ChattigoLoginRequest,
    ChattigoLoginResponse,
    ChattigoOutboundMessage,
    ChattigoWebhookPayload,
)

__all__ = [
    # Adapter
    "ChattigoAdapter",
    "ChattigoError",
    "ChattigoAuthError",
    "ChattigoSendError",
    # Models
    "ChattigoWebhookPayload",
    "ChattigoOutboundMessage",
    "ChattigoAttachmentMessage",
    "ChattigoLoginRequest",
    "ChattigoLoginResponse",
]
