"""
Credit Scoring Service - Backwards compatibility module.

This module re-exports from the refactored scoring package.
All new code should import directly from app.domains.credit.domain.services.scoring
"""

from app.domains.credit.domain.services.scoring import (
    CreditScoreResult,
    CreditScoringService,
    RiskAssessmentResult,
)

__all__ = [
    "CreditScoringService",
    "CreditScoreResult",
    "RiskAssessmentResult",
]
