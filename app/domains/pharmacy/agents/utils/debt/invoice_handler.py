# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Invoice selection and aggregation utilities.
#              Extracted from debt_manager_node._handle_invoice_detail().
# Tenant-Aware: No - operates on debt items regardless of tenant.
# ============================================================================
"""
Invoice selection and aggregation utilities.

This module provides utilities for selecting invoices from state/message
and aggregating invoice amounts from debt items.

Single Responsibility: Invoice selection and amount aggregation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)

# Pattern to extract invoice number from user message
INVOICE_PATTERN = re.compile(r"(?:factura|comprobante)\s*(?:n[°o]?)?\s*(\w+)", re.IGNORECASE)


@dataclass
class InvoiceData:
    """
    Container for invoice data.

    Groups invoice number, date, and aggregated total.
    """

    invoice_number: str
    """Invoice number (e.g., "FC-001234")."""

    invoice_date: str
    """Invoice date as string."""

    invoice_total: float
    """Total amount for this invoice."""


class InvoiceHandler:
    """
    Handles invoice selection and amount aggregation.

    Single Responsibility: Select invoice and aggregate amounts.

    This class extracts the invoice handling logic from
    _handle_invoice_detail() to reduce function complexity.
    """

    @staticmethod
    def select_invoice(
        state: "PharmacyStateV2",
        debt_items: list[Any],
        message: str | None = None,
    ) -> str | None:
        """
        Select invoice number from state, message, or first available.

        Priority order:
        1. selected_invoice_number from state
        2. Invoice number extracted from message
        3. First invoice from debt_items

        Args:
            state: Current conversation state
            debt_items: List of debt items
            message: User message to search for invoice number

        Returns:
            Invoice number if found, None otherwise
        """
        # Priority 1: From state
        selected = state.get("selected_invoice_number")
        if selected:
            logger.debug(f"Invoice selected from state: {selected}")
            return selected

        # Priority 2: From message
        if message:
            extracted = InvoiceHandler._extract_from_message(message)
            if extracted:
                logger.debug(f"Invoice extracted from message: {extracted}")
                return extracted

        # Priority 3: First from debt items
        if debt_items:
            first = InvoiceHandler._get_first_invoice(debt_items)
            if first:
                logger.debug(f"Using first invoice: {first}")
                return first

        logger.debug("No invoice could be selected")
        return None

    @staticmethod
    def _extract_from_message(message: str) -> str | None:
        """Extract invoice number from message using regex."""
        match = INVOICE_PATTERN.search(message)
        if match:
            return match.group(1).upper()
        return None

    @staticmethod
    def _get_first_invoice(debt_items: list[Any]) -> str | None:
        """Get invoice number from first debt item."""
        if not debt_items:
            return None

        first_item = debt_items[0]
        if isinstance(first_item, dict):
            return first_item.get("invoice_number")
        return getattr(first_item, "invoice_number", None)

    @staticmethod
    def aggregate_invoice_amounts(
        debt_items: list[Any],
        invoice_number: str,
    ) -> InvoiceData:
        """
        Aggregate amounts for a specific invoice.

        Iterates through debt items and sums amounts for matching invoice.

        Args:
            debt_items: List of debt items (dicts or objects)
            invoice_number: Invoice number to aggregate

        Returns:
            InvoiceData with aggregated total and date
        """
        total = 0.0
        date = ""

        for item in debt_items:
            item_invoice = InvoiceHandler._get_invoice_number(item)

            if item_invoice == invoice_number:
                amount = InvoiceHandler._get_amount(item)
                total += amount

                if not date:
                    date = InvoiceHandler._get_date(item)

        return InvoiceData(
            invoice_number=invoice_number,
            invoice_date=date,
            invoice_total=total,
        )

    @staticmethod
    def _get_invoice_number(item: dict[str, Any] | Any) -> str | None:
        """Extract invoice number from item (dict or object)."""
        if isinstance(item, dict):
            return item.get("invoice_number")
        return getattr(item, "invoice_number", None)

    @staticmethod
    def _get_amount(item: dict[str, Any] | Any) -> float:
        """Extract amount from item (dict or object)."""
        if isinstance(item, dict):
            raw = item.get("amount", 0)
        else:
            raw = getattr(item, "amount", 0)
        return float(raw or 0)

    @staticmethod
    def _get_date(item: dict[str, Any] | Any) -> str:
        """Extract date from item (dict or object)."""
        if isinstance(item, dict):
            raw = item.get("invoice_date", "")
        else:
            raw = getattr(item, "invoice_date", "")
        return str(raw) if raw else ""
