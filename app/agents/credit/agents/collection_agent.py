"""
Collection Agent - Manages overdue accounts and collection strategies
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from app.agents.credit.base_credit_agent import BaseCreditAgent
from app.agents.credit.schemas import CreditState, UserRole


class CollectionAgent(BaseCreditAgent):
    """Agent for managing collections and overdue accounts"""

    def __init__(self):
        super().__init__("collection")

    async def _process_internal(self, state: CreditState) -> Dict[str, Any]:
        """Process collection-related requests"""
        user_message = self._get_last_user_message(state)
        user_role = UserRole(state.get("user_role", UserRole.CUSTOMER))

        if user_role == UserRole.CUSTOMER:
            # Customer inquiring about overdue account
            return await self._handle_customer_collection(state)
        else:
            # Staff managing collections
            return await self._handle_staff_collection(state, user_message)

    async def _handle_customer_collection(self, state: CreditState) -> Dict[str, Any]:
        """Handle customer inquiries about overdue accounts"""
        account_id = state.get("credit_account_id", state["user_id"])

        try:
            # Get account status
            account_info = await self._get_overdue_account_info(account_id)

            if not account_info["is_overdue"]:
                return {"message": "✅ Tu cuenta está al día. No tienes pagos vencidos.", "data": account_info}

            # Generate payment options
            payment_options = self._generate_payment_options(account_info)
            message = self._format_customer_collection_message(account_info, payment_options)

            return {"message": message, "data": {"account_info": account_info, "payment_options": payment_options}}

        except Exception as e:
            self.logger.error(f"Error in customer collection: {str(e)}")
            return {"message": "Error al consultar el estado de tu cuenta.", "data": None}

    async def _handle_staff_collection(self, state: CreditState, message: str) -> Dict[str, Any]:
        """Handle staff collection management"""
        user_role = UserRole(state.get("user_role"))

        # Check permissions
        if user_role not in [UserRole.COLLECTION_AGENT, UserRole.MANAGER, UserRole.ADMIN]:
            return {"message": "No tienes permisos para gestionar cobranzas.", "data": None}

        # Determine collection action
        action = await self._extract_collection_action(message)

        if action["type"] == "portfolio_view":
            return await self._get_collection_portfolio()
        elif action["type"] == "account_detail":
            return await self._get_account_collection_detail(action["account_id"])
        elif action["type"] == "strategy":
            return await self._generate_collection_strategy(action["account_id"])
        else:
            return await self._show_collection_dashboard()

    async def _get_overdue_account_info(self, account_id: str) -> Dict[str, Any]:
        """Get overdue account information"""
        # TODO: Implement actual database query
        return {
            "account_id": account_id,
            "is_overdue": True,
            "days_overdue": 15,
            "overdue_amount": Decimal("5000.00"),
            "total_debt": Decimal("15000.00"),
            "minimum_payment": Decimal("2500.00"),
            "late_fees": Decimal("250.00"),
            "last_payment_date": date.today() - timedelta(days=45),
            "collection_stage": "early",
        }

    def _generate_payment_options(self, account_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate payment options for overdue account"""
        options = []

        # Option 1: Pay overdue amount
        options.append(
            {
                "option": "pay_overdue",
                "amount": account_info["overdue_amount"] + account_info["late_fees"],
                "description": "Pagar monto vencido",
                "benefit": "Evita más cargos por mora",
            }
        )

        # Option 2: Payment plan
        installments = 3
        monthly_amount = (account_info["overdue_amount"] + account_info["late_fees"]) / installments
        options.append(
            {
                "option": "payment_plan",
                "amount": monthly_amount,
                "installments": installments,
                "description": f"Plan de pago en {installments} cuotas",
                "benefit": "Regulariza tu cuenta gradualmente",
            }
        )

        # Option 3: Settlement offer
        if account_info["days_overdue"] > 30:
            settlement_amount = account_info["total_debt"] * Decimal("0.7")
            options.append(
                {
                    "option": "settlement",
                    "amount": settlement_amount,
                    "description": "Oferta de liquidación",
                    "benefit": "Salda tu deuda con descuento",
                }
            )

        return options

    async def _extract_collection_action(self, message: str) -> Dict[str, Any]:
        """Extract collection action from message"""
        message_lower = message.lower()

        if "portfolio" in message_lower or "cartera" in message_lower:
            return {"type": "portfolio_view"}
        elif "cuenta" in message_lower and any(word in message_lower for word in ["detalle", "información"]):
            return {"type": "account_detail", "account_id": "extracted_id"}
        elif "estrategia" in message_lower or "strategy" in message_lower:
            return {"type": "strategy", "account_id": "extracted_id"}
        else:
            return {"type": "dashboard"}

    async def _get_collection_portfolio(self) -> Dict[str, Any]:
        """Get collection portfolio overview"""
        # TODO: Implement actual database query
        portfolio = {
            "total_accounts": 150,
            "total_amount": Decimal("2500000.00"),
            "by_stage": {
                "early": {"count": 80, "amount": Decimal("800000.00")},
                "intermediate": {"count": 50, "amount": Decimal("1000000.00")},
                "advanced": {"count": 20, "amount": Decimal("700000.00")},
            },
            "recovery_rate": 0.65,
            "average_days_overdue": 35,
        }

        message = self._format_portfolio_message(portfolio)
        return {"message": message, "data": portfolio}

    async def _show_collection_dashboard(self) -> Dict[str, Any]:
        """Show collection dashboard"""
        message = """📊 **Panel de Cobranza**

**Opciones disponibles:**

1️⃣ **Ver cartera de cobranza**
2️⃣ **Buscar cuenta específica**
3️⃣ **Generar estrategia de cobranza**
4️⃣ **Ver reportes de recuperación**
5️⃣ **Gestionar promesas de pago**
6️⃣ **Actualizar notas de cobranza**

¿Qué deseas hacer?"""

        return {"message": message, "data": {"type": "dashboard"}}

    def _format_customer_collection_message(self, account_info: Dict[str, Any], options: List[Dict[str, Any]]) -> str:
        """Format collection message for customer"""
        severity_icon = "⚠️" if account_info["days_overdue"] < 30 else "🔴"

        message = f"""{severity_icon} **Atención: Tu cuenta tiene un saldo vencido**

📅 **Días de atraso:** {account_info["days_overdue"]} días
💰 **Monto vencido:** ${account_info["overdue_amount"]:,.2f}
📈 **Cargos por mora:** ${account_info["late_fees"]:,.2f}
💳 **Deuda total:** ${account_info["total_debt"]:,.2f}

**🎯 Opciones de Pago Disponibles:**
"""

        for i, option in enumerate(options, 1):
            message += f"\n{i}️⃣ **{option['description']}**"
            if "installments" in option:
                message += f"\n   💵 ${option['amount']:,.2f} mensuales x {option['installments']} meses"
            else:
                message += f"\n   💵 ${option['amount']:,.2f}"
            message += f"\n   ✅ {option['benefit']}\n"

        message += """
⏰ **Es importante regularizar tu cuenta para:**
• Evitar cargos adicionales
• Mantener tu historial crediticio
• Conservar tu línea de crédito

¿Te gustaría seleccionar alguna opción de pago?"""

        return message

    def _format_portfolio_message(self, portfolio: Dict[str, Any]) -> str:
        """Format portfolio overview message"""
        message = f"""📊 **Cartera de Cobranza**

📈 **Resumen General:**
• **Total de cuentas:** {portfolio["total_accounts"]}
• **Monto total:** ${portfolio["total_amount"]:,.2f}
• **Tasa de recuperación:** {portfolio["recovery_rate"]:.1%}
• **Promedio días vencidos:** {portfolio["average_days_overdue"]}

📋 **Por Etapa de Cobranza:**"""

        stage_names = {
            "early": "Temprana (1-30 días)",
            "intermediate": "Intermedia (31-60 días)",
            "advanced": "Avanzada (60+ días)",
        }

        for stage, data in portfolio["by_stage"].items():
            message += f"\n\n**{stage_names[stage]}:**"
            message += f"\n• Cuentas: {data['count']}"
            message += f"\n• Monto: ${data['amount']:,.2f}"

        message += """

📊 **Acciones Recomendadas:**
• Priorizar cuentas en etapa avanzada
• Ofrecer planes de pago a etapa intermedia
• Llamadas preventivas a etapa temprana"""

        return message

    async def _generate_collection_strategy(self, account_id: str) -> Dict[str, Any]:
        """Generate collection strategy for specific account"""
        # TODO: Implement actual strategy generation
        strategy = {
            "account_id": account_id,
            "recommended_actions": [
                {"day": 1, "action": "SMS recordatorio", "channel": "SMS"},
                {"day": 3, "action": "Llamada telefónica", "channel": "Phone"},
                {"day": 7, "action": "Email con opciones de pago", "channel": "Email"},
                {"day": 15, "action": "Carta formal", "channel": "Mail"},
                {"day": 30, "action": "Visita domiciliaria", "channel": "Field"},
            ],
            "settlement_options": {"min_acceptable": Decimal("12000.00"), "recommended": Decimal("13500.00")},
        }

        message = "📋 **Estrategia de Cobranza Generada**\n\n"
        for action in strategy["recommended_actions"]:
            message += f"📅 Día {action['day']}: {action['action']} ({action['channel']})\n"

        return {"message": message, "data": strategy}

    async def _get_account_collection_detail(self, account_id: str) -> Dict[str, Any]:
        """Get detailed collection information for specific account"""
        # TODO: Implement actual database query
        account_detail = {
            "account_id": account_id,
            "days_overdue": 25,
            "overdue_amount": Decimal("3500.00"),
            "collection_stage": "intermediate",
            "last_contact_date": date.today() - timedelta(days=5),
            "contact_history": [
                {"date": date.today() - timedelta(days=5), "type": "SMS", "outcome": "no_response"},
                {"date": date.today() - timedelta(days=10), "type": "Phone", "outcome": "promise_to_pay"},
            ],
            "payment_promises": [
                {"date": date.today() - timedelta(days=10), "amount": Decimal("1500.00"), "fulfilled": False}
            ]
        }

        message = f"""📋 **Detalle de Cuenta en Cobranza**

🆔 **Cuenta:** {account_id}
📅 **Días de atraso:** {account_detail['days_overdue']} días
💰 **Monto vencido:** ${account_detail['overdue_amount']:,.2f}
🏷️ **Etapa:** {account_detail['collection_stage']}
📞 **Último contacto:** {account_detail['last_contact_date'].strftime('%d/%m/%Y')}

📊 **Historial de contactos:**"""

        for contact in account_detail["contact_history"]:
            message += f"\n• {contact['date'].strftime('%d/%m/%Y')} - {contact['type']}: {contact['outcome']}"

        return {"message": message, "data": account_detail}

