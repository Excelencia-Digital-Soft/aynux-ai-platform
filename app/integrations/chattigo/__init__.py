# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Chattigo integration module exports.
# ============================================================================
"""
Chattigo Integration Module.

Provides integration with Chattigo WhatsApp Business API intermediary.
Chattigo handles Meta verification and forwards messages to the application.

Usage (Multi-DID - Recommended):
    from app.integrations.chattigo import get_chattigo_adapter_factory

    factory = get_chattigo_adapter_factory()
    adapter = await factory.get_adapter(db, did="5492644710400")
    await adapter.send_message(msisdn, message)

Usage (Legacy - Single DID):
    from app.integrations.chattigo import ChattigoAdapter

    async with ChattigoAdapter(settings) as adapter:
        await adapter.send_message(msisdn, did, id_chat, "Hello!")
"""

# Legacy adapter (single-DID, settings-based)
from .adapter import (
    ChattigoAdapter,
    ChattigoAuthError,
    ChattigoError,
    ChattigoSendError,
)

# Retry-related exceptions (ISV Chattigo Section 8.1)
from .exceptions import ChattigoRateLimitError, ChattigoRetryableError

# Multi-DID adapter system (refactored for SRP)
from .adapter_factory import (
    ChattigoAdapterFactory,
    ChattigoMultiDIDAdapter,
    ChattigoTokenCache,
    ChattigoTokenError,
    get_chattigo_adapter_factory,
)
from .http_client import ChattigoHttpClient
from .models import (
    ChattigoAttachmentMessage,
    ChattigoLoginRequest,
    ChattigoLoginResponse,
    ChattigoOutboundMessage,
    ChattigoWebhookPayload,
)
from .payload_builder import ChattigoPayloadBuilder

__all__ = [
    # Legacy Adapter
    "ChattigoAdapter",
    "ChattigoError",
    "ChattigoAuthError",
    "ChattigoSendError",
    # Retry Exceptions (ISV Chattigo Section 8.1)
    "ChattigoRetryableError",
    "ChattigoRateLimitError",
    # Multi-DID Adapter System
    "ChattigoAdapterFactory",
    "ChattigoMultiDIDAdapter",
    "ChattigoTokenCache",
    "ChattigoTokenError",
    "ChattigoHttpClient",
    "ChattigoPayloadBuilder",
    "get_chattigo_adapter_factory",
    # Models
    "ChattigoWebhookPayload",
    "ChattigoOutboundMessage",
    "ChattigoAttachmentMessage",
    "ChattigoLoginRequest",
    "ChattigoLoginResponse",
]
