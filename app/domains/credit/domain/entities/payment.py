"""
Payment Entity

Entity representing a payment transaction on a credit account.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.core.domain import AggregateRoot, InvalidOperationException

from ..value_objects.account_status import PaymentMethod, PaymentStatus, PaymentType


@dataclass
class Payment(AggregateRoot[int]):
    """
    Payment entity for credit domain.

    Represents a payment transaction with lifecycle management.

    Example:
        ```python
        payment = Payment.create(
            account_id=123,
            amount=Decimal("5000"),
            payment_type=PaymentType.REGULAR,
            payment_method=PaymentMethod.BANK_TRANSFER,
        )
        payment.process()
        payment.complete(transaction_id="TXN123")
        ```
    """

    # References
    account_id: int = 0
    customer_id: int = 0
    account_number: str = ""

    # Payment details
    amount: Decimal = Decimal("0")
    payment_type: PaymentType = PaymentType.REGULAR
    payment_method: PaymentMethod = PaymentMethod.BANK_TRANSFER

    # Status
    status: PaymentStatus = PaymentStatus.PENDING

    # Transaction details
    transaction_id: str | None = None
    reference_number: str | None = None
    receipt_url: str | None = None

    # Payment breakdown
    interest_paid: Decimal = Decimal("0")
    charges_paid: Decimal = Decimal("0")
    principal_paid: Decimal = Decimal("0")

    # Timestamps
    initiated_at: datetime | None = None
    processed_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None

    # Error handling
    failure_reason: str | None = None
    retry_count: int = 0
    max_retries: int = 3

    # Metadata
    description: str | None = None
    notes: str | None = None

    def __post_init__(self):
        """Initialize payment."""
        if not self.initiated_at:
            self.initiated_at = datetime.now(UTC)
        if not self.reference_number:
            self.reference_number = self._generate_reference()

    def _generate_reference(self) -> str:
        """Generate unique payment reference."""
        import uuid

        return f"PAY-{uuid.uuid4().hex[:8].upper()}"

    # Status Transitions

    def process(self) -> None:
        """Start processing the payment."""
        if self.status != PaymentStatus.PENDING:
            raise InvalidOperationException(
                operation="process",
                current_state=self.status.value,
            )

        self.status = PaymentStatus.PROCESSING
        self.processed_at = datetime.now(UTC)
        self.touch()

    def complete(
        self,
        transaction_id: str | None = None,
        interest_paid: Decimal | None = None,
        charges_paid: Decimal | None = None,
        principal_paid: Decimal | None = None,
    ) -> None:
        """
        Complete the payment successfully.

        Args:
            transaction_id: External transaction ID
            interest_paid: Amount applied to interest
            charges_paid: Amount applied to charges
            principal_paid: Amount applied to principal
        """
        if self.status not in [PaymentStatus.PENDING, PaymentStatus.PROCESSING]:
            raise InvalidOperationException(
                operation="complete",
                current_state=self.status.value,
            )

        self.status = PaymentStatus.COMPLETED
        self.completed_at = datetime.now(UTC)

        if transaction_id:
            self.transaction_id = transaction_id
        if interest_paid is not None:
            self.interest_paid = interest_paid
        if charges_paid is not None:
            self.charges_paid = charges_paid
        if principal_paid is not None:
            self.principal_paid = principal_paid

        # Generate receipt URL
        self.receipt_url = f"/receipts/{self.reference_number}"
        self.touch()

    def fail(self, reason: str) -> None:
        """Mark payment as failed."""
        if self.status.is_final():
            raise InvalidOperationException(
                operation="fail",
                current_state=self.status.value,
            )

        self.status = PaymentStatus.FAILED
        self.failed_at = datetime.now(UTC)
        self.failure_reason = reason
        self.touch()

    def cancel(self, reason: str | None = None) -> None:
        """Cancel the payment."""
        if self.status.is_final():
            raise InvalidOperationException(
                operation="cancel",
                current_state=self.status.value,
            )

        self.status = PaymentStatus.CANCELLED
        self.failure_reason = reason or "Cancelled by user"
        self.touch()

    def refund(self, reason: str | None = None) -> None:
        """Refund a completed payment."""
        if self.status != PaymentStatus.COMPLETED:
            raise InvalidOperationException(
                operation="refund",
                current_state=self.status.value,
                message="Only completed payments can be refunded",
            )

        self.status = PaymentStatus.REFUNDED
        self.failure_reason = reason or "Refunded"
        self.touch()

    def retry(self) -> bool:
        """
        Attempt to retry a failed payment.

        Returns:
            True if retry is allowed, False if max retries exceeded
        """
        if self.status != PaymentStatus.FAILED:
            raise InvalidOperationException(
                operation="retry",
                current_state=self.status.value,
            )

        if self.retry_count >= self.max_retries:
            return False

        self.retry_count += 1
        self.status = PaymentStatus.PENDING
        self.failure_reason = None
        self.failed_at = None
        self.touch()
        return True

    # Properties

    @property
    def is_successful(self) -> bool:
        """Check if payment was successful."""
        return self.status == PaymentStatus.COMPLETED

    @property
    def is_pending(self) -> bool:
        """Check if payment is still pending."""
        return self.status in [PaymentStatus.PENDING, PaymentStatus.PROCESSING]

    @property
    def can_be_retried(self) -> bool:
        """Check if payment can be retried."""
        return self.status == PaymentStatus.FAILED and self.retry_count < self.max_retries

    @property
    def processing_time_seconds(self) -> float | None:
        """Get processing time in seconds."""
        if self.initiated_at and self.completed_at:
            return (self.completed_at - self.initiated_at).total_seconds()
        return None

    # Serialization

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary."""
        return {
            "id": self.id,
            "reference_number": self.reference_number,
            "amount": float(self.amount),
            "payment_type": self.payment_type.value,
            "payment_method": self.payment_method.value,
            "status": self.status.value,
            "initiated_at": self.initiated_at.isoformat() if self.initiated_at else None,
            "is_successful": self.is_successful,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        """Convert to detailed dictionary."""
        return {
            **self.to_summary_dict(),
            "account_id": self.account_id,
            "account_number": self.account_number,
            "transaction_id": self.transaction_id,
            "receipt_url": self.receipt_url,
            "interest_paid": float(self.interest_paid),
            "charges_paid": float(self.charges_paid),
            "principal_paid": float(self.principal_paid),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "failure_reason": self.failure_reason,
            "retry_count": self.retry_count,
        }

    def to_chat_context(self) -> dict[str, Any]:
        """Convert to chat context for agent conversations."""
        return {
            "reference": self.reference_number,
            "amount": f"${self.amount:,.2f}",
            "status": self.status.value,
            "date": self.initiated_at.strftime("%d/%m/%Y") if self.initiated_at else "N/A",
            "receipt_url": self.receipt_url if self.is_successful else None,
        }

    @classmethod
    def create(
        cls,
        account_id: int,
        amount: Decimal,
        payment_type: PaymentType = PaymentType.REGULAR,
        payment_method: PaymentMethod = PaymentMethod.BANK_TRANSFER,
        customer_id: int | None = None,
        account_number: str | None = None,
        description: str | None = None,
    ) -> "Payment":
        """
        Factory method to create a new payment.

        Args:
            account_id: Credit account ID
            amount: Payment amount
            payment_type: Type of payment
            payment_method: Payment method
            customer_id: Optional customer ID
            account_number: Optional account number
            description: Optional description

        Returns:
            New Payment instance
        """
        return cls(
            account_id=account_id,
            amount=amount,
            payment_type=payment_type,
            payment_method=payment_method,
            customer_id=customer_id or 0,
            account_number=account_number or "",
            description=description,
        )
