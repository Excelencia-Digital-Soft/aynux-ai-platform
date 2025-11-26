"""
Credit Scoring Service

Domain service for credit risk assessment and scoring.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from ..entities.credit_account import CreditAccount
from ..value_objects.account_status import RiskLevel


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


class CreditScoringService:
    """
    Domain service for credit scoring and risk assessment.

    Handles:
    - Credit score calculation
    - Risk assessment
    - Credit limit recommendations
    - Payment behavior analysis

    Example:
        ```python
        service = CreditScoringService()
        score = service.calculate_credit_score(account, payment_history)
        risk = service.assess_risk(account)
        ```
    """

    # Score weights
    PAYMENT_HISTORY_WEIGHT = Decimal("0.35")
    UTILIZATION_WEIGHT = Decimal("0.30")
    ACCOUNT_AGE_WEIGHT = Decimal("0.15")
    CREDIT_MIX_WEIGHT = Decimal("0.10")
    NEW_CREDIT_WEIGHT = Decimal("0.10")

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
        factors = []
        total_score = Decimal("0")

        # 1. Payment History (35%)
        payment_score = self._calculate_payment_history_score(account, payment_history or [])
        total_score += payment_score * self.PAYMENT_HISTORY_WEIGHT
        factors.append(
            {
                "factor": "Payment History",
                "weight": float(self.PAYMENT_HISTORY_WEIGHT * 100),
                "score": float(payment_score),
                "impact": "positive" if payment_score >= 70 else "negative",
            }
        )

        # 2. Credit Utilization (30%)
        utilization_score = self._calculate_utilization_score(account)
        total_score += utilization_score * self.UTILIZATION_WEIGHT
        factors.append(
            {
                "factor": "Credit Utilization",
                "weight": float(self.UTILIZATION_WEIGHT * 100),
                "score": float(utilization_score),
                "impact": "positive" if utilization_score >= 70 else "negative",
            }
        )

        # 3. Account Age (15%)
        age_score = self._calculate_account_age_score(account)
        total_score += age_score * self.ACCOUNT_AGE_WEIGHT
        factors.append(
            {
                "factor": "Account Age",
                "weight": float(self.ACCOUNT_AGE_WEIGHT * 100),
                "score": float(age_score),
                "impact": "positive" if age_score >= 70 else "neutral",
            }
        )

        # 4. Credit Mix (10%)
        mix_score = self._calculate_credit_mix_score(other_accounts_count)
        total_score += mix_score * self.CREDIT_MIX_WEIGHT
        factors.append(
            {
                "factor": "Credit Mix",
                "weight": float(self.CREDIT_MIX_WEIGHT * 100),
                "score": float(mix_score),
                "impact": "neutral",
            }
        )

        # 5. New Credit (10%)
        new_credit_score = self._calculate_new_credit_score(account)
        total_score += new_credit_score * self.NEW_CREDIT_WEIGHT
        factors.append(
            {
                "factor": "New Credit",
                "weight": float(self.NEW_CREDIT_WEIGHT * 100),
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
        recommendations = self._generate_recommendations(account, final_score, factors)

        # Check eligibility for limit increase
        eligible, increase_amount = self._check_limit_increase_eligibility(account, final_score)

        return CreditScoreResult(
            score=final_score,
            risk_level=risk_level,
            factors=factors,
            recommendations=recommendations,
            eligible_for_increase=eligible,
            recommended_limit_increase=increase_amount,
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
        factors = []
        total_risk = Decimal("0")

        # 1. Payment Behavior Risk
        payment_risk = self._assess_payment_risk(account)
        total_risk += payment_risk * Decimal("0.40")
        factors.append(
            {
                "factor": "Payment Behavior",
                "risk_contribution": float(payment_risk * Decimal("0.40")),
                "details": f"{account.consecutive_late_payments} late payments",
            }
        )

        # 2. Utilization Risk
        utilization_risk = self._assess_utilization_risk(account)
        total_risk += utilization_risk * Decimal("0.25")
        factors.append(
            {
                "factor": "Credit Utilization",
                "risk_contribution": float(utilization_risk * Decimal("0.25")),
                "details": f"{account.utilization_ratio:.1f}% utilization",
            }
        )

        # 3. Account Status Risk
        status_risk = self._assess_status_risk(account)
        total_risk += status_risk * Decimal("0.20")
        factors.append(
            {
                "factor": "Account Status",
                "risk_contribution": float(status_risk * Decimal("0.20")),
                "details": account.status.value,
            }
        )

        # 4. Collection Risk
        collection_risk = self._assess_collection_risk(account)
        total_risk += collection_risk * Decimal("0.15")
        factors.append(
            {
                "factor": "Collection Status",
                "risk_contribution": float(collection_risk * Decimal("0.15")),
                "details": account.collection_status.value,
            }
        )

        # Determine risk level
        risk_level = self._risk_score_to_level(total_risk)

        # Generate recommended actions
        actions = self._generate_risk_actions(account, risk_level, factors)

        # Determine if manual review needed
        requires_review = total_risk >= 70 or account.days_overdue >= 60

        return RiskAssessmentResult(
            risk_level=risk_level,
            risk_score=total_risk,
            factors=factors,
            recommended_actions=actions,
            requires_review=requires_review,
        )

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
        base_limit = account.credit_limit.amount

        # Score-based multiplier
        score_result = self.calculate_credit_score(account)
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
            "change_percentage": float((recommended_limit - base_limit) / base_limit * 100),
            "credit_score": score_result.score,
            "risk_level": score_result.risk_level.value,
            "eligible": account.can_request_limit_increase() and recommended_limit > base_limit,
        }

    # Private Helper Methods

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
        base_score += min(Decimal(str(account.consecutive_on_time_payments * 2)), Decimal("20"))

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
        # Accounts less than 6 months get lower score
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

    def _risk_score_to_level(self, risk_score: Decimal) -> RiskLevel:
        """Convert risk score to risk level."""
        if risk_score <= 25:
            return RiskLevel.LOW
        elif risk_score <= 50:
            return RiskLevel.MEDIUM
        elif risk_score <= 75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.VERY_HIGH

    def _assess_payment_risk(self, account: CreditAccount) -> Decimal:
        """Assess risk based on payment behavior."""
        risk = Decimal("0")

        if account.consecutive_late_payments >= 3:
            risk += Decimal("50")
        elif account.consecutive_late_payments >= 1:
            risk += Decimal("25")

        if account.days_overdue > 90:
            risk += Decimal("50")
        elif account.days_overdue > 60:
            risk += Decimal("35")
        elif account.days_overdue > 30:
            risk += Decimal("20")
        elif account.days_overdue > 0:
            risk += Decimal("10")

        return min(Decimal("100"), risk)

    def _assess_utilization_risk(self, account: CreditAccount) -> Decimal:
        """Assess risk based on utilization."""
        utilization = account.utilization_ratio

        if utilization >= 90:
            return Decimal("100")
        elif utilization >= 75:
            return Decimal("70")
        elif utilization >= 50:
            return Decimal("40")
        elif utilization >= 30:
            return Decimal("20")
        else:
            return Decimal("0")

    def _assess_status_risk(self, account: CreditAccount) -> Decimal:
        """Assess risk based on account status."""
        status_risk = {
            "active": Decimal("0"),
            "blocked": Decimal("50"),
            "overdue": Decimal("70"),
            "suspended": Decimal("60"),
            "defaulted": Decimal("100"),
            "closed": Decimal("30"),
            "pending_approval": Decimal("20"),
        }
        return status_risk.get(account.status.value, Decimal("50"))

    def _assess_collection_risk(self, account: CreditAccount) -> Decimal:
        """Assess risk based on collection status."""
        return Decimal(str(account.collection_status.get_severity() * 20))

    def _generate_recommendations(
        self,
        account: CreditAccount,
        score: int,
        factors: list[dict[str, Any]],
    ) -> list[str]:
        """Generate recommendations to improve credit score."""
        recommendations = []

        # Utilization recommendations
        if account.utilization_ratio > 30:
            recommendations.append("Reduce credit utilization below 30% to improve your score")

        # Payment recommendations
        if account.consecutive_late_payments > 0:
            recommendations.append("Make payments on time to build positive payment history")

        if account.days_overdue > 0:
            recommendations.append("Pay overdue balance immediately to prevent further damage")

        # General recommendations based on score
        if score < 650:
            recommendations.append("Consider paying more than the minimum payment each month")
        elif score < 750:
            recommendations.append("Continue good payment habits to reach excellent credit")

        # Limit increase recommendation
        if account.can_request_limit_increase():
            recommendations.append("You may be eligible for a credit limit increase")

        return recommendations

    def _generate_risk_actions(
        self,
        account: CreditAccount,
        risk_level: RiskLevel,
        factors: list[dict[str, Any]],
    ) -> list[str]:
        """Generate recommended actions based on risk assessment."""
        actions = []

        if risk_level == RiskLevel.LOW:
            actions.append("Continue monitoring - account in good standing")
        elif risk_level == RiskLevel.MEDIUM:
            actions.append("Review account monthly for early warning signs")
            if account.utilization_ratio > 50:
                actions.append("Consider proactive outreach about payment options")
        elif risk_level == RiskLevel.HIGH:
            actions.append("Weekly account monitoring required")
            actions.append("Contact customer for payment arrangement")
            if account.utilization_ratio > 80:
                actions.append("Consider temporary credit limit reduction")
        else:  # VERY_HIGH
            actions.append("Immediate escalation to collections team")
            actions.append("Block further credit usage")
            actions.append("Initiate formal collection process")

        return actions

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

        # Calculate increase amount based on score
        if score >= 750:
            increase_percent = Decimal("0.30")
        elif score >= 700:
            increase_percent = Decimal("0.20")
        else:
            increase_percent = Decimal("0.10")

        increase_amount = account.credit_limit.amount * increase_percent
        return True, increase_amount
