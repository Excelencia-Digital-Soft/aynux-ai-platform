"""
Database Models for Credit System
"""

from enum import Enum as PyEnum

from sqlalchemy import DECIMAL, JSON, Column, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.database import Base


class CreditStatus(str, PyEnum):
    """Credit account status"""

    ACTIVE = "active"
    BLOCKED = "blocked"
    OVERDUE = "overdue"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class ApplicationStatus(str, PyEnum):
    """Credit application status"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_REVIEW = "under_review"
    CANCELLED = "cancelled"


class PaymentStatus(str, PyEnum):
    """Payment status"""

    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    REVERSED = "reversed"


class RiskCategory(str, PyEnum):
    """Risk categories"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class CollectionStage(str, PyEnum):
    """Collection stages"""

    EARLY = "early"  # 1-30 days
    INTERMEDIATE = "intermediate"  # 31-60 days
    ADVANCED = "advanced"  # 60+ days
    LEGAL = "legal"  # Legal action


class CreditAccount(Base):
    """Credit account model"""

    __tablename__ = "credit_accounts"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    account_number = Column(String, unique=True, nullable=False)
    credit_limit = Column(DECIMAL(12, 2), nullable=False)
    used_credit = Column(DECIMAL(12, 2), default=0)
    available_credit = Column(DECIMAL(12, 2))
    interest_rate = Column(DECIMAL(5, 2), nullable=False)
    status = Column(Enum(CreditStatus), default=CreditStatus.ACTIVE)
    opening_date = Column(Date, default=func.current_date())
    last_payment_date = Column(Date)
    next_payment_date = Column(Date)
    minimum_payment = Column(DECIMAL(12, 2))
    total_debt = Column(DECIMAL(12, 2), default=0)
    days_overdue = Column(Integer, default=0)
    collection_stage = Column(Enum(CollectionStage))
    risk_score = Column(Float)
    risk_category = Column(Enum(RiskCategory))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="credit_accounts")
    applications = relationship("CreditApplication", back_populates="account")
    transactions = relationship("CreditTransaction", back_populates="account")
    payments = relationship("CreditPayment", back_populates="account")
    statements = relationship("CreditStatement", back_populates="account")

    # Indexes for performance
    __table_args__ = (
        Index("idx_credit_account_user", "user_id"),
        Index("idx_credit_account_status", "status"),
        Index("idx_credit_account_collection", "collection_stage"),
    )


