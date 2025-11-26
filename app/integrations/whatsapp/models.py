"""
WhatsApp Models (Deprecated)

This module is deprecated. Use app.models.whatsapp_advanced instead.
"""

# Re-export from whatsapp_advanced for backwards compatibility
from app.models.whatsapp_advanced import (
    CatalogConfiguration,
    FlowConfiguration,
    MessageFactory,
    WhatsAppApiResponse,
)

__all__ = [
    "CatalogConfiguration",
    "FlowConfiguration",
    "MessageFactory",
    "WhatsAppApiResponse",
]
