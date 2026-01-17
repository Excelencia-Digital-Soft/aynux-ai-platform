# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Constants and enums for WhatsApp response formatting.
#              Replaces hardcoded magic numbers in response_formatter.py.
# Tenant-Aware: No - these are universal formatting constraints.
# ============================================================================
"""
Formatting constants for WhatsApp response generation.

This module centralizes all magic numbers and configuration constants
previously hardcoded in response_formatter.py.
"""

from enum import IntEnum, StrEnum


class FormattingLimits(IntEnum):
    """WhatsApp message limits and display constraints."""

    MAX_INVOICES_DISPLAYED = 5
    """Maximum number of invoices to show in debt details."""

    MAX_LIST_ITEMS = 10
    """Maximum items in WhatsApp interactive list."""

    MAX_TITLE_CHARS = 24
    """Maximum characters for list item titles."""

    MAX_BUTTONS = 3
    """Maximum buttons in WhatsApp interactive message."""


class ResponseType(StrEnum):
    """WhatsApp response types for interactive messages."""

    TEXT = "text"
    """Plain text message."""

    BUTTONS = "buttons"
    """Interactive message with reply buttons (max 3)."""

    LIST = "list"
    """Interactive list message (max 10 items)."""


class AwaitingInputType(StrEnum):
    """Valid awaiting_input values for response formatting."""

    DNI = "dni"
    NAME = "name"
    AMOUNT = "amount"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    ACCOUNT_SELECTION = "account_selection"
    MENU_SELECTION = "menu_selection"
    DEBT_ACTION = "debt_action"


# Default values for template variables
DEFAULT_PHARMACY_NAME = "Farmacia"
"""Default pharmacy name when not provided in state."""

DEFAULT_CUSTOMER_NAME = "tu cuenta"
"""Default customer name when not provided in state."""
