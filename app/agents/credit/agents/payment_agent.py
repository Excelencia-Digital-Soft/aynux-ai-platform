"""
Payment Agent - Handles credit payments and payment schedules
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from app.agents.credit.base_credit_agent import BaseCreditAgent
from app.agents.credit.schemas import CreditState, PaymentResponse


class PaymentAgent(BaseCreditAgent):
    """Agent for handling credit payments"""

    def __init__(self):
        super().__init__("payment")

    async def _process_internal(self, state: CreditState) -> Dict[str, Any]:
        """Process payment request"""
        user_message = self._get_last_user_message(state)
        user_id = state["user_id"]
        credit_account_id = state.get("credit_account_id", user_id)

        # Determine payment intent
        payment_intent = await self._extract_payment_intent(user_message)

        if payment_intent["action"] == "make_payment":
            return await self._process_payment(state, credit_account_id, payment_intent)
        elif payment_intent["action"] == "payment_schedule":
            return await self._get_payment_schedule(credit_account_id)
        elif payment_intent["action"] == "payment_history":
            return await self._get_payment_history(credit_account_id)
        else:
            return await self._payment_options_menu(credit_account_id)

    async def _extract_payment_intent(self, message: str) -> Dict[str, Any]:
        """Extract payment intent from message"""
        message_lower = message.lower()

        if any(word in message_lower for word in ["pagar", "pago", "abonar", "depositar"]):
            # Try to extract amount
            # TODO: Use NLP for better extraction
            return {
                "action": "make_payment",
                "amount": Decimal("2500.00"),  # Mock amount
                "type": "regular",
            }
        elif any(word in message_lower for word in ["calendario", "fechas", "cuándo"]):
            return {"action": "payment_schedule"}
        elif any(word in message_lower for word in ["historial", "pagos anteriores", "comprobantes"]):
            return {"action": "payment_history"}
        else:
            return {"action": "menu"}

    async def _process_payment(
        self, state: CreditState, account_id: str, payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a payment"""
        try:
            # Get current balance
            balance = await self._get_account_balance(account_id)

            # Validate payment amount
            validation = self._validate_payment(payment_data["amount"], balance)
            if not validation["valid"]:
                return {"message": f"❌ {validation['reason']}", "data": None}

            # Process the payment
            payment_id = str(uuid.uuid4())

            # Calculate new balance
            new_balance = balance["current_balance"] - payment_data["amount"]

            payment_response = PaymentResponse(
                payment_id=payment_id,
                account_id=account_id,
                amount=payment_data["amount"],
                payment_type=payment_data["type"],
                status="success",
                transaction_date=datetime.now(UTC),
                remaining_balance=new_balance,
                next_payment_date=balance.get("next_payment_date"),
                receipt_url=f"/receipts/{payment_id}",
            )

            message = self._format_payment_success_message(payment_response, balance)

            # Update payment history in state
            if "payment_history" not in state or state["payment_history"] is None:
                state["payment_history"] = []

            state["payment_history"].append(payment_response.model_dump())

            return {
                "message": message,
                "data": payment_response.model_dump(),
                "available_credit": float(balance["credit_limit"] - new_balance),
            }

        except Exception as e:
            self.logger.error(f"Error processing payment: {str(e)}")
            return {"message": "Error al procesar el pago. Por favor, intenta nuevamente.", "data": None}

    async def _get_payment_schedule(self, account_id: str) -> Dict[str, Any]:
        """Get payment schedule"""
        try:
            schedule = await self._fetch_payment_schedule(account_id)

            message = self._format_payment_schedule_message(schedule)

            return {"message": message, "data": {"schedule": schedule}}

        except Exception as e:
            self.logger.error(f"Error getting payment schedule: {str(e)}")
            return {"message": "Error al obtener el calendario de pagos.", "data": None}

    async def _get_payment_history(self, account_id: str) -> Dict[str, Any]:
        """Get payment history"""
        try:
            history = await self._fetch_payment_history(account_id)

            message = self._format_payment_history_message(history)

            return {"message": message, "data": {"history": history}}

        except Exception as e:
            self.logger.error(f"Error getting payment history: {str(e)}")
            return {"message": "Error al obtener el historial de pagos.", "data": None}

    async def _payment_options_menu(self, account_id: str) -> Dict[str, Any]:
        """Show payment options menu"""
        balance = await self._get_account_balance(account_id)

        message = f"""💳 **Opciones de Pago**

💰 **Saldo Actual:** ${balance["current_balance"]:,.2f}
📅 **Próximo Pago:** ${balance["minimum_payment"]:,.2f}
📆 **Fecha de Vencimiento:** {balance["next_payment_date"].strftime("%d/%m/%Y")}

**¿Qué deseas hacer?**

1️⃣ **Pagar monto mínimo** (${balance["minimum_payment"]:,.2f})
2️⃣ **Pagar saldo total** (${balance["current_balance"]:,.2f})
3️⃣ **Pagar otro monto**
4️⃣ **Ver calendario de pagos**
5️⃣ **Ver historial de pagos**
6️⃣ **Configurar pago automático**

Escribe el número de la opción o el monto que deseas pagar."""

        return {"message": message, "data": {"balance": balance}}

    async def _get_account_balance(self, _account_id: str) -> Dict[str, Any]:
        """Get account balance information"""
        # TODO: Implement actual database query
        return {
            "current_balance": Decimal("15000.00"),
            "credit_limit": Decimal("50000.00"),
            "minimum_payment": Decimal("2500.00"),
            "next_payment_date": date.today() + timedelta(days=15),
        }

    def _validate_payment(self, amount: Decimal, balance: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payment amount"""
        if amount <= 0:
            return {"valid": False, "reason": "El monto debe ser mayor a cero"}

        if amount < balance["minimum_payment"] * Decimal("0.5"):
            return {
                "valid": False,
                "reason": f"El pago mínimo permitido es ${balance['minimum_payment'] * Decimal('0.5'):,.2f}",
            }

        if amount > balance["current_balance"] * Decimal("1.1"):
            return {"valid": False, "reason": "El monto excede el saldo adeudado"}

        return {"valid": True}

    async def _fetch_payment_schedule(self, _account_id: str) -> List[Dict[str, Any]]:
        """Fetch payment schedule from database"""
        # TODO: Implement actual database query
        schedule = []
        current_date = date.today()
        for i in range(6):
            payment_date = current_date + timedelta(days=30 * (i + 1))
            schedule.append(
                {
                    "payment_number": i + 1,
                    "due_date": payment_date,
                    "amount": Decimal("2500.00"),
                    "status": "pending" if i > 0 else "current",
                }
            )
        return schedule

    async def _fetch_payment_history(self, _account_id: str) -> List[Dict[str, Any]]:
        """Fetch payment history from database"""
        # TODO: Implement actual database query
        return [
            {
                "payment_id": "pay_001",
                "date": date.today() - timedelta(days=30),
                "amount": Decimal("2500.00"),
                "status": "completed",
            },
            {
                "payment_id": "pay_002",
                "date": date.today() - timedelta(days=60),
                "amount": Decimal("3000.00"),
                "status": "completed",
            },
        ]

    def _format_payment_success_message(self, payment: PaymentResponse, balance: Dict[str, Any]) -> str:
        """Format payment success message"""
        return f"""✅ **¡Pago Procesado Exitosamente!**

📋 **Detalles del Pago:**
🆔 **ID de Transacción:** {payment.payment_id[:8]}
💰 **Monto Pagado:** ${payment.amount:,.2f}
📅 **Fecha:** {payment.transaction_date.strftime("%d/%m/%Y %H:%M")}
✅ **Estado:** Completado

💳 **Estado de tu Cuenta:**
📊 **Saldo Restante:** ${payment.remaining_balance:,.2f}
✨ **Crédito Disponible:** ${balance["credit_limit"] - payment.remaining_balance:,.2f}
📅 **Próximo Pago:** {payment.next_payment_date.strftime("%d/%m/%Y") if payment.next_payment_date else "N/A"}

📄 **Comprobante:** {payment.receipt_url}

¡Gracias por tu pago! ¿Necesitas algo más?"""

    def _format_payment_schedule_message(self, schedule: List[Dict[str, Any]]) -> str:
        """Format payment schedule message"""
        message = "📅 **Calendario de Pagos**\n\n"

        for payment in schedule:
            status_icon = "🔵" if payment["status"] == "current" else "⏳"
            message += f"{status_icon} **Pago #{payment['payment_number']}**\n"
            message += f"   📆 Fecha: {payment['due_date'].strftime('%d/%m/%Y')}\n"
            message += f"   💰 Monto: ${payment['amount']:,.2f}\n\n"

        message += "💡 **Tip:** Configura pagos automáticos para nunca olvidar una fecha."

        return message

    def _format_payment_history_message(self, history: List[Dict[str, Any]]) -> str:
        """Format payment history message"""
        message = "📊 **Historial de Pagos**\n\n"

        for payment in history:
            message += f"✅ **{payment['date'].strftime('%d/%m/%Y')}**\n"
            message += f"   💰 Monto: ${payment['amount']:,.2f}\n"
            message += f"   🆔 ID: {payment['payment_id']}\n\n"

        message += "📄 Para descargar comprobantes, visita tu portal en línea."

        return message
