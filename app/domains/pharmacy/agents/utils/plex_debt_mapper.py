"""
Plex Debt Mapper

Utility for mapping Plex ERP balance responses to domain entities.
Handles transformation between external API format and internal PharmacyDebt entity.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domains.pharmacy.domain.entities.pharmacy_debt import DebtItem, PharmacyDebt
from app.domains.pharmacy.domain.value_objects.debt_status import DebtStatus


class PlexDebtMapper:
    """
    Maps Plex ERP responses to domain entities.

    Handles the transformation of raw Plex /saldo_cliente responses
    to PharmacyDebt domain entities.

    Single Responsibility: Transform Plex data to domain entities.
    """

    @classmethod
    def map_balance_to_debt(
        cls,
        balance_data: dict[str, Any],
        customer_id: int,
        customer_name: str,
    ) -> PharmacyDebt:
        """
        Map Plex balance response to PharmacyDebt entity.

        Args:
            balance_data: Raw response from Plex /saldo_cliente
            customer_id: Plex customer ID
            customer_name: Customer display name

        Returns:
            PharmacyDebt domain entity
        """
        # Extract items from Plex response
        items = cls._extract_items(balance_data.get("detalle", []))

        # Sort items by amount descending to ensure highest values are first
        items.sort(key=lambda x: x.amount, reverse=True)

        # Build debt entity
        return PharmacyDebt.from_dict(
            {
                "id": str(balance_data.get("id", customer_id)),
                "customer_id": str(customer_id),
                "customer_name": customer_name,
                "total_debt": balance_data.get("saldo", 0),
                "status": DebtStatus.PENDING.value,
                "due_date": balance_data.get("fecha_vencimiento"),
                "items": [item.to_dict() for item in items],
                "created_at": balance_data.get("fecha"),
                "notes": balance_data.get("observaciones"),
            }
        )

    @classmethod
    def _extract_items(cls, detalle: list[dict[str, Any]]) -> list[DebtItem]:
        """
        Extract DebtItem list from Plex detalle array.

        Args:
            detalle: Raw detail array from Plex response

        Returns:
            List of DebtItem objects
        """
        items: list[DebtItem] = []

        for item_data in detalle:
            items.append(
                DebtItem(
                    description=item_data.get("descripcion", "Item"),
                    amount=Decimal(str(item_data.get("importe", 0))),
                    quantity=item_data.get("cantidad", 1),
                    unit_price=(
                        Decimal(str(item_data["precio_unitario"])) if item_data.get("precio_unitario") else None
                    ),
                    product_code=item_data.get("codigo"),
                    invoice_number=item_data.get("comprobante"),
                    invoice_date=item_data.get("fecha"),
                )
            )

        return items

    @classmethod
    def reconstruct_items(
        cls,
        items_data: list[dict[str, Any]],
    ) -> list[DebtItem]:
        """
        Reconstruct DebtItem objects from stored dictionary data.

        Used when items were serialized to state and need to be
        converted back to DebtItem objects for formatting.

        Args:
            items_data: List of item dictionaries from state

        Returns:
            List of DebtItem objects
        """
        items: list[DebtItem] = []

        for data in items_data:
            items.append(
                DebtItem(
                    description=data.get("description", "Item"),
                    amount=Decimal(str(data.get("amount", 0))),
                    quantity=data.get("quantity", 1),
                    unit_price=(Decimal(str(data["unit_price"])) if data.get("unit_price") else None),
                    product_code=data.get("product_code"),
                    invoice_number=data.get("invoice_number"),
                    invoice_date=data.get("invoice_date"),
                )
            )

        return items
