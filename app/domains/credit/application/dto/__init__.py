"""
Credit Application DTOs

Data Transfer Objects for the Credit domain.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


# ==================== Balance DTOs ====================


@dataclass
class GetBalanceRequest:
    """Request to get credit balance"""

    account_id: str
    customer_id: str | None = None


@dataclass
class GetBalanceResponse:
    """Response with credit balance"""

    account_id: str
    current_balance: Decimal
    available_credit: Decimal
    credit_limit: Decimal
    status: str
    last_payment_date: datetime | None
    next_payment_due: datetime | None
    minimum_payment: Decimal | None


# ==================== Payment DTOs ====================


@dataclass
class PaymentDTO:
    """Payment data transfer object"""

    id: str
    account_id: str
    amount: Decimal
    payment_date: datetime
    payment_method: str
    reference_number: str
    status: str


@dataclass
class ProcessPaymentRequest:
    """Request to process a payment"""

    account_id: str
    amount: Decimal
    payment_method: str
    reference_number: str | None = None
    notes: str = ""


@dataclass
class ProcessPaymentResponse:
    """Response after processing payment"""

    payment: PaymentDTO
    success: bool
    message: str
    new_balance: Decimal


@dataclass
class GetPaymentHistoryRequest:
    """Request for payment history"""

    account_id: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int = 20


@dataclass
class GetPaymentHistoryResponse:
    """Response with payment history"""

    payments: list[PaymentDTO]
    total_count: int
    total_paid: Decimal


# ==================== Schedule DTOs ====================


@dataclass
class ScheduleItemDTO:
    """Payment schedule item"""

    due_date: datetime
    amount_due: Decimal
    principal: Decimal
    interest: Decimal
    status: str
    payment_number: int


@dataclass
class GetPaymentScheduleRequest:
    """Request for payment schedule"""

    account_id: str
    include_paid: bool = False


@dataclass
class GetPaymentScheduleResponse:
    """Response with payment schedule"""

    account_id: str
    schedule: list[ScheduleItemDTO]
    total_remaining: Decimal
    next_payment: ScheduleItemDTO | None
    payments_remaining: int


# ==================== Account DTOs ====================


@dataclass
class CreditAccountDTO:
    """Credit account data transfer object"""

    id: str
    customer_id: str
    account_number: str
    credit_limit: Decimal
    current_balance: Decimal
    available_credit: Decimal
    interest_rate: Decimal
    status: str
    opened_date: datetime
    last_activity_date: datetime | None


@dataclass
class GetAccountDetailsRequest:
    """Request for account details"""

    account_id: str


@dataclass
class GetAccountDetailsResponse:
    """Response with account details"""

    account: CreditAccountDTO | None
    found: bool


__all__ = [
    # Balance DTOs
    "GetBalanceRequest",
    "GetBalanceResponse",
    # Payment DTOs
    "PaymentDTO",
    "ProcessPaymentRequest",
    "ProcessPaymentResponse",
    "GetPaymentHistoryRequest",
    "GetPaymentHistoryResponse",
    # Schedule DTOs
    "ScheduleItemDTO",
    "GetPaymentScheduleRequest",
    "GetPaymentScheduleResponse",
    # Account DTOs
    "CreditAccountDTO",
    "GetAccountDetailsRequest",
    "GetAccountDetailsResponse",
]
