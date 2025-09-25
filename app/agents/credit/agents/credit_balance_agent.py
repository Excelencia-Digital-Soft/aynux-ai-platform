"""
Credit Balance Agent - Handles balance inquiries and credit limit information
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict

from app.agents.credit.base_credit_agent import BaseCreditAgent
from app.agents.credit.schemas import CreditBalanceResponse, CreditState


class CreditBalanceAgent(BaseCreditAgent):
    """Agent for handling credit balance inquiries"""

    def __init__(self):
        super().__init__("credit_balance")

    async def _process_internal(self, state: CreditState) -> Dict[str, Any]:
        """Process credit balance inquiry"""
        self._get_last_user_message(state)
        user_id = state["user_id"]
        credit_account_id = state.get("credit_account_id")

        self.logger.info(f"Processing balance inquiry for user {user_id}")

        try:
            # In production, this would query the database
            # For now, we'll simulate the response
            balance_data = await self._get_credit_balance(credit_account_id or user_id)

            if balance_data:
                response = CreditBalanceResponse(**balance_data)

                message = self._format_balance_message(response)

                return {
                    "message": message,
                    "data": response.model_dump(),
                    "credit_limit": float(response.credit_limit),
                    "available_credit": float(response.available_credit),
                }
            else:
                return {
                    "message": "No se encontró información de crédito para tu cuenta. \
                        Por favor, contacta a servicio al cliente.",
                    "data": None,
                }

        except Exception as e:
            self.logger.error(f"Error getting credit balance: {str(e)}")
            return {"message": "Ocurrió un error al consultar tu saldo. Por favor, intenta nuevamente.", "data": None}

    async def _get_credit_balance(self, account_id: str) -> Dict[str, Any]:
        """Get credit balance from database"""
        # TODO: Implement actual database query
        # This is a mock implementation
        return {
            "account_id": account_id,
            "credit_limit": Decimal("50000.00"),
            "used_credit": Decimal("15000.00"),
            "available_credit": Decimal("35000.00"),
            "next_payment_date": date(2024, 2, 15),
            "next_payment_amount": Decimal("2500.00"),
            "interest_rate": Decimal("18.5"),
            "status": "active",
        }

    def _format_balance_message(self, balance: CreditBalanceResponse) -> str:
        """Format balance information into a readable message"""
        message = f"""📊 **Estado de tu Crédito**

💳 **Cuenta:** {balance.account_id[-4:]}
📈 **Límite de Crédito:** ${balance.credit_limit:,.2f}
💰 **Crédito Utilizado:** ${balance.used_credit:,.2f}
✅ **Crédito Disponible:** ${balance.available_credit:,.2f}

📅 **Próximo Pago:** {balance.next_payment_date.strftime("%d/%m/%Y") if balance.next_payment_date else "N/A"}
💵 **Monto a Pagar:** ${balance.next_payment_amount:,.2f} if balance.next_payment_amount else 'N/A'

📊 **Tasa de Interés:** {balance.interest_rate}% anual
🔔 **Estado:** {self._translate_status(balance.status)}

¿Necesitas algo más? Puedo ayudarte con:
• 💳 Solicitar aumento de línea de crédito
• 💰 Realizar un pago
• 📄 Descargar tu estado de cuenta
• 🛍️ Ver productos disponibles para agregar a tu crédito"""

        return message

    def _translate_status(self, status: str) -> str:
        """Translate status to Spanish"""
        translations = {
            "active": "Activo ✅",
            "blocked": "Bloqueado ⚠️",
            "overdue": "Con retraso 🔴",
            "closed": "Cerrado ❌",
        }
        return translations.get(status, status)

