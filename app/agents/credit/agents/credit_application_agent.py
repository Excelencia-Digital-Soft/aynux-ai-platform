"""
Credit Application Agent - Handles new credit applications and approvals
"""

import uuid
from decimal import Decimal
from typing import Any, Dict

from app.agents.credit.base_credit_agent import BaseCreditAgent
from app.agents.credit.schemas import CreditApplicationResponse, CreditState, UserRole


class CreditApplicationAgent(BaseCreditAgent):
    """Agent for handling credit applications"""

    def __init__(self):
        super().__init__("credit_application")

    async def _process_internal(self, state: CreditState) -> Dict[str, Any]:
        """Process credit application"""
        user_message = self._get_last_user_message(state)
        user_id = state["user_id"]
        user_role = UserRole(state.get("user_role", UserRole.CUSTOMER))

        # Extract application details from message
        application_data = await self._extract_application_data(user_message, state)

        if user_role == UserRole.CUSTOMER:
            # Customer is applying for credit
            return await self._handle_customer_application(user_id, application_data)
        else:
            # Staff is reviewing/approving application
            return await self._handle_staff_review(state, application_data)

    async def _extract_application_data(self, message: str, state: CreditState) -> Dict[str, Any]:
        """Extract application details from user message"""
        # TODO: Use NLP to extract amount, term, purpose
        # For now, use simple extraction
        return {
            "requested_amount": Decimal("25000.00"),
            "term_months": 12,
            "purpose": "personal",
            "monthly_income": Decimal("15000.00"),
        }

    async def _handle_customer_application(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle customer credit application"""
        try:
            # Perform initial validation
            validation_result = await self._validate_application(data)

            if not validation_result["valid"]:
                return {
                    "message": f"❌ Tu solicitud no puede ser procesada:\n{validation_result['reason']}",
                    "data": None,
                }

            # Create application
            application_id = str(uuid.uuid4())

            # Perform risk assessment
            risk_score = await self._calculate_risk_score(user_id, data)

            # Determine initial decision
            decision = self._make_credit_decision(risk_score, data)

            application_response = CreditApplicationResponse(
                application_id=application_id,
                status=decision["status"],
                requested_amount=data["requested_amount"],
                approved_amount=decision.get("approved_amount"),
                interest_rate=decision.get("interest_rate"),
                term_months=data["term_months"],
                risk_score=risk_score,
                decision_reason=decision.get("reason"),
                required_documents=decision.get("required_documents", []),
            )

            message = self._format_application_message(application_response)

            return {"message": message, "data": application_response.model_dump(), "risk_score": risk_score}

        except Exception as e:
            self.logger.error(f"Error processing application: {str(e)}")
            return {"message": "Error al procesar tu solicitud. Por favor, intenta nuevamente.", "data": None}

    async def _handle_staff_review(self, state: CreditState, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle staff review of credit application"""
        # TODO: Implement staff review workflow
        return {"message": "Función de revisión de créditos en desarrollo.", "data": None}

    async def _validate_application(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate application data"""
        if data["requested_amount"] < 1000:
            return {"valid": False, "reason": "El monto mínimo es $1,000"}

        if data["requested_amount"] > 500000:
            return {"valid": False, "reason": "El monto máximo es $500,000"}

        if data["term_months"] < 3 or data["term_months"] > 60:
            return {"valid": False, "reason": "El plazo debe ser entre 3 y 60 meses"}

        return {"valid": True}

    async def _calculate_risk_score(self, user_id: str, data: Dict[str, Any]) -> float:
        """Calculate risk score for credit application"""
        # TODO: Implement actual risk scoring model
        # This is a simplified mock
        base_score = 0.7

        # Adjust based on amount
        if data["requested_amount"] > 100000:
            base_score -= 0.1

        # Adjust based on income ratio
        debt_to_income = float(data["requested_amount"]) / float(data["monthly_income"])
        if debt_to_income > 3:
            base_score -= 0.2

        return max(0.1, min(1.0, base_score))

    def _make_credit_decision(self, risk_score: float, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make credit decision based on risk score"""
        if risk_score >= 0.8:
            return {
                "status": "approved",
                "approved_amount": data["requested_amount"],
                "interest_rate": Decimal("12.5"),
                "reason": "Excelente perfil crediticio",
            }
        elif risk_score >= 0.6:
            return {
                "status": "approved",
                "approved_amount": data["requested_amount"] * Decimal("0.8"),
                "interest_rate": Decimal("18.5"),
                "reason": "Buen perfil crediticio, monto ajustado",
            }
        elif risk_score >= 0.4:
            return {
                "status": "under_review",
                "reason": "Requiere revisión adicional",
                "required_documents": [
                    "Comprobante de ingresos últimos 3 meses",
                    "Referencias crediticias",
                    "Estado de cuenta bancario",
                ],
            }
        else:
            return {"status": "rejected", "reason": "No cumple con los requisitos mínimos de crédito"}

    def _format_application_message(self, app: CreditApplicationResponse) -> str:
        """Format application response message"""
        if app.status == "approved":
            message = f"""✅ **¡Felicidades! Tu solicitud de crédito ha sido aprobada**

📋 **Número de Solicitud:** {app.application_id[:8]}
💰 **Monto Solicitado:** ${app.requested_amount:,.2f}
✅ **Monto Aprobado:** ${app.approved_amount:,.2f}
📊 **Tasa de Interés:** {app.interest_rate}% anual
📅 **Plazo:** {app.term_months} meses
🎯 **Score de Riesgo:** {app.risk_score:.2%}

📝 **Próximos pasos:**
1. Firma digital del contrato
2. Verificación de identidad
3. Desembolso en 24-48 horas

¿Deseas proceder con la firma del contrato?"""

        elif app.status == "under_review":
            docs_list = "\n".join([f"• {doc}" for doc in (app.required_documents or [])])
            message = f"""🔍 **Tu solicitud está en revisión**

📋 **Número de Solicitud:** {app.application_id[:8]}
💰 **Monto Solicitado:** ${app.requested_amount:,.2f}

📄 **Documentos requeridos:**
{docs_list}

Por favor, envía los documentos para continuar con la evaluación.
Recibirás una respuesta en 24-48 horas hábiles."""

        else:
            message = f"""❌ **Solicitud de Crédito**

📋 **Número de Solicitud:** {app.application_id[:8]}
📝 **Estado:** No aprobada

**Motivo:** {app.decision_reason}

💡 **Recomendaciones:**
• Mejora tu historial crediticio
• Reduce tus deudas actuales
• Incrementa tus ingresos comprobables

Puedes volver a aplicar en 90 días."""

        return message

