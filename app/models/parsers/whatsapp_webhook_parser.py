"""
WhatsApp Webhook Parser.

Utility functions for parsing WhatsApp webhook payloads.
Single Responsibility: Extract and validate data from WhatsApp webhook requests.
"""

from __future__ import annotations

from app.models.message import WhatsAppWebhookRequest


def is_status_update(request: WhatsAppWebhookRequest) -> bool:
    """
    Check if request is a status update (not a message).

    WhatsApp sends status updates for message delivery, read receipts, etc.
    These should be acknowledged but not processed as messages.

    Args:
        request: WhatsApp webhook request

    Returns:
        True if status update, False if message
    """
    try:
        return bool(request.entry[0].changes[0].value.get("statuses"))
    except (IndexError, AttributeError, KeyError):
        return False


def extract_phone_number_id(request: WhatsAppWebhookRequest) -> str | None:
    """
    Extract WhatsApp Business phone number ID from metadata.

    This ID identifies which WhatsApp Business phone number received
    the message. Used for bypass routing rules.

    Args:
        request: WhatsApp webhook request

    Returns:
        Phone number ID string or None if not found
    """
    try:
        return (
            request.entry[0]
            .changes[0]
            .value.get("metadata", {})
            .get("phone_number_id")
        )
    except (IndexError, AttributeError, KeyError):
        return None


def extract_display_phone_number(request: WhatsAppWebhookRequest) -> str | None:
    """
    Extract WhatsApp Business display phone number from metadata.

    This is the actual phone number (e.g., "5492644710400") that corresponds
    to the DID used in Chattigo for credential lookup.

    Args:
        request: WhatsApp webhook request

    Returns:
        Display phone number string or None if not found
    """
    try:
        return (
            request.entry[0]
            .changes[0]
            .value.get("metadata", {})
            .get("display_phone_number")
        )
    except (IndexError, AttributeError, KeyError):
        return None
