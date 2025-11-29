"""
Credit Score Calculator.

Single Responsibility: Calculate credit score components.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from app.domains.credit.domain.entities.credit_account import CreditAccount
from app.domains.credit.domain.value_objects.account_status import RiskLevel

from .schemas import (
    ACCOUNT_AGE_WEIGHT,
    CREDIT_MIX_WEIGHT,
    NEW_CREDIT_WEIGHT,
    PAYMENT_HISTORY_WEIGHT,
    UTILIZATION_WEIGHT,
    CreditScoreResult,
)


class CreditScoreCalculator:
    """Calculates credit scores based on account data."""

    def calculate(
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
        factors = []
        total_score = Decimal("0")

        # 1. Payment History (35%)
        payment_score = self._calculate_payment_history_score(
            account, payment_history or []
        )
        total_score += payment_score * PAYMENT_HISTORY_WEIGHT
        factors.append(
            {
                "factor": "Payment History",
                "weight": float(PAYMENT_HISTORY_WEIGHT * 100),
                "score": float(payment_score),
                "impact": "positive" if payment_score >= 70 else "negative",
            }
        )

        # 2. Credit Utilization (30%)
        utilization_score = self._calculate_utilization_score(account)
        total_score += utilization_score * UTILIZATION_WEIGHT
        factors.append(
            {
                "factor": "Credit Utilization",
                "weight": float(UTILIZATION_WEIGHT * 100),
                "score": float(utilization_score),
                "impact": "positive" if utilization_score >= 70 else "negative",
            }
        )

        # 3. Account Age (15%)
        age_score = self._calculate_account_age_score(account)
        total_score += age_score * ACCOUNT_AGE_WEIGHT
        factors.append(
            {
                "factor": "Account Age",
                "weight": float(ACCOUNT_AGE_WEIGHT * 100),
                "score": float(age_score),
                "impact": "positive" if age_score >= 70 else "neutral",
            }
        )

        # 4. Credit Mix (10%)
        mix_score = self._calculate_credit_mix_score(other_accounts_count)
        total_score += mix_score * CREDIT_MIX_WEIGHT
        factors.append(
            {
                "factor": "Credit Mix",
                "weight": float(CREDIT_MIX_WEIGHT * 100),
                "score": float(mix_score),
                "impact": "neutral",
            }
        )

        # 5. New Credit (10%)
        new_credit_score = self._calculate_new_credit_score(account)
        total_score += new_credit_score * NEW_CREDIT_WEIGHT
        factors.append(
            {
                "factor": "New Credit",
                "weight": float(NEW_CREDIT_WEIGHT * 100),
                "score": float(new_credit_score),
                "impact": "neutral",
            }
        )

        # Convert to 300-850 scale
        final_score = int(300 + (total_score / 100) * 550)
        final_score = max(300, min(850, final_score))

        # Determine risk level
        risk_level = self._score_to_risk_level(final_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(account, final_score)

        # Check eligibility for limit increase
        eligible, increase_amount = self._check_limit_increase_eligibility(
            account, final_score
        )

        return CreditScoreResult(
            score=final_score,
            risk_level=risk_level,
            factors=factors,
            recommendations=recommendations,
            eligible_for_increase=eligible,
            recommended_limit_increase=increase_amount,
        )

    def _calculate_payment_history_score(
        self,
        account: CreditAccount,
        payment_history: list[dict[str, Any]],
    ) -> Decimal:
        """Calculate score based on payment history."""
        if not payment_history and account.total_payments_made == 0:
            return Decimal("50")  # No history

        base_score = Decimal("100")

        # Deduct for late payments
        base_score -= Decimal(str(account.consecutive_late_payments * 15))

        # Bonus for on-time payments
        base_score += min(
            Decimal(str(account.consecutive_on_time_payments * 2)), Decimal("20")
        )

        # Deduct for days overdue
        if account.days_overdue > 0:
            base_score -= min(Decimal(str(account.days_overdue)), Decimal("50"))

        return max(Decimal("0"), min(Decimal("100"), base_score))

    def _calculate_utilization_score(self, account: CreditAccount) -> Decimal:
        """Calculate score based on credit utilization."""
        utilization = account.utilization_ratio

        if utilization <= 10:
            return Decimal("100")
        elif utilization <= 30:
            return Decimal("90")
        elif utilization <= 50:
            return Decimal("70")
        elif utilization <= 75:
            return Decimal("50")
        elif utilization <= 90:
            return Decimal("30")
        else:
            return Decimal("10")

    def _calculate_account_age_score(self, account: CreditAccount) -> Decimal:
        """Calculate score based on account age."""
        if not account.activated_at:
            return Decimal("30")

        days_active = (date.today() - account.activated_at.date()).days
        months_active = days_active / 30

        if months_active >= 60:  # 5+ years
            return Decimal("100")
        elif months_active >= 36:  # 3+ years
            return Decimal("85")
        elif months_active >= 24:  # 2+ years
            return Decimal("70")
        elif months_active >= 12:  # 1+ year
            return Decimal("55")
        elif months_active >= 6:
            return Decimal("40")
        else:
            return Decimal("25")

    def _calculate_credit_mix_score(self, other_accounts_count: int) -> Decimal:
        """Calculate score based on credit mix."""
        if other_accounts_count >= 4:
            return Decimal("100")
        elif other_accounts_count >= 2:
            return Decimal("75")
        elif other_accounts_count >= 1:
            return Decimal("50")
        else:
            return Decimal("30")

    def _calculate_new_credit_score(self, account: CreditAccount) -> Decimal:
        """Calculate score based on new credit activity."""
        if account.activated_at:
            days_active = (date.today() - account.activated_at.date()).days
            if days_active < 180:
                return Decimal("60")

        return Decimal("80")

    def _score_to_risk_level(self, score: int) -> RiskLevel:
        """Convert credit score to risk level."""
        if score >= 750:
            return RiskLevel.LOW
        elif score >= 650:
            return RiskLevel.MEDIUM
        elif score >= 550:
            return RiskLevel.HIGH
        else:
            return RiskLevel.VERY_HIGH

    def _generate_recommendations(
        self,
        account: CreditAccount,
        score: int,
    ) -> list[str]:
        """Generate recommendations to improve credit score."""
        recommendations = []

        if account.utilization_ratio > 30:
            recommendations.append(
                "Reduce credit utilization below 30% to improve your score"
            )

        if account.consecutive_late_payments > 0:
            recommendations.append(
                "Make payments on time to build positive payment history"
            )

        if account.days_overdue > 0:
            recommendations.append(
                "Pay overdue balance immediately to prevent further damage"
            )

        if score < 650:
            recommendations.append(
                "Consider paying more than the minimum payment each month"
            )
        elif score < 750:
            recommendations.append(
                "Continue good payment habits to reach excellent credit"
            )

        if account.can_request_limit_increase():
            recommendations.append("You may be eligible for a credit limit increase")

        return recommendations

    def _check_limit_increase_eligibility(
        self,
        account: CreditAccount,
        score: int,
    ) -> tuple[bool, Decimal | None]:
        """Check eligibility for credit limit increase."""
        if not account.can_request_limit_increase():
            return False, None

        if score < 650:
            return False, None

        if score >= 750:
            increase_percent = Decimal("0.30")
        elif score >= 700:
            increase_percent = Decimal("0.20")
        else:
            increase_percent = Decimal("0.10")

        increase_amount = account.credit_limit.amount * increase_percent
        return True, increase_amount
