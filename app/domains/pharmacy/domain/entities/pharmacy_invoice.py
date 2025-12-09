"""
Pharmacy Invoice Entity

Entity representing a generated invoice from confirmed debt.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class InvoiceItem:
    """Individual line item within an invoice."""

    description: str
    quantity: int
    unit_price: Decimal
    total: Decimal
    product_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "total": float(self.total),
            "product_code": self.product_code,
        }


@dataclass
class PharmacyInvoice:
    """
    Pharmacy Invoice entity representing a generated invoice.

    Attributes:
        id: Unique invoice identifier
        invoice_number: Display invoice number (e.g., "FAC-2024-001234")
        debt_id: Reference to original debt
        customer_id: Customer identifier
        customer_name: Customer name for invoice
        subtotal: Invoice subtotal before tax
        tax_amount: Tax component
        total_amount: Invoice total
        items: Invoice line items
        generated_at: Generation timestamp
        pdf_url: Optional URL to PDF document
    """

    id: str
    invoice_number: str
    debt_id: str
    customer_id: str
    customer_name: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    items: list[InvoiceItem] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now())
    pdf_url: str | None = None
    notes: str | None = None

    @property
    def tax_rate(self) -> Decimal:
        """Calculate effective tax rate."""
        if self.subtotal == 0:
            return Decimal("0")
        return (self.tax_amount / self.subtotal * 100).quantize(Decimal("0.01"))

    @property
    def items_count(self) -> int:
        """Get number of items in invoice."""
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "debt_id": self.debt_id,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "subtotal": float(self.subtotal),
            "tax_amount": float(self.tax_amount),
            "tax_rate": float(self.tax_rate),
            "total_amount": float(self.total_amount),
            "items": [item.to_dict() for item in self.items],
            "items_count": self.items_count,
            "generated_at": self.generated_at.isoformat(),
            "pdf_url": self.pdf_url,
            "notes": self.notes,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """Get summarized representation for chat context."""
        return {
            "invoice_number": self.invoice_number,
            "customer_name": self.customer_name,
            "total_amount": float(self.total_amount),
            "generated_at": self.generated_at.isoformat(),
            "pdf_url": self.pdf_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PharmacyInvoice":
        """
        Create PharmacyInvoice from dictionary.

        Args:
            data: Dictionary with invoice data

        Returns:
            PharmacyInvoice instance
        """
        items = [
            InvoiceItem(
                description=item.get("description", ""),
                quantity=item.get("quantity", 1),
                unit_price=Decimal(str(item.get("unit_price", 0))),
                total=Decimal(str(item.get("total", 0))),
                product_code=item.get("product_code"),
            )
            for item in data.get("items", [])
        ]

        generated_at = datetime.now()
        if data.get("generated_at"):
            if isinstance(data["generated_at"], str):
                generated_at = datetime.fromisoformat(data["generated_at"])
            elif isinstance(data["generated_at"], datetime):
                generated_at = data["generated_at"]

        return cls(
            id=data.get("id", ""),
            invoice_number=data.get("invoice_number", ""),
            debt_id=data.get("debt_id", ""),
            customer_id=data.get("customer_id", ""),
            customer_name=data.get("customer_name", ""),
            subtotal=Decimal(str(data.get("subtotal", 0))),
            tax_amount=Decimal(str(data.get("tax_amount", 0))),
            total_amount=Decimal(str(data.get("total_amount", 0))),
            items=items,
            generated_at=generated_at,
            pdf_url=data.get("pdf_url"),
            notes=data.get("notes"),
        )
