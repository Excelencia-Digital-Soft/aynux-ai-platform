"""
Risk Assessment Agent - Evaluates credit risk and provides recommendations
"""

import uuid
from decimal import Decimal
from typing import Any, Dict, List

from app.agents.credit.base_credit_agent import BaseCreditAgent
from app.agents.credit.schemas import CreditState, RiskAssessmentResponse, UserRole


class RiskAssessmentAgent(BaseCreditAgent):
    """Agent for credit risk assessment"""

    def __init__(self):
        super().__init__("risk_assessment")

    async def _process_internal(self, state: CreditState) -> Dict[str, Any]:
        """Process risk assessment request"""
        user_message = self._get_last_user_message(state)
        user_role = UserRole(state.get("user_role", UserRole.CUSTOMER))

        # Only analysts and above can perform risk assessments
        if user_role not in [UserRole.CREDIT_ANALYST, UserRole.MANAGER, UserRole.ADMIN]:
            return {"message": "No tienes permisos para realizar evaluaciones de riesgo.", "data": None}

        # Extract assessment target
        target = await self._extract_assessment_target(user_message, state)

        try:
            # Perform risk assessment
            assessment = await self._perform_risk_assessment(target)
            response = RiskAssessmentResponse(**assessment)

            message = self._format_assessment_message(response)

            return {"message": message, "data": response.model_dump(), "risk_score": response.risk_score}

        except Exception as e:
            self.logger.error(f"Error in risk assessment: {str(e)}")
            return {"message": "Error al realizar la evaluación de riesgo.", "data": None}

    async def _extract_assessment_target(self, _message: str, state: CreditState) -> Dict[str, Any]:
        """Extract assessment target from message"""
        # TODO: Implement NLP extraction using message
        return {
            "account_id": state.get("credit_account_id", "default_account"),
            "assessment_type": "credit_review",
            "requested_amount": Decimal("50000.00"),
        }

    async def _perform_risk_assessment(self, target: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive risk assessment"""
        assessment_id = str(uuid.uuid4())

        # Collect risk factors
        factors = await self._collect_risk_factors(target["account_id"])

        # Calculate risk score
        risk_score = self._calculate_comprehensive_risk_score(factors)

        # Determine risk category
        risk_category = self._categorize_risk(risk_score)

        # Generate recommendations
        recommendation = self._generate_credit_recommendation(risk_score, factors, target)

        # Calculate suggested parameters
        suggested_limit = self._calculate_suggested_limit(risk_score, factors, target)
        suggested_rate = self._calculate_suggested_interest_rate(risk_score, risk_category)

        return {
            "assessment_id": assessment_id,
            "account_id": target["account_id"],
            "risk_score": risk_score,
            "risk_category": risk_category,
            "credit_recommendation": recommendation,
            "factors": factors,
            "suggested_limit": suggested_limit,
            "suggested_interest_rate": suggested_rate,
        }

    async def _collect_risk_factors(self, _account_id: str) -> List[Dict[str, Any]]:
        """Collect and analyze risk factors"""
        # TODO: Implement actual data collection using account_id
        return [
            {
                "factor": "payment_history",
                "score": 0.85,
                "weight": 0.35,
                "description": "Historial de pagos excelente",
                "impact": "positive",
            },
            {
                "factor": "credit_utilization",
                "score": 0.70,
                "weight": 0.25,
                "description": "Utilización de crédito moderada (30%)",
                "impact": "positive",
            },
            {
                "factor": "income_stability",
                "score": 0.75,
                "weight": 0.20,
                "description": "Ingresos estables por 2+ años",
                "impact": "positive",
            },
            {
                "factor": "debt_to_income",
                "score": 0.60,
                "weight": 0.15,
                "description": "Relación deuda/ingreso aceptable",
                "impact": "neutral",
            },
            {
                "factor": "credit_history_length",
                "score": 0.50,
                "weight": 0.05,
                "description": "Historial crediticio de 1 año",
                "impact": "neutral",
            },
        ]

    def _calculate_comprehensive_risk_score(self, factors: List[Dict[str, Any]]) -> float:
        """Calculate weighted risk score"""
        total_score = 0.0
        total_weight = 0.0

        for factor in factors:
            total_score += factor["score"] * factor["weight"]
            total_weight += factor["weight"]

        if total_weight > 0:
            return round(total_score / total_weight, 3)
        return 0.5

    def _categorize_risk(self, risk_score: float) -> str:
        """Categorize risk based on score"""
        if risk_score >= 0.8:
            return "low"
        elif risk_score >= 0.6:
            return "medium"
        elif risk_score >= 0.4:
            return "high"
        else:
            return "very_high"

    def _generate_credit_recommendation(
        self, risk_score: float, _factors: List[Dict[str, Any]], _target: Dict[str, Any]
    ) -> str:
        """Generate credit recommendation based on assessment"""
        # TODO: Use factors and target in recommendation logic
        if risk_score >= 0.8:
            return "Aprobar con condiciones preferenciales"
        elif risk_score >= 0.6:
            return "Aprobar con condiciones estándar"
        elif risk_score >= 0.4:
            return "Aprobar con garantías adicionales o codeudor"
        else:
            return "Rechazar o solicitar mayor documentación"

    def _calculate_suggested_limit(
        self, risk_score: float, _factors: List[Dict[str, Any]], target: Dict[str, Any]
    ) -> Decimal:
        """Calculate suggested credit limit"""
        # TODO: Use factors in credit limit calculation
        base_limit = target.get("requested_amount", Decimal("50000.00"))

        if risk_score >= 0.8:
            return base_limit * Decimal("1.2")
        elif risk_score >= 0.6:
            return base_limit
        elif risk_score >= 0.4:
            return base_limit * Decimal("0.7")
        else:
            return base_limit * Decimal("0.5")

    def _calculate_suggested_interest_rate(self, _risk_score: float, risk_category: str) -> Decimal:
        """Calculate suggested interest rate based on risk"""
        # TODO: Use risk_score for fine-grained rate calculation
        rates = {
            "low": Decimal("12.5"),
            "medium": Decimal("18.5"),
            "high": Decimal("24.5"),
            "very_high": Decimal("29.9"),
        }
        return rates.get(risk_category, Decimal("18.5"))

    def _format_assessment_message(self, assessment: RiskAssessmentResponse) -> str:
        """Format risk assessment message"""
        # Risk category icons
        category_icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "very_high": "🔴"}

        icon = category_icons.get(assessment.risk_category, "⚪")

        message = f"""📊 **Evaluación de Riesgo Crediticio**

🆔 **ID de Evaluación:** {assessment.assessment_id[:8]}
📅 **Fecha:** {assessment.assessment_date.strftime("%d/%m/%Y %H:%M")}

🎯 **Score de Riesgo:** {assessment.risk_score:.1%}
{icon} **Categoría:** {self._translate_risk_category(assessment.risk_category)}

📋 **Factores de Riesgo Analizados:**"""

        # Add risk factors
        for factor in assessment.factors:
            impact_icon = "✅" if factor["impact"] == "positive" else "⚠️" if factor["impact"] == "neutral" else "❌"
            message += f"\n{impact_icon} **{self._translate_factor(factor['factor'])}**"
            message += f"\n   • Score: {factor['score']:.1%} (Peso: {factor['weight']:.0%})"
            message += f"\n   • {factor['description']}\n"

        message += f"""
💡 **Recomendación:** {assessment.credit_recommendation}

💰 **Parámetros Sugeridos:**
• **Límite de Crédito:** ${assessment.suggested_limit:,.2f}
• **Tasa de Interés:** {assessment.suggested_interest_rate}% anual

📊 **Acciones Recomendadas:**"""

        # Add recommended actions based on risk
        if assessment.risk_category == "low":
            message += """
✅ Aprobar inmediatamente
✅ Ofrecer productos adicionales
✅ Considerar aumento de límite automático"""
        elif assessment.risk_category == "medium":
            message += """
✅ Aprobar con monitoreo regular
⚠️ Revisar en 6 meses
📊 Mantener límite actual"""
        elif assessment.risk_category == "high":
            message += """
⚠️ Solicitar garantías adicionales
⚠️ Requerir codeudor
📊 Reducir límite gradualmente"""
        else:
            message += """
❌ Revisar documentación adicional
❌ Considerar restructuración
🔴 Activar protocolo de cobranza preventiva"""

        return message

    def _translate_risk_category(self, category: str) -> str:
        """Translate risk category to Spanish"""
        translations = {
            "low": "Riesgo Bajo",
            "medium": "Riesgo Medio",
            "high": "Riesgo Alto",
            "very_high": "Riesgo Muy Alto",
        }
        return translations.get(category, category)

    def _translate_factor(self, factor: str) -> str:
        """Translate risk factor to Spanish"""
        translations = {
            "payment_history": "Historial de Pagos",
            "credit_utilization": "Utilización de Crédito",
            "income_stability": "Estabilidad de Ingresos",
            "debt_to_income": "Relación Deuda/Ingreso",
            "credit_history_length": "Antigüedad Crediticia",
        }
        return translations.get(factor, factor)
