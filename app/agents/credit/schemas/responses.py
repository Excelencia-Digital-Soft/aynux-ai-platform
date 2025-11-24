"""
Credit Agent Response Models
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreditBalanceResponse(BaseModel):
    """Credit balance response"""

    account_id: str
    credit_limit: Decimal
    used_credit: Decimal
    available_credit: Decimal
    next_payment_date: Optional[date] = None
    next_payment_amount: Optional[Decimal] = None
    interest_rate: Decimal
    status: str
    last_update: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CreditApplicationResponse(BaseModel):
    """Credit application response"""

    application_id: str
    status: str  # pending, approved, rejected, under_review
    requested_amount: Decimal
    approved_amount: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    term_months: Optional[int] = None
    risk_score: Optional[float] = None
    decision_reason: Optional[str] = None
    required_documents: Optional[List[str]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaymentResponse(BaseModel):
    """Payment processing response"""

    payment_id: str
    account_id: str
    amount: Decimal
    payment_type: str  # regular, advance, partial, full
    status: str  # success, pending, failed
    transaction_date: datetime
    remaining_balance: Decimal
    next_payment_date: Optional[date] = None
    receipt_url: Optional[str] = None


class StatementResponse(BaseModel):
    """Account statement response"""

    account_id: str
    statement_period: str
    opening_balance: Decimal
    closing_balance: Decimal
    total_charges: Decimal
    total_payments: Decimal
    interest_charged: Decimal
    transactions: List[Dict[str, Any]]
    minimum_payment: Decimal
    due_date: date
    pdf_url: Optional[str] = None


class RiskAssessmentResponse(BaseModel):
    """Risk assessment response"""

    assessment_id: str
    account_id: str
    risk_score: float
    risk_category: str  # low, medium, high, very_high
    credit_recommendation: str
    factors: List[Dict[str, Any]]
    suggested_limit: Decimal
    suggested_interest_rate: Decimal
    assessment_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
