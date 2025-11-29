"""
Credit Scoring Schemas.

Single Responsibility: Data models for credit scoring results.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domains.credit.domain.value_objects.account_status import RiskLevel


@dataclass
class CreditScoreResult:
    """Result of credit score calculation."""

    score: int  # 300-850 range
    risk_level: RiskLevel
    factors: list[dict[str, Any]]
    recommendations: list[str]
    eligible_for_increase: bool
    recommended_limit_increase: Decimal | None = None


@dataclass
class RiskAssessmentResult:
    """Result of risk assessment."""

    risk_level: RiskLevel
    risk_score: Decimal  # 0-100 scale
    factors: list[dict[str, Any]]
    recommended_actions: list[str]
    requires_review: bool = False


# Score weights
PAYMENT_HISTORY_WEIGHT = Decimal("0.35")
UTILIZATION_WEIGHT = Decimal("0.30")
ACCOUNT_AGE_WEIGHT = Decimal("0.15")
CREDIT_MIX_WEIGHT = Decimal("0.10")
NEW_CREDIT_WEIGHT = Decimal("0.10")
