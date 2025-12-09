"""
Pharmacy Debt Entity

Aggregate root representing a customer's outstanding debt.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.domains.pharmacy.domain.value_objects.debt_status import DebtStatus


@dataclass
class DebtItem:
    """Individual line item within a debt."""

    description: str
    amount: Decimal
    quantity: int = 1
    unit_price: Decimal | None = None
    product_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "description": self.description,
            "amount": float(self.amount),
            "quantity": self.quantity,
            "unit_price": float(self.unit_price) if self.unit_price else None,
            "product_code": self.product_code,
        }


@dataclass
class PharmacyDebt:
    """
    Pharmacy Debt entity representing a customer's outstanding debt.

    This is the aggregate root for debt-related operations.

    Attributes:
        id: Unique debt identifier from ERP
        customer_id: Customer identifier (phone number or ERP ID)
        customer_name: Customer's display name
        total_debt: Total outstanding amount
        due_date: Payment due date
        status: Current debt status
        items: List of debt line items
        created_at: When debt was created
        confirmed_at: When debt was confirmed by customer
    """

    id: str
    customer_id: str
    customer_name: str
    total_debt: Decimal
    status: DebtStatus
    items: list[DebtItem] = field(default_factory=list)
    due_date: date | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now())
    confirmed_at: datetime | None = None
    notes: str | None = None

    @property
    def is_confirmable(self) -> bool:
        """Check if debt can be confirmed."""
        return self.status == DebtStatus.PENDING and self.total_debt > 0

    @property
    def is_invoiceable(self) -> bool:
        """Check if debt can generate an invoice."""
        return self.status == DebtStatus.CONFIRMED

    @property
    def is_overdue(self) -> bool:
        """Check if debt is past due date."""
        if not self.due_date:
            return False
        return date.today() > self.due_date

    @property
    def items_count(self) -> int:
        """Get number of items in debt."""
        return len(self.items)

    def confirm(self) -> None:
        """
        Confirm the debt.

        Raises:
            ValueError: If debt cannot be confirmed
        """
        if not self.is_confirmable:
            raise ValueError(
                f"Debt cannot be confirmed. Status: {self.status}, Amount: {self.total_debt}"
            )
        self.status = DebtStatus.CONFIRMED
        self.confirmed_at = datetime.now()

    def mark_invoiced(self) -> None:
        """
        Mark debt as invoiced.

        Raises:
            ValueError: If debt cannot be invoiced
        """
        if not self.is_invoiceable:
            raise ValueError(f"Debt cannot be invoiced. Status: {self.status}")
        self.status = DebtStatus.INVOICED

    def cancel(self) -> None:
        """
        Cancel the debt.

        Raises:
            ValueError: If debt cannot be cancelled
        """
        if not self.status.can_transition_to(DebtStatus.CANCELLED):
            raise ValueError(f"Debt cannot be cancelled. Status: {self.status}")
        self.status = DebtStatus.CANCELLED

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "total_debt": float(self.total_debt),
            "status": self.status.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "items": [item.to_dict() for item in self.items],
            "items_count": self.items_count,
            "created_at": self.created_at.isoformat(),
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "is_overdue": self.is_overdue,
            "notes": self.notes,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """Get summarized representation for chat context."""
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "total_debt": float(self.total_debt),
            "status": self.status.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "items_count": self.items_count,
            "is_overdue": self.is_overdue,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PharmacyDebt":
        """
        Create PharmacyDebt from dictionary.

        Args:
            data: Dictionary with debt data

        Returns:
            PharmacyDebt instance
        """
        items = [
            DebtItem(
                description=item.get("description", ""),
                amount=Decimal(str(item.get("amount", 0))),
                quantity=item.get("quantity", 1),
                unit_price=(
                    Decimal(str(item["unit_price"])) if item.get("unit_price") else None
                ),
                product_code=item.get("product_code"),
            )
            for item in data.get("items", [])
        ]

        due_date = None
        if data.get("due_date"):
            if isinstance(data["due_date"], str):
                due_date = date.fromisoformat(data["due_date"])
            elif isinstance(data["due_date"], date):
                due_date = data["due_date"]

        created_at = datetime.now()
        if data.get("created_at"):
            if isinstance(data["created_at"], str):
                created_at = datetime.fromisoformat(data["created_at"])
            elif isinstance(data["created_at"], datetime):
                created_at = data["created_at"]

        confirmed_at = None
        if data.get("confirmed_at"):
            if isinstance(data["confirmed_at"], str):
                confirmed_at = datetime.fromisoformat(data["confirmed_at"])
            elif isinstance(data["confirmed_at"], datetime):
                confirmed_at = data["confirmed_at"]

        return cls(
            id=data.get("id", ""),
            customer_id=data.get("customer_id", ""),
            customer_name=data.get("customer_name", ""),
            total_debt=Decimal(str(data.get("total_debt", 0))),
            status=DebtStatus(data.get("status", "pending")),
            items=items,
            due_date=due_date,
            created_at=created_at,
            confirmed_at=confirmed_at,
            notes=data.get("notes"),
        )
