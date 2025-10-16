"""
Statement Agent - Handles account statements and transaction history
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from app.agents.credit.base_credit_agent import BaseCreditAgent
from app.agents.credit.schemas import CreditState, StatementResponse


class StatementAgent(BaseCreditAgent):
    """Agent for handling account statements"""

    def __init__(self):
        super().__init__("statement")

    async def _process_internal(self, state: CreditState) -> Dict[str, Any]:
        """Process statement request"""
        user_message = self._get_last_user_message(state)
        user_id = state["user_id"]
        credit_account_id = state.get("credit_account_id", user_id)

        # Determine statement period
        period = await self._extract_statement_period(user_message)

        try:
            # Generate statement
            statement = await self._generate_statement(credit_account_id, period)

            if statement:
                response = StatementResponse(**statement)
                message = self._format_statement_message(response)

                return {"message": message, "data": response.model_dump()}
            else:
                return {"message": "No se encontraron transacciones para el período solicitado.", "data": None}

        except Exception as e:
            self.logger.error(f"Error generating statement: {str(e)}")
            return {"message": "Error al generar el estado de cuenta. Por favor, intenta nuevamente.", "data": None}

    async def _extract_statement_period(self, message: str) -> Dict[str, date]:
        """Extract statement period from message"""
        message_lower = message.lower()

        # Check for specific months
        months = {
            "enero": 1,
            "febrero": 2,
            "marzo": 3,
            "abril": 4,
            "mayo": 5,
            "junio": 6,
            "julio": 7,
            "agosto": 8,
            "septiembre": 9,
            "octubre": 10,
            "noviembre": 11,
            "diciembre": 12,
        }

        for month_name, month_num in months.items():
            if month_name in message_lower:
                year = date.today().year
                start_date = date(year, month_num, 1)
                last_day = calendar.monthrange(year, month_num)[1]
                end_date = date(year, month_num, last_day)
                return {"start": start_date, "end": end_date}

        # Default to current month
        today = date.today()
        start_date = date(today.year, today.month, 1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_date = date(today.year, today.month, last_day)

        return {"start": start_date, "end": end_date}

    async def _generate_statement(self, account_id: str, period: Dict[str, date]) -> Dict[str, Any]:
        """Generate account statement"""
        # TODO: Implement actual database queries
        # This is a mock implementation

        # Get transactions for the period
        transactions = await self._get_transactions(account_id, period)

        # Calculate totals
        total_charges = sum(t["amount"] for t in transactions if t["type"] == "charge")
        total_payments = sum(t["amount"] for t in transactions if t["type"] == "payment")
        interest_charged = Decimal("250.00")  # Mock interest

        # Get balances
        opening_balance = Decimal("12000.00")  # Mock
        closing_balance = opening_balance + total_charges - total_payments + interest_charged

        return {
            "account_id": account_id,
            "statement_period": f"{period['start'].strftime('%B %Y')}",
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "total_charges": total_charges,
            "total_payments": total_payments,
            "interest_charged": interest_charged,
            "transactions": transactions,
            "minimum_payment": closing_balance * Decimal("0.05"),
            "due_date": period["end"] + timedelta(days=20),
            "pdf_url": f"/statements/{account_id}/{period['start'].strftime('%Y%m')}.pdf",
        }

    async def _get_transactions(self, _account_id: str, period: Dict[str, date]) -> List[Dict[str, Any]]:
        """Get transactions for the period"""
        # TODO: Implement actual database query
        # Mock transactions
        return [
            {
                "date": period["start"] + timedelta(days=5),
                "description": "Compra - Tienda XYZ",
                "type": "charge",
                "amount": Decimal("1500.00"),
                "balance": Decimal("13500.00"),
            },
            {
                "date": period["start"] + timedelta(days=10),
                "description": "Compra - Restaurante ABC",
                "type": "charge",
                "amount": Decimal("800.00"),
                "balance": Decimal("14300.00"),
            },
            {
                "date": period["start"] + timedelta(days=15),
                "description": "Pago - Gracias",
                "type": "payment",
                "amount": Decimal("2500.00"),
                "balance": Decimal("11800.00"),
            },
            {
                "date": period["start"] + timedelta(days=20),
                "description": "Compra - Supermercado",
                "type": "charge",
                "amount": Decimal("3200.00"),
                "balance": Decimal("15000.00"),
            },
        ]

    def _format_statement_message(self, statement: StatementResponse) -> str:
        """Format statement message"""
        message = f"""📄 **Estado de Cuenta - {statement.statement_period}**

🏦 **Cuenta:** ***{statement.account_id[-4:]}

💰 **Resumen del Período:**
• **Saldo Inicial:** ${statement.opening_balance:,.2f}
• **Cargos (+):** ${statement.total_charges:,.2f}
• **Pagos (-):** ${statement.total_payments:,.2f}
• **Intereses (+):** ${statement.interest_charged:,.2f}
• **Saldo Final:** ${statement.closing_balance:,.2f}

📊 **Movimientos:**
"""

        # Add transactions
        for trans in statement.transactions[:5]:  # Show first 5 transactions
            if trans["type"] == "charge":
                icon = "🛍️"
                sign = "+"
            else:
                icon = "💳"
                sign = "-"

            message += f"\n{icon} {trans['date'].strftime('%d/%m')} - {trans['description']}"
            message += f"\n   {sign}${trans['amount']:,.2f} | Saldo: ${trans['balance']:,.2f}\n"

        if len(statement.transactions) > 5:
            message += f"\n... y {len(statement.transactions) - 5} transacciones más\n"

        message += f"""
💵 **Pago Mínimo:** ${statement.minimum_payment:,.2f}
📅 **Fecha de Vencimiento:** {statement.due_date.strftime("%d/%m/%Y")}

📥 **Descargar Estado de Cuenta Completo:**
{statement.pdf_url}

¿Necesitas algo más? Puedo ayudarte con:
• 💳 Realizar un pago
• 📊 Ver otro período
• 🔍 Buscar una transacción específica"""

        return message

