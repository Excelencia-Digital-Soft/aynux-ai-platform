"""
Risk Assessor.

Single Responsibility: Assess credit risk based on account data.
"""

from decimal import Decimal
from typing import Any

from app.domains.credit.domain.entities.credit_account import CreditAccount
from app.domains.credit.domain.value_objects.account_status import RiskLevel

from .schemas import RiskAssessmentResult


class RiskAssessor:
    """Assesses credit risk for accounts."""

    def assess(
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
        actions = self._generate_risk_actions(account, risk_level)

        # Determine if manual review needed
        requires_review = total_risk >= 70 or account.days_overdue >= 60

        return RiskAssessmentResult(
            risk_level=risk_level,
            risk_score=total_risk,
            factors=factors,
            recommended_actions=actions,
            requires_review=requires_review,
        )

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

    def _generate_risk_actions(
        self,
        account: CreditAccount,
        risk_level: RiskLevel,
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
