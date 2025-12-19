"""
Payment Transaction Entity

Represents a payment transaction through Mercado Pago.
Tracks the full lifecycle from preference creation to PLEX registration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class PaymentStatus(Enum):
    """Payment status enum matching Mercado Pago statuses."""

    PENDING = "pending"  # Preference created, awaiting payment
    APPROVED = "approved"  # Payment successful
    REJECTED = "rejected"  # Payment rejected
    CANCELLED = "cancelled"  # Payment cancelled
    IN_PROCESS = "in_process"  # Payment being processed
    IN_MEDIATION = "in_mediation"  # Payment in dispute
    REFUNDED = "refunded"  # Payment refunded
    CHARGED_BACK = "charged_back"  # Chargeback received

    @classmethod
    def from_mp_status(cls, mp_status: str) -> PaymentStatus:
        """Convert Mercado Pago status string to enum."""
        status_map = {
            "pending": cls.PENDING,
            "approved": cls.APPROVED,
            "authorized": cls.APPROVED,
            "in_process": cls.IN_PROCESS,
            "in_mediation": cls.IN_MEDIATION,
            "rejected": cls.REJECTED,
            "cancelled": cls.CANCELLED,
            "refunded": cls.REFUNDED,
            "charged_back": cls.CHARGED_BACK,
        }
        return status_map.get(mp_status.lower(), cls.PENDING)


@dataclass
class PaymentTransaction:
    """
    Represents a payment transaction through Mercado Pago.

    Tracks the complete payment lifecycle:
    1. Preference creation (pending)
    2. Customer payment (approved/rejected)
    3. PLEX registration (plex_receipt set)

    Attributes:
        id: Internal transaction ID
        preference_id: Mercado Pago preference ID
        payment_id: Mercado Pago payment ID (set after payment)
        customer_id: Plex customer ID
        customer_phone: Customer WhatsApp phone for notifications
        amount: Payment amount
        status: Current payment status
        external_reference: Reference for webhook correlation (customer_id:debt_id:uuid)
        init_point: Mercado Pago payment URL
        plex_receipt: PLEX receipt number (set after REGISTRAR_PAGO_CLIENTE)
        plex_new_balance: Customer's new balance after payment
        created_at: When transaction was created
        paid_at: When payment was approved
        registered_at: When payment was registered in PLEX
    """

    id: str
    preference_id: str
    customer_id: int
    amount: Decimal
    external_reference: str
    customer_phone: str | None = None
    status: PaymentStatus = PaymentStatus.PENDING
    payment_id: str | None = None
    init_point: str | None = None
    plex_receipt: str | None = None
    plex_new_balance: Decimal | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    paid_at: datetime | None = None
    registered_at: datetime | None = None

    def mark_approved(self, payment_id: str) -> None:
        """
        Mark transaction as approved.

        Called when Mercado Pago webhook confirms successful payment.

        Args:
            payment_id: Mercado Pago payment ID
        """
        self.payment_id = payment_id
        self.status = PaymentStatus.APPROVED
        self.paid_at = datetime.now(UTC)

    def mark_rejected(self) -> None:
        """Mark transaction as rejected."""
        self.status = PaymentStatus.REJECTED

    def mark_cancelled(self) -> None:
        """Mark transaction as cancelled."""
        self.status = PaymentStatus.CANCELLED

    def set_plex_receipt(self, receipt: str, new_balance: Decimal | None = None) -> None:
        """
        Set PLEX receipt after successful registration.

        Called after REGISTRAR_PAGO_CLIENTE succeeds.

        Args:
            receipt: PLEX receipt number (e.g., "RC X 0001-00016790")
            new_balance: Customer's new balance after payment
        """
        self.plex_receipt = receipt
        self.plex_new_balance = new_balance
        self.registered_at = datetime.now(UTC)

    @property
    def is_payable(self) -> bool:
        """Check if payment link is still valid for payment."""
        return self.status == PaymentStatus.PENDING

    @property
    def is_paid(self) -> bool:
        """Check if payment was successful."""
        return self.status == PaymentStatus.APPROVED

    @property
    def is_registered_in_plex(self) -> bool:
        """Check if payment was registered in PLEX."""
        return self.plex_receipt is not None

    @property
    def is_complete(self) -> bool:
        """Check if full payment cycle is complete (paid + registered in PLEX)."""
        return self.is_paid and self.is_registered_in_plex

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "preference_id": self.preference_id,
            "payment_id": self.payment_id,
            "customer_id": self.customer_id,
            "customer_phone": self.customer_phone,
            "amount": float(self.amount),
            "status": self.status.value,
            "external_reference": self.external_reference,
            "init_point": self.init_point,
            "plex_receipt": self.plex_receipt,
            "plex_new_balance": float(self.plex_new_balance) if self.plex_new_balance else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "is_complete": self.is_complete,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaymentTransaction:
        """Create instance from dictionary."""
        return cls(
            id=data["id"],
            preference_id=data["preference_id"],
            payment_id=data.get("payment_id"),
            customer_id=data["customer_id"],
            customer_phone=data.get("customer_phone"),
            amount=Decimal(str(data["amount"])),
            status=PaymentStatus(data.get("status", "pending")),
            external_reference=data["external_reference"],
            init_point=data.get("init_point"),
            plex_receipt=data.get("plex_receipt"),
            plex_new_balance=Decimal(str(data["plex_new_balance"])) if data.get("plex_new_balance") else None,
        )
