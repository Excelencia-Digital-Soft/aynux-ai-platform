"""
Credit Scoring Service.

Single Responsibility: Orchestrate credit scoring workflow using composition.
"""

from decimal import Decimal
from typing import Any

from app.domains.credit.domain.entities.credit_account import CreditAccount

from .limit_recommender import CreditLimitRecommender
from .risk_assessor import RiskAssessor
from .schemas import CreditScoreResult, RiskAssessmentResult
from .score_calculator import CreditScoreCalculator


class CreditScoringService:
    """
    Domain service for credit scoring and risk assessment.

    Uses composition:
    - CreditScoreCalculator for score calculation
    - RiskAssessor for risk assessment
    - CreditLimitRecommender for limit recommendations
    """

    def __init__(self):
        self._score_calculator = CreditScoreCalculator()
        self._risk_assessor = RiskAssessor()
        self._limit_recommender = CreditLimitRecommender(self._score_calculator)

    def calculate_credit_score(
        self,
        account: CreditAccount,
        payment_history: list[dict[str, Any]] | None = None,
        other_accounts_count: int = 0,
    ) -> CreditScoreResult:
        """
        Calculate credit score for an account.

        Args:
            account: Credit account to score
            payment_history: List of payment records
            other_accounts_count: Number of other credit accounts

        Returns:
            Credit score result
        """
        return self._score_calculator.calculate(
            account, payment_history, other_accounts_count
        )

    def assess_risk(
        self,
        account: CreditAccount,
        market_conditions: dict[str, Any] | None = None,
    ) -> RiskAssessmentResult:
        """
        Assess risk level for an account.

        Args:
            account: Account to assess
            market_conditions: Optional market condition data

        Returns:
            Risk assessment result
        """
        return self._risk_assessor.assess(account, market_conditions)

    def recommend_credit_limit(
        self,
        account: CreditAccount,
        income: Decimal | None = None,
        debt_to_income: Decimal | None = None,
    ) -> dict[str, Any]:
        """
        Recommend credit limit based on account performance.

        Args:
            account: Credit account
            income: Monthly income (if available)
            debt_to_income: Debt-to-income ratio (if available)

        Returns:
            Recommendation details
        """
        return self._limit_recommender.recommend(account, income, debt_to_income)
