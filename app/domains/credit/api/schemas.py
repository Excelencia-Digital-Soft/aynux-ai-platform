"""
Credit API Schemas

Pydantic schemas for API request/response validation.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CreditAccountResponse(BaseModel):
    """Credit account response schema."""

    id: int
    customer_id: int
    account_number: str
    credit_limit: Decimal
    current_balance: Decimal
    available_credit: Decimal
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentRequest(BaseModel):
    """Payment request schema."""

    account_id: int
    amount: Decimal = Field(..., gt=0)
    payment_method: str
    reference: str | None = None


class PaymentResponse(BaseModel):
    """Payment response schema."""

    id: str
    account_id: int
    amount: Decimal
    payment_date: datetime
    status: str
    reference: str | None = None

    class Config:
        from_attributes = True


class PaymentScheduleResponse(BaseModel):
    """Payment schedule item response schema."""

    installment_number: int
    due_date: date
    amount: Decimal
    principal: Decimal
    interest: Decimal
    status: str


class AccountBalanceResponse(BaseModel):
    """Account balance response schema."""

    account_id: int
    current_balance: Decimal
    credit_limit: Decimal
    available_credit: Decimal
    minimum_payment: Decimal
    next_payment_date: date | None = None


class CollectionStatusResponse(BaseModel):
    """Collection status response schema."""

    account_id: int
    days_past_due: int
    overdue_amount: Decimal
    collection_status: str
    last_contact_date: datetime | None = None


__all__ = [
    "CreditAccountResponse",
    "PaymentRequest",
    "PaymentResponse",
    "PaymentScheduleResponse",
    "AccountBalanceResponse",
    "CollectionStatusResponse",
]
