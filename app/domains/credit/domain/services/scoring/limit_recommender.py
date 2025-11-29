"""
Credit Limit Recommender.

Single Responsibility: Recommend credit limit changes based on account performance.
"""

from decimal import Decimal
from typing import Any

from app.domains.credit.domain.entities.credit_account import CreditAccount

from .score_calculator import CreditScoreCalculator


class CreditLimitRecommender:
    """Recommends credit limit changes."""

    def __init__(self, score_calculator: CreditScoreCalculator | None = None):
        self._score_calculator = score_calculator or CreditScoreCalculator()

    def recommend(
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
        base_limit = account.credit_limit.amount

        # Score-based multiplier
        score_result = self._score_calculator.calculate(account)
        if score_result.score >= 750:
            multiplier = Decimal("1.50")
        elif score_result.score >= 700:
            multiplier = Decimal("1.25")
        elif score_result.score >= 650:
            multiplier = Decimal("1.10")
        elif score_result.score >= 600:
            multiplier = Decimal("1.00")
        else:
            multiplier = Decimal("0.90")

        # Performance adjustment
        if account.consecutive_on_time_payments >= 12:
            multiplier += Decimal("0.10")
        elif account.consecutive_late_payments >= 3:
            multiplier -= Decimal("0.20")

        # Utilization adjustment
        if account.utilization_ratio < 30:
            multiplier += Decimal("0.05")
        elif account.utilization_ratio > 80:
            multiplier -= Decimal("0.10")

        recommended_limit = base_limit * multiplier

        # Cap based on income if available
        if income:
            max_limit = income * 3
            recommended_limit = min(recommended_limit, max_limit)

        return {
            "current_limit": float(base_limit),
            "recommended_limit": float(recommended_limit),
            "change_amount": float(recommended_limit - base_limit),
            "change_percentage": float(
                (recommended_limit - base_limit) / base_limit * 100
            ),
            "credit_score": score_result.score,
            "risk_level": score_result.risk_level.value,
            "eligible": (
                account.can_request_limit_increase()
                and recommended_limit > base_limit
            ),
        }
