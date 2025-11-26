"""
Balance Node - Credit domain node for balance inquiries.
"""

import logging
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method

logger = logging.getLogger(__name__)


class BalanceNode(BaseAgent):
    """Credit node specialized in balance inquiries and account status."""

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        super().__init__("balance_node", config or {}, ollama=ollama)

    @trace_async_method(
        name="balance_node_process",
        run_type="chain",
        metadata={"agent_type": "balance_node", "domain": "credit"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process balance inquiry queries."""
        try:
            # Get credit account info from state
            credit_account_id = state_dict.get("credit_account_id")
            customer = state_dict.get("customer", {})

            if not credit_account_id:
                return self._handle_no_account()

            # Get balance information (simulated)
            balance_info = self._get_balance_info(credit_account_id, customer)

            # Format response
            response_text = self._format_balance_response(balance_info)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "balance_info": balance_info,
                    "credit_account_id": credit_account_id,
                },
                "credit_balance": balance_info,
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in balance node: {str(e)}")

            error_response = (
                "Disculpa, tuve un problema consultando tu saldo. "
                "Por favor intenta de nuevo en unos momentos."
            )

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    def _handle_no_account(self) -> dict[str, Any]:
        """Handle when no credit account is found."""
        response = """**Cuenta de Crédito**

No encontré una cuenta de crédito asociada.

Para consultar tu saldo necesito:
- Tu número de cuenta
- O tu número de cliente

¿Podrías proporcionarme esa información?"""

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "is_complete": False,
        }

    def _get_balance_info(self, account_id: str, customer: dict) -> dict[str, Any]:
        """Get balance information (simulated)."""
        # In production this would query the database
        return {
            "account_id": account_id,
            "customer_name": customer.get("name", "Cliente"),
            "credit_limit": 50000.00,
            "used_credit": 15000.00,
            "available_credit": 35000.00,
            "minimum_payment": 2500.00,
            "next_payment_date": "15/12/2024",
            "status": "active",
            "days_until_cutoff": 10,
            "last_payment_date": "15/11/2024",
            "last_payment_amount": 2500.00,
        }

    def _format_balance_response(self, balance: dict[str, Any]) -> str:
        """Format balance information as response."""
        status_emoji = {
            "active": "[ACTIVE]",
            "delinquent": "[OVERDUE]",
            "suspended": "[SUSPENDED]",
            "closed": "[CLOSED]",
        }

        indicator = status_emoji.get(balance["status"], "[ACCOUNT]")

        response = f"""**Estado de tu Cuenta de Crédito**

{indicator} **Estado:** {balance["status"].capitalize()}

**Resumen Financiero:**
- Límite de crédito: ${balance["credit_limit"]:,.2f}
- Crédito utilizado: ${balance["used_credit"]:,.2f}
- Crédito disponible: ${balance["available_credit"]:,.2f}

**Próximo Pago:**
- Monto mínimo: ${balance["minimum_payment"]:,.2f}
- Fecha de vencimiento: {balance["next_payment_date"]}
- Días hasta el corte: {balance["days_until_cutoff"]}

**Último Pago:**
- Fecha: {balance["last_payment_date"]}
- Monto: ${balance["last_payment_amount"]:,.2f}

¿Necesitas realizar un pago o consultar algo más?"""

        return response


# Alias for backward compatibility
BalanceAgent = BalanceNode
