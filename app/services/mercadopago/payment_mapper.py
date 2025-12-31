"""
Payment data extraction utilities for MercadoPago webhooks.

Extracts and normalizes payer information from MP payment responses,
handling multiple possible data locations and formats.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from app.core.tenancy import PharmacyConfig

logger = logging.getLogger(__name__)


class MercadoPagoPaymentMapper:
    """Extracts and normalizes data from MP payment responses."""

    @staticmethod
    def extract_payer_phone(payment: dict[str, Any]) -> str | None:
        """
        Extract payer phone number from payment data.

        Tries multiple locations where phone might be stored:
        1. payer.phone.number (primary)
        2. additional_info.payer.phone.number (fallback)

        Args:
            payment: MP payment response dictionary

        Returns:
            Phone number string or None if not found
        """
        # Try payer.phone.number
        payer = payment.get("payer", {})
        phone_data = payer.get("phone", {})
        if phone_data and phone_data.get("number"):
            return str(phone_data["number"])

        # Try additional_info if available
        additional_info = payment.get("additional_info", {})
        payer_info = additional_info.get("payer", {})
        phone_info = payer_info.get("phone", {})
        if phone_info and phone_info.get("number"):
            return str(phone_info["number"])

        return None

    @staticmethod
    def extract_payer_name(payment: dict[str, Any]) -> str | None:
        """
        Extract payer name from payment data.

        Tries multiple locations where name might be stored:
        1. payer.first_name + payer.last_name (primary)
        2. additional_info.payer.first_name + last_name (fallback)

        Args:
            payment: MP payment response dictionary

        Returns:
            Full name string or None if not found
        """
        # Try payer.first_name + payer.last_name
        payer = payment.get("payer", {})
        first_name = payer.get("first_name", "")
        last_name = payer.get("last_name", "")
        if first_name or last_name:
            return f"{first_name} {last_name}".strip()

        # Try additional_info if available
        additional_info = payment.get("additional_info", {})
        payer_info = additional_info.get("payer", {})
        first_name = payer_info.get("first_name", "")
        last_name = payer_info.get("last_name", "")
        if first_name or last_name:
            return f"{first_name} {last_name}".strip()

        return None

    @staticmethod
    def get_public_url_base(pharmacy_config: PharmacyConfig) -> str:
        """
        Get the base URL for public file access from pharmacy config.

        Priority:
        1. pharmacy_config.receipt_public_url_base (from DB)
        2. pharmacy_config.mp_notification_url (extract base from webhook URL)
        3. localhost (testing only - won't work for WhatsApp)

        Args:
            pharmacy_config: Pharmacy configuration from database

        Returns:
            Base URL string for public file access
        """
        if pharmacy_config.receipt_public_url_base:
            return pharmacy_config.receipt_public_url_base.rstrip("/")

        if pharmacy_config.mp_notification_url:
            parsed = urlparse(pharmacy_config.mp_notification_url)
            return f"{parsed.scheme}://{parsed.netloc}"

        # Fallback to localhost (won't work for WhatsApp but useful for testing)
        logger.warning(
            f"No public URL base configured for org {pharmacy_config.organization_id} "
            "- receipts may not be accessible via WhatsApp"
        )
        return "http://localhost:8000"