class CreditApplication(Base):
    """Credit application model"""

    __tablename__ = "credit_applications"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("credit_accounts.id"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    application_number = Column(String, unique=True, nullable=False)
    requested_amount = Column(DECIMAL(12, 2), nullable=False)
    approved_amount = Column(DECIMAL(12, 2))
    term_months = Column(Integer)
    purpose = Column(String)
    monthly_income = Column(DECIMAL(12, 2))
    employment_status = Column(String)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.PENDING)
    risk_score = Column(Float)
    interest_rate = Column(DECIMAL(5, 2))
    decision_reason = Column(Text)
    required_documents = Column(JSON)
    submitted_documents = Column(JSON)
    reviewed_by = Column(String, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    account = relationship("CreditAccount", back_populates="applications")
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    # Indexes
    __table_args__ = (
        Index("idx_application_user", "user_id"),
        Index("idx_application_status", "status"),
        Index("idx_application_created", "created_at"),
    )


class CreditTransaction(Base):
    """Credit transaction model"""

    __tablename__ = "credit_transactions"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("credit_accounts.id"), nullable=False)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    description = Column(String, nullable=False)
    amount = Column(DECIMAL(12, 2), nullable=False)
    transaction_type = Column(String, nullable=False)  # charge, payment, interest, fee
    category = Column(String)
    merchant = Column(String)
    reference_number = Column(String)
    balance_after = Column(DECIMAL(12, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    account = relationship("CreditAccount", back_populates="transactions")

    # Indexes
    __table_args__ = (
        Index("idx_transaction_account", "account_id"),
        Index("idx_transaction_date", "transaction_date"),
        Index("idx_transaction_type", "transaction_type"),
    )


class CreditPayment(Base):
    """Credit payment model"""

    __tablename__ = "credit_payments"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("credit_accounts.id"), nullable=False)
    payment_number = Column(String, unique=True, nullable=False)
    amount = Column(DECIMAL(12, 2), nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False)
    payment_method = Column(String)  # card, transfer, cash, etc.
    payment_type = Column(String)  # regular, advance, partial, full
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    reference = Column(String)
    receipt_url = Column(String)
    processed_by = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    account = relationship("CreditAccount", back_populates="payments")

    # Indexes
    __table_args__ = (
        Index("idx_payment_account", "account_id"),
        Index("idx_payment_date", "payment_date"),
        Index("idx_payment_status", "status"),
    )


class CreditStatement(Base):
    """Credit statement model"""

    __tablename__ = "credit_statements"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("credit_accounts.id"), nullable=False)
    statement_date = Column(Date, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    opening_balance = Column(DECIMAL(12, 2))
    closing_balance = Column(DECIMAL(12, 2))
    total_charges = Column(DECIMAL(12, 2))
    total_payments = Column(DECIMAL(12, 2))
    interest_charged = Column(DECIMAL(12, 2))
    fees_charged = Column(DECIMAL(12, 2))
    minimum_payment = Column(DECIMAL(12, 2))
    due_date = Column(Date)
    pdf_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    account = relationship("CreditAccount", back_populates="statements")

    # Indexes
    __table_args__ = (
        Index("idx_statement_account", "account_id"),
        Index("idx_statement_date", "statement_date"),
    )


class RiskAssessment(Base):
    """Risk assessment model"""

    __tablename__ = "risk_assessments"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("credit_accounts.id"))
    application_id = Column(String, ForeignKey("credit_applications.id"))
    assessment_type = Column(String)  # initial, periodic, special
    risk_score = Column(Float, nullable=False)
    risk_category = Column(Enum(RiskCategory), nullable=False)
    factors = Column(JSON)  # Detailed risk factors
    credit_recommendation = Column(Text)
    suggested_limit = Column(DECIMAL(12, 2))
    suggested_interest_rate = Column(DECIMAL(5, 2))
    assessed_by = Column(String, ForeignKey("users.id"))
    assessment_date = Column(DateTime(timezone=True), server_default=func.now())
    valid_until = Column(Date)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_risk_account", "account_id"),
        Index("idx_risk_application", "application_id"),
        Index("idx_risk_date", "assessment_date"),
    )


class CollectionActivity(Base):
    """Collection activity tracking"""

    __tablename__ = "collection_activities"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("credit_accounts.id"), nullable=False)
    activity_type = Column(String, nullable=False)  # call, sms, email, letter, visit
    activity_date = Column(DateTime(timezone=True), nullable=False)
    outcome = Column(String)  # contacted, promise_to_pay, no_answer, refused
    promise_amount = Column(DECIMAL(12, 2))
    promise_date = Column(Date)
    notes = Column(Text)
    performed_by = Column(String, ForeignKey("users.id"))
    next_action = Column(String)
    next_action_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_collection_account", "account_id"),
        Index("idx_collection_date", "activity_date"),
        Index("idx_collection_outcome", "outcome"),
    )


class CreditProduct(Base):
    """Products that can be purchased on credit"""

    __tablename__ = "credit_products"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    account_id = Column(String, ForeignKey("credit_accounts.id"), nullable=False)
    purchase_date = Column(DateTime(timezone=True), nullable=False)
    amount = Column(DECIMAL(12, 2), nullable=False)
    installments = Column(Integer, default=1)
    installment_amount = Column(DECIMAL(12, 2))
    interest_applied = Column(DECIMAL(12, 2), default=0)
    status = Column(String)  # active, paid, cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_credit_product_account", "account_id"),
        Index("idx_credit_product_date", "purchase_date"),
    )

