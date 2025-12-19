"""
Debt Grouping Domain Service

Provides invoice-level aggregation logic for debt items.
Groups items by comprobante (invoice number) and calculates totals.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domains.pharmacy.domain.entities.pharmacy_debt import DebtItem


@dataclass
class InvoiceGroup:
    """
    Represents a group of debt items belonging to the same invoice/comprobante.

    Attributes:
        invoice_number: The comprobante/invoice number (e.g., "TF B0018-00018160")
        invoice_date: Date of the invoice (YYYY-MM-DD format)
        items: List of DebtItem objects belonging to this invoice
        total_amount: Sum of all item amounts in this invoice
    """

    invoice_number: str
    invoice_date: str | None
    items: list[DebtItem | dict[str, Any]]
    total_amount: Decimal

    @property
    def item_count(self) -> int:
        """Get number of items in this invoice group."""
        return len(self.items)

    @property
    def product_names(self) -> list[str]:
        """Get list of product descriptions in this invoice."""
        names = []
        for item in self.items:
            if isinstance(item, dict):
                names.append(item.get("description", "Item"))
            else:
                names.append(item.description)
        return names

    @property
    def products_summary(self) -> str:
        """Get comma-separated summary of products."""
        names = self.product_names
        if len(names) <= 3:
            return ", ".join(names)
        first_three = ", ".join(names[:3])
        remaining = len(names) - 3
        return f"{first_three} y {remaining} más"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        items_list = []
        for item in self.items:
            if isinstance(item, dict):
                items_list.append(item)
            else:
                items_list.append(item.to_dict())

        return {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "total_amount": float(self.total_amount),
            "item_count": self.item_count,
            "items": items_list,
            "products_summary": self.products_summary,
        }


class DebtGroupingService:
    """
    Domain service for grouping debt items by invoice.

    Handles the business logic of aggregating items by comprobante
    for debt analysis queries.
    """

    # Items without invoice go into this special group
    NO_INVOICE_KEY = "Sin comprobante"

    @classmethod
    def _get_item_value(cls, item: DebtItem | dict[str, Any], key: str, default: Any = None) -> Any:
        """Extract value from DebtItem or dict."""
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    @classmethod
    def _get_item_amount(cls, item: DebtItem | dict[str, Any]) -> Decimal:
        """Extract amount from DebtItem or dict as Decimal."""
        if isinstance(item, dict):
            return Decimal(str(item.get("amount", 0)))
        return item.amount

    @classmethod
    def _get_invoice_key(cls, item: DebtItem | dict[str, Any]) -> str:
        """Extract invoice number from item."""
        if isinstance(item, dict):
            key = item.get("invoice_number") or item.get("comprobante") or ""
        else:
            key = item.invoice_number or ""
        return key.strip() if key else cls.NO_INVOICE_KEY

    @classmethod
    def _get_invoice_date(cls, item: DebtItem | dict[str, Any]) -> str | None:
        """Extract invoice date from item."""
        if isinstance(item, dict):
            return item.get("invoice_date") or item.get("fecha")
        return item.invoice_date

    @classmethod
    def group_by_invoice(
        cls,
        items: list[DebtItem | dict[str, Any]],
    ) -> list[InvoiceGroup]:
        """
        Group debt items by their invoice number (comprobante).

        Args:
            items: List of DebtItem objects or dicts with item data

        Returns:
            List of InvoiceGroup sorted by total_amount descending
        """
        if not items:
            return []

        # Group items by invoice number
        grouped: dict[str, list[DebtItem | dict[str, Any]]] = defaultdict(list)
        dates: dict[str, str | None] = {}

        for item in items:
            key = cls._get_invoice_key(item)
            grouped[key].append(item)

            # Capture date from first item of each group
            if key not in dates:
                dates[key] = cls._get_invoice_date(item)

        # Create InvoiceGroup for each group
        invoice_groups: list[InvoiceGroup] = []
        for invoice_number, group_items in grouped.items():
            if not group_items:
                continue

            total = sum(cls._get_item_amount(item) for item in group_items)

            group = InvoiceGroup(
                invoice_number=invoice_number,
                invoice_date=dates.get(invoice_number),
                items=group_items,
                total_amount=total,
            )
            invoice_groups.append(group)

        # Sort by total amount descending
        invoice_groups.sort(key=lambda g: g.total_amount, reverse=True)

        return invoice_groups

    @classmethod
    def get_highest_debt_invoice(
        cls,
        items: list[DebtItem | dict[str, Any]],
    ) -> InvoiceGroup | None:
        """
        Get the invoice with the highest total debt.

        Args:
            items: List of debt items

        Returns:
            InvoiceGroup with highest total, or None if no items
        """
        groups = cls.group_by_invoice(items)
        return groups[0] if groups else None

    @classmethod
    def get_highest_individual_item(
        cls,
        items: list[DebtItem | dict[str, Any]],
    ) -> DebtItem | dict[str, Any] | None:
        """
        Get the individual item with the highest amount.

        Args:
            items: List of debt items

        Returns:
            DebtItem or dict with highest amount, or None if no items
        """
        if not items:
            return None

        return max(items, key=lambda x: cls._get_item_amount(x))

    @classmethod
    def get_grouped_summary(
        cls,
        items: list[DebtItem | dict[str, Any]],
        max_groups: int = 5,
    ) -> dict[str, Any]:
        """
        Get summary of debt grouped by invoice.

        Args:
            items: List of debt items
            max_groups: Maximum number of groups to include

        Returns:
            Dictionary with grouped summary
        """
        groups = cls.group_by_invoice(items)
        highest = cls.get_highest_individual_item(items)

        highest_item_dict: dict[str, Any] | None = None
        if highest:
            if isinstance(highest, dict):
                highest_item_dict = highest
            else:
                highest_item_dict = highest.to_dict()

        return {
            "total_invoices": len(groups),
            "groups": [g.to_dict() for g in groups[:max_groups]],
            "highest_debt_invoice": groups[0].to_dict() if groups else None,
            "highest_individual_item": highest_item_dict,
        }
