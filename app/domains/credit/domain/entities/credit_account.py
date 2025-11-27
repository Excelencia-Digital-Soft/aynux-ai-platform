"""
Credit Account Entity

Aggregate root for credit accounts with balance management and credit lifecycle.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.core.domain import (
    AggregateRoot,
    BusinessRuleViolationException,
    CreditLimitExceededException,
    InvalidOperationException,
)

from ..value_objects.account_status import (
    AccountStatus,
    CollectionStatus,
    CreditLimit,
    InterestRate,
    RiskLevel,
)


@dataclass
class CreditAccount(AggregateRoot[int]):
    """
    Credit Account aggregate root.

    Manages credit account lifecycle, balances, and credit operations.

    Example:
        ```python
        account = CreditAccount(
            customer_id=123,
            credit_limit=CreditLimit(Decimal("50000")),
            interest_rate=InterestRate(Decimal("0.24")),
        )
        account.activate()
        account.use_credit(Decimal("10000"), "Purchase at Store X")
        account.make_payment(Decimal("5000"))
        ```
    """

    # Account identifiers
    account_number: str = ""
    customer_id: int = 0
    customer_name: str = ""

    # Credit configuration
    credit_limit: CreditLimit = field(default_factory=lambda: CreditLimit(Decimal("0")))
    interest_rate: InterestRate = field(default_factory=lambda: InterestRate(Decimal("0.24")))
    risk_level: RiskLevel = RiskLevel.LOW

    # Balances
    used_credit: Decimal = Decimal("0")
    pending_charges: Decimal = Decimal("0")
    accrued_interest: Decimal = Decimal("0")

    # Payment configuration
    payment_day: int = 10  # Day of month for payment
    minimum_payment_percentage: Decimal = Decimal("0.05")  # 5% minimum payment
    grace_period_days: int = 20

    # Status
    status: AccountStatus = AccountStatus.PENDING_APPROVAL
    collection_status: CollectionStatus = CollectionStatus.NONE

    # Dates
    opened_at: datetime | None = None
    activated_at: datetime | None = None
    last_payment_date: date | None = None
    next_payment_date: date | None = None
    last_statement_date: date | None = None
    blocked_at: datetime | None = None
    closed_at: datetime | None = None

    # Payment tracking
    consecutive_on_time_payments: int = 0
    consecutive_late_payments: int = 0
    total_payments_made: int = 0

    # Collection info
    days_overdue: int = 0
    last_collection_action: datetime | None = None

    def __post_init__(self):
        """Initialize credit account."""
        if not self.opened_at:
            self.opened_at = datetime.now(UTC)
        if not self.account_number:
            self.account_number = self._generate_account_number()

    def _generate_account_number(self) -> str:
        """Generate unique account number."""
        import uuid

        return f"CR-{uuid.uuid4().hex[:8].upper()}"

    # Properties

    @property
    def available_credit(self) -> Decimal:
        """Calculate available credit."""
        return self.credit_limit.amount - self.used_credit - self.pending_charges

    @property
    def total_debt(self) -> Decimal:
        """Total debt including interest."""
        return self.used_credit + self.pending_charges + self.accrued_interest

    @property
    def minimum_payment(self) -> Decimal:
        """Calculate minimum payment amount."""
        calculated = self.total_debt * self.minimum_payment_percentage
        return max(calculated, Decimal("100"))  # Minimum $100

    @property
    def utilization_ratio(self) -> Decimal:
        """Credit utilization percentage."""
        if self.credit_limit.amount == 0:
            return Decimal("0")
        return (self.used_credit / self.credit_limit.amount) * 100

    @property
    def is_overdue(self) -> bool:
        """Check if account has overdue payments."""
        return self.days_overdue > 0

    @property
    def is_blocked(self) -> bool:
        """Check if account is blocked."""
        return self.status == AccountStatus.BLOCKED

    # Status Transitions

    def activate(self) -> None:
        """Activate the credit account."""
        if not self.status.can_transition_to(AccountStatus.ACTIVE):
            raise InvalidOperationException(
                operation="activate",
                current_state=self.status.value,
            )

        self.status = AccountStatus.ACTIVE
        self.activated_at = datetime.now(UTC)
        self._calculate_next_payment_date()
        self.touch()

    def block(self, reason: str | None = None) -> None:
        """Block the credit account."""
        if not self.status.can_transition_to(AccountStatus.BLOCKED):
            raise InvalidOperationException(
                operation="block",
                current_state=self.status.value,
            )

        self.status = AccountStatus.BLOCKED
        self.blocked_at = datetime.now(UTC)
        self.touch()

    def unblock(self) -> None:
        """Unblock the credit account."""
        if self.status != AccountStatus.BLOCKED:
            raise InvalidOperationException(
                operation="unblock",
                current_state=self.status.value,
            )

        # Can only unblock if not overdue
        if self.days_overdue > 0:
            raise BusinessRuleViolationException(
                rule="Cannot unblock account with overdue balance",
                details={"days_overdue": self.days_overdue},
            )

        self.status = AccountStatus.ACTIVE
        self.blocked_at = None
        self.touch()

    def mark_overdue(self, days: int) -> None:
        """Mark account as overdue."""
        if not self.status.can_transition_to(AccountStatus.OVERDUE):
            return  # Silently ignore if can't transition

        self.status = AccountStatus.OVERDUE
        self.days_overdue = days
        self.consecutive_late_payments += 1
        self.consecutive_on_time_payments = 0
        self._update_collection_status()
        self.touch()

    def close(self, reason: str | None = None) -> None:
        """Close the credit account."""
        if self.total_debt > 0:
            raise BusinessRuleViolationException(
                rule="Cannot close account with outstanding balance",
                details={"total_debt": float(self.total_debt)},
            )

        if not self.status.can_transition_to(AccountStatus.CLOSED):
            raise InvalidOperationException(
                operation="close",
                current_state=self.status.value,
            )

        self.status = AccountStatus.CLOSED
        self.closed_at = datetime.now(UTC)
        self.touch()

    # Credit Operations

    def use_credit(self, amount: Decimal, description: str | None = None) -> None:
        """
        Use credit from the account.

        Args:
            amount: Amount to charge
            description: Description of the charge
        """
        if not self.status.can_make_purchases():
            raise InvalidOperationException(
                operation="use_credit",
                current_state=self.status.value,
                message="Account cannot make purchases in current state",
            )

        if amount <= 0:
            raise BusinessRuleViolationException(
                rule="Charge amount must be positive",
                details={"amount": float(amount)},
            )

        if amount > self.available_credit:
            raise CreditLimitExceededException(
                account_id=self.id or 0,
                requested=float(amount),
                available=float(self.available_credit),
            )

        self.used_credit += amount
        self.touch()

    def make_payment(self, amount: Decimal) -> dict[str, Any]:
        """
        Process a payment to the account.

        Args:
            amount: Payment amount

        Returns:
            Payment result details
        """
        if not self.status.can_receive_payments():
            raise InvalidOperationException(
                operation="make_payment",
                current_state=self.status.value,
                message="Account cannot receive payments in current state",
            )

        if amount <= 0:
            raise BusinessRuleViolationException(
                rule="Payment amount must be positive",
                details={"amount": float(amount)},
            )

        # Apply payment: first to interest, then to pending, then to principal
        remaining = amount
        interest_paid = Decimal("0")
        charges_paid = Decimal("0")
        principal_paid = Decimal("0")

        if remaining > 0 and self.accrued_interest > 0:
            interest_paid = min(remaining, self.accrued_interest)
            self.accrued_interest -= interest_paid
            remaining -= interest_paid

        if remaining > 0 and self.pending_charges > 0:
            charges_paid = min(remaining, self.pending_charges)
            self.pending_charges -= charges_paid
            remaining -= charges_paid

        if remaining > 0 and self.used_credit > 0:
            principal_paid = min(remaining, self.used_credit)
            self.used_credit -= principal_paid
            remaining -= principal_paid

        # Update payment tracking
        self.last_payment_date = date.today()
        self.total_payments_made += 1
        self._calculate_next_payment_date()

        # Update status if was overdue
        if self.status == AccountStatus.OVERDUE and amount >= self.minimum_payment:
            self.days_overdue = 0
            self.status = AccountStatus.ACTIVE
            self.consecutive_on_time_payments = 1
            self.consecutive_late_payments = 0
            self.collection_status = CollectionStatus.NONE

        self.touch()

        return {
            "total_paid": float(amount),
            "interest_paid": float(interest_paid),
            "charges_paid": float(charges_paid),
            "principal_paid": float(principal_paid),
            "overpayment": float(remaining),
            "remaining_balance": float(self.total_debt),
        }

    def calculate_interest(self, days: int | None = None) -> Decimal:
        """
        Calculate interest for a period.

        Args:
            days: Number of days (defaults to days since last statement)
        """
        if days is None:
            if self.last_statement_date:
                days = (date.today() - self.last_statement_date).days
            else:
                days = 30

        return self.interest_rate.calculate_interest(self.used_credit, days)

    def apply_interest(self) -> Decimal:
        """Apply accrued interest to the account."""
        interest = self.calculate_interest()
        self.accrued_interest += interest
        self.last_statement_date = date.today()
        self.touch()
        return interest

    # Credit Limit Management

    def increase_credit_limit(self, amount: Decimal, reason: str | None = None) -> None:
        """Increase credit limit."""
        if amount <= 0:
            raise BusinessRuleViolationException(
                rule="Increase amount must be positive",
                details={"amount": float(amount)},
            )

        self.credit_limit = self.credit_limit.increase(amount)
        self.touch()

    def decrease_credit_limit(self, amount: Decimal, reason: str | None = None) -> None:
        """Decrease credit limit."""
        new_limit = self.credit_limit.amount - amount

        if new_limit < self.used_credit:
            raise BusinessRuleViolationException(
                rule="New limit cannot be less than used credit",
                details={
                    "new_limit": float(new_limit),
                    "used_credit": float(self.used_credit),
                },
            )

        self.credit_limit = self.credit_limit.decrease(amount)
        self.touch()

    # Risk Management

    def update_risk_level(self, new_level: RiskLevel) -> None:
        """Update risk level and adjust interest rate."""
        old_rate = self.interest_rate.annual_rate
        adjustment = new_level.get_interest_adjustment() - self.risk_level.get_interest_adjustment()
        new_rate = old_rate + adjustment

        self.risk_level = new_level
        self.interest_rate = InterestRate(new_rate)
        self.touch()

    # Helper Methods

    def _calculate_next_payment_date(self) -> None:
        """Calculate next payment date."""
        today = date.today()

        # Next payment is on the payment_day of current or next month
        if today.day <= self.payment_day:
            next_date = date(today.year, today.month, self.payment_day)
        else:
            if today.month == 12:
                next_date = date(today.year + 1, 1, self.payment_day)
            else:
                next_date = date(today.year, today.month + 1, self.payment_day)

        self.next_payment_date = next_date

    def _update_collection_status(self) -> None:
        """Update collection status based on days overdue."""
        if self.days_overdue <= 0:
            self.collection_status = CollectionStatus.NONE
        elif self.days_overdue <= 30:
            self.collection_status = CollectionStatus.SOFT_REMINDER
        elif self.days_overdue <= 60:
            self.collection_status = CollectionStatus.FORMAL_NOTICE
        elif self.days_overdue <= 90:
            self.collection_status = CollectionStatus.COLLECTION_AGENCY
        else:
            self.collection_status = CollectionStatus.LEGAL_ACTION

    def can_request_limit_increase(self) -> bool:
        """Check if account is eligible for limit increase."""
        return (
            self.status == AccountStatus.ACTIVE
            and self.consecutive_on_time_payments >= 6
            and self.utilization_ratio >= 50
            and self.days_overdue == 0
        )

    # Serialization

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary."""
        return {
            "id": self.id,
            "account_number": self.account_number,
            "customer_name": self.customer_name,
            "credit_limit": float(self.credit_limit.amount),
            "used_credit": float(self.used_credit),
            "available_credit": float(self.available_credit),
            "minimum_payment": float(self.minimum_payment),
            "next_payment_date": self.next_payment_date.isoformat() if self.next_payment_date else None,
            "status": self.status.value,
            "is_overdue": self.is_overdue,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        """Convert to detailed dictionary."""
        return {
            **self.to_summary_dict(),
            "customer_id": self.customer_id,
            "interest_rate": str(self.interest_rate),
            "risk_level": self.risk_level.value,
            "total_debt": float(self.total_debt),
            "accrued_interest": float(self.accrued_interest),
            "pending_charges": float(self.pending_charges),
            "utilization_ratio": float(self.utilization_ratio),
            "days_overdue": self.days_overdue,
            "collection_status": self.collection_status.value,
            "consecutive_on_time_payments": self.consecutive_on_time_payments,
            "last_payment_date": self.last_payment_date.isoformat() if self.last_payment_date else None,
        }

    def to_chat_context(self) -> dict[str, Any]:
        """Convert to chat context for agent conversations."""
        return {
            "account_number": self.account_number,
            "available_credit": f"${self.available_credit:,.2f}",
            "total_debt": f"${self.total_debt:,.2f}",
            "minimum_payment": f"${self.minimum_payment:,.2f}",
            "next_payment_date": self.next_payment_date.strftime("%d/%m/%Y") if self.next_payment_date else "N/A",
            "status": self.status.value,
            "is_overdue": self.is_overdue,
            "days_overdue": self.days_overdue if self.is_overdue else 0,
        }
