"""
WhatsApp Client (Deprecated)

This module is deprecated. Use service.py instead.
"""

# Re-export from service for backwards compatibility
from app.integrations.whatsapp.service import WhatsAppService

# Alias for backwards compatibility
WhatsAppClient = WhatsAppService

__all__ = [
    "WhatsAppService",
    "WhatsAppClient",
]
