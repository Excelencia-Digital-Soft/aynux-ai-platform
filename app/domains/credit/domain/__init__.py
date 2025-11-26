"""
Credit Domain Layer

This module contains the core business logic for the Credit bounded context,
following Domain-Driven Design (DDD) principles.

Components:
- Entities: CreditAccount, Payment (Aggregate Roots with business logic)
- Value Objects: AccountStatus, PaymentStatus, CreditLimit, InterestRate
- Domain Services: CreditScoringService (risk assessment and scoring)
"""

from app.domains.credit.domain.entities import CreditAccount, Payment
from app.domains.credit.domain.services import (
    CreditScoreResult,
    CreditScoringService,
    RiskAssessmentResult,
)
from app.domains.credit.domain.value_objects import (
    AccountStatus,
    CollectionStatus,
    CreditLimit,
    InterestRate,
    PaymentMethod,
    PaymentStatus,
    PaymentType,
    RiskLevel,
)

__all__ = [
    # Entities
    "CreditAccount",
    "Payment",
    # Value Objects
    "AccountStatus",
    "PaymentStatus",
    "PaymentType",
    "PaymentMethod",
    "CollectionStatus",
    "RiskLevel",
    "CreditLimit",
    "InterestRate",
    # Services
    "CreditScoringService",
    "CreditScoreResult",
    "RiskAssessmentResult",
]
