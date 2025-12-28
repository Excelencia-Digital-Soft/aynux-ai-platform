"""
Tests for WhatsApp Webhook Parser.

Tests the utility functions for parsing WhatsApp webhook payloads.
"""

import pytest

from app.models.message import WhatsAppWebhookRequest
from app.models.parsers.whatsapp_webhook_parser import (
    extract_phone_number_id,
    is_status_update,
)


class TestIsStatusUpdate:
    """Tests for is_status_update function."""

    def test_message_is_not_status_update(self):
        """Test that a regular message is not detected as status update."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "123456789"},
                                "contacts": [{"wa_id": "5491234567890", "profile": {"name": "Test"}}],
                                "messages": [
                                    {
                                        "from": "5491234567890",
                                        "id": "wamid.test",
                                        "timestamp": "1234567890",
                                        "text": {"body": "Hello"},
                                        "type": "text",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        request = WhatsAppWebhookRequest.model_validate(payload)
        assert is_status_update(request) is False

    def test_status_update_is_detected(self):
        """Test that a status update is correctly detected."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "123456789"},
                                "statuses": [
                                    {
                                        "id": "wamid.test",
                                        "status": "delivered",
                                        "timestamp": "1234567890",
                                        "recipient_id": "5491234567890",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        request = WhatsAppWebhookRequest.model_validate(payload)
        assert is_status_update(request) is True

    def test_empty_statuses_is_not_status_update(self):
        """Test that empty statuses list is not detected as status update."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "statuses": [],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        request = WhatsAppWebhookRequest.model_validate(payload)
        assert is_status_update(request) is False

    def test_empty_entry_returns_false(self):
        """Test that empty entry list returns False."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [],
        }
        request = WhatsAppWebhookRequest.model_validate(payload)
        assert is_status_update(request) is False


class TestExtractPhoneNumberId:
    """Tests for extract_phone_number_id function."""

    def test_extracts_phone_number_id(self):
        """Test successful extraction of phone_number_id from metadata."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "987654321",
                                },
                                "messages": [
                                    {
                                        "from": "5491234567890",
                                        "id": "wamid.test",
                                        "timestamp": "1234567890",
                                        "text": {"body": "Hello"},
                                        "type": "text",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        request = WhatsAppWebhookRequest.model_validate(payload)
        assert extract_phone_number_id(request) == "987654321"

    def test_returns_none_when_no_metadata(self):
        """Test that None is returned when metadata is missing."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        request = WhatsAppWebhookRequest.model_validate(payload)
        assert extract_phone_number_id(request) is None

    def test_returns_none_when_empty_entry(self):
        """Test that None is returned when entry is empty."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [],
        }
        request = WhatsAppWebhookRequest.model_validate(payload)
        assert extract_phone_number_id(request) is None

    def test_returns_none_when_no_phone_number_id_in_metadata(self):
        """Test that None is returned when phone_number_id is not in metadata."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"display_phone_number": "15551234567"},
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        request = WhatsAppWebhookRequest.model_validate(payload)
        assert extract_phone_number_id(request) is None
