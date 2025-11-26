"""
Credit Account Status Value Objects

Value objects representing statuses and types in the credit domain.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class AccountStatus(str, Enum):
    """Status of a credit account."""

    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    BLOCKED = "blocked"
    OVERDUE = "overdue"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    DEFAULTED = "defaulted"

    def is_active(self) -> bool:
        """Check if account can be used."""
        return self == AccountStatus.ACTIVE

    def can_make_purchases(self) -> bool:
        """Check if account can make purchases."""
        return self in [AccountStatus.ACTIVE]

    def can_receive_payments(self) -> bool:
        """Check if account can receive payments."""
        return self in [
            AccountStatus.ACTIVE,
            AccountStatus.BLOCKED,
            AccountStatus.OVERDUE,
            AccountStatus.SUSPENDED,
            AccountStatus.DEFAULTED,
        ]

    def can_transition_to(self, new_status: "AccountStatus") -> bool:
        """Check if status transition is valid."""
        transitions = {
            AccountStatus.PENDING_APPROVAL: [AccountStatus.ACTIVE, AccountStatus.CLOSED],
            AccountStatus.ACTIVE: [
                AccountStatus.BLOCKED,
                AccountStatus.OVERDUE,
                AccountStatus.SUSPENDED,
                AccountStatus.CLOSED,
            ],
            AccountStatus.BLOCKED: [AccountStatus.ACTIVE, AccountStatus.SUSPENDED, AccountStatus.CLOSED],
            AccountStatus.OVERDUE: [
                AccountStatus.ACTIVE,
                AccountStatus.BLOCKED,
                AccountStatus.DEFAULTED,
                AccountStatus.CLOSED,
            ],
            AccountStatus.SUSPENDED: [AccountStatus.ACTIVE, AccountStatus.CLOSED],
            AccountStatus.DEFAULTED: [AccountStatus.CLOSED],
            AccountStatus.CLOSED: [],
        }
        return new_status in transitions.get(self, [])


class PaymentStatus(str, Enum):
    """Status of a payment."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

    def is_successful(self) -> bool:
        """Check if payment was successful."""
        return self == PaymentStatus.COMPLETED

    def is_final(self) -> bool:
        """Check if payment is in final state."""
        return self in [
            PaymentStatus.COMPLETED,
            PaymentStatus.FAILED,
            PaymentStatus.REFUNDED,
            PaymentStatus.CANCELLED,
        ]


class PaymentType(str, Enum):
    """Type of payment."""

    REGULAR = "regular"
    MINIMUM = "minimum"
    FULL = "full"
    EXTRA = "extra"
    EARLY = "early"
    LATE = "late"


class PaymentMethod(str, Enum):
    """Payment method."""

    BANK_TRANSFER = "bank_transfer"
    DEBIT_CARD = "debit_card"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    CHECK = "check"
    DIRECT_DEBIT = "direct_debit"


class CollectionStatus(str, Enum):
    """Collection status for overdue accounts."""

    NONE = "none"
    SOFT_REMINDER = "soft_reminder"
    FORMAL_NOTICE = "formal_notice"
    COLLECTION_AGENCY = "collection_agency"
    LEGAL_ACTION = "legal_action"
    WRITTEN_OFF = "written_off"

    def get_severity(self) -> int:
        """Get severity level (0-5)."""
        severity_map = {
            CollectionStatus.NONE: 0,
            CollectionStatus.SOFT_REMINDER: 1,
            CollectionStatus.FORMAL_NOTICE: 2,
            CollectionStatus.COLLECTION_AGENCY: 3,
            CollectionStatus.LEGAL_ACTION: 4,
            CollectionStatus.WRITTEN_OFF: 5,
        }
        return severity_map.get(self, 0)


class RiskLevel(str, Enum):
    """Credit risk level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

    def get_interest_adjustment(self) -> Decimal:
        """Get interest rate adjustment based on risk."""
        adjustments = {
            RiskLevel.LOW: Decimal("0"),
            RiskLevel.MEDIUM: Decimal("0.02"),
            RiskLevel.HIGH: Decimal("0.05"),
            RiskLevel.VERY_HIGH: Decimal("0.10"),
        }
        return adjustments.get(self, Decimal("0"))


@dataclass(frozen=True)
class CreditLimit:
    """Value object representing a credit limit."""

    amount: Decimal
    currency: str = "ARS"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Credit limit cannot be negative")

    def increase(self, amount: Decimal) -> "CreditLimit":
        """Increase credit limit."""
        return CreditLimit(amount=self.amount + amount, currency=self.currency)

    def decrease(self, amount: Decimal) -> "CreditLimit":
        """Decrease credit limit."""
        new_amount = self.amount - amount
        if new_amount < 0:
            raise ValueError("Credit limit cannot be negative")
        return CreditLimit(amount=new_amount, currency=self.currency)

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:,.2f}"


@dataclass(frozen=True)
class InterestRate:
    """Value object representing an interest rate."""

    annual_rate: Decimal  # As decimal, e.g., 0.24 for 24%

    def __post_init__(self):
        if self.annual_rate < 0:
            raise ValueError("Interest rate cannot be negative")
        if self.annual_rate > 1:
            raise ValueError("Interest rate should be expressed as decimal (e.g., 0.24 for 24%)")

    @property
    def monthly_rate(self) -> Decimal:
        """Get monthly interest rate."""
        return self.annual_rate / Decimal("12")

    @property
    def daily_rate(self) -> Decimal:
        """Get daily interest rate."""
        return self.annual_rate / Decimal("365")

    def calculate_interest(self, principal: Decimal, days: int) -> Decimal:
        """Calculate interest for a number of days."""
        return principal * self.daily_rate * days

    def as_percentage(self) -> str:
        """Get rate as percentage string."""
        return f"{self.annual_rate * 100:.2f}%"

    def __str__(self) -> str:
        return self.as_percentage()
