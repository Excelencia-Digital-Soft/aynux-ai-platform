"""
Credit Domain SQLAlchemy Models

Database models for credit domain persistence.
Uses SQLAlchemy 2.0 style with Mapped[] type annotations for Pyright compatibility.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, List

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.setup import Base
from app.domains.credit.domain.value_objects.account_status import (
    AccountStatus,
    CollectionStatus,
    PaymentMethod,
    PaymentStatus,
    PaymentType,
    RiskLevel,
)


class CreditAccountModel(Base):
    """SQLAlchemy model for CreditAccount entity."""

    __tablename__ = "credit_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Account identifiers
    account_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Credit configuration
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=0.24)
    risk_level: Mapped[RiskLevel] = mapped_column(
        SQLEnum(RiskLevel),
        default=RiskLevel.LOW,
        nullable=False,
    )

    # Balances
    used_credit: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    pending_charges: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    accrued_interest: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)

    # Payment configuration
    payment_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    minimum_payment_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=0.05)
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    # Status
    status: Mapped[AccountStatus] = mapped_column(
        SQLEnum(AccountStatus),
        default=AccountStatus.PENDING_APPROVAL,
        nullable=False,
        index=True,
    )
    collection_status: Mapped[CollectionStatus] = mapped_column(
        SQLEnum(CollectionStatus),
        default=CollectionStatus.NONE,
        nullable=False,
    )

    # Dates
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_statement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Payment tracking
    consecutive_on_time_payments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_late_payments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_payments_made: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Collection info
    days_overdue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_collection_action: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payments: Mapped[List["PaymentModel"]] = relationship("PaymentModel", back_populates="account")
    schedule_items: Mapped[List["PaymentScheduleItemModel"]] = relationship(
        "PaymentScheduleItemModel", back_populates="account"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        credit_limit_val = float(self.credit_limit) if self.credit_limit is not None else 0.0
        used_credit_val = float(self.used_credit) if self.used_credit is not None else 0.0
        pending_charges_val = float(self.pending_charges) if self.pending_charges is not None else 0.0
        interest_rate_val = float(self.interest_rate) if self.interest_rate is not None else 0.0

        return {
            "id": self.id,
            "account_number": self.account_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "credit_limit": credit_limit_val,
            "used_credit": used_credit_val,
            "available_credit": credit_limit_val - used_credit_val - pending_charges_val,
            "interest_rate": interest_rate_val,
            "status": self.status.value if self.status is not None else None,
            "days_overdue": self.days_overdue,
            "next_payment_date": self.next_payment_date.isoformat() if self.next_payment_date is not None else None,
        }


class PaymentModel(Base):
    """SQLAlchemy model for Payment entity."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # References
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("credit_accounts.id"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Payment details
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    payment_type: Mapped[PaymentType] = mapped_column(
        SQLEnum(PaymentType),
        default=PaymentType.REGULAR,
        nullable=False,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(PaymentMethod),
        default=PaymentMethod.BANK_TRANSFER,
        nullable=False,
    )

    # Status
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Transaction details
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Payment breakdown
    interest_paid: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    charges_paid: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    principal_paid: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)

    # Timestamps
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Error handling
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    account: Mapped["CreditAccountModel"] = relationship("CreditAccountModel", back_populates="payments")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "reference_number": self.reference_number,
            "amount": float(self.amount) if self.amount is not None else 0,
            "payment_type": self.payment_type.value if self.payment_type is not None else None,
            "payment_method": self.payment_method.value if self.payment_method is not None else None,
            "status": self.status.value if self.status is not None else None,
            "initiated_at": self.initiated_at.isoformat() if self.initiated_at is not None else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at is not None else None,
        }


class PaymentScheduleItemModel(Base):
    """SQLAlchemy model for payment schedule items."""

    __tablename__ = "payment_schedule_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # References
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("credit_accounts.id"), nullable=False, index=True)

    # Schedule details
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    principal_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    interest_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    account: Mapped["CreditAccountModel"] = relationship("CreditAccountModel", back_populates="schedule_items")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "due_date": self.due_date.isoformat() if self.due_date is not None else None,
            "amount": float(self.amount) if self.amount is not None else 0,
            "principal_amount": float(self.principal_amount) if self.principal_amount is not None else 0,
            "interest_amount": float(self.interest_amount) if self.interest_amount is not None else 0,
            "status": self.status,
            "paid_date": self.paid_date.isoformat() if self.paid_date is not None else None,
            "paid_amount": float(self.paid_amount) if self.paid_amount is not None else None,
        }
