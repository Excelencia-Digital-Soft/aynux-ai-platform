"""
Payment Node - Credit domain node for payment processing.
"""

import logging
import re
from datetime import datetime
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method

logger = logging.getLogger(__name__)


class PaymentNode(BaseAgent):
    """Credit node specialized in payment processing and history."""

    def __init__(self, llm=None, config: dict[str, Any] | None = None):
        super().__init__("payment_node", config or {}, llm=llm)

    @trace_async_method(
        name="payment_node_process",
        run_type="chain",
        metadata={"agent_type": "payment_node", "domain": "credit"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process payment queries and requests."""
        try:
            # Detect query type
            query_type = self._detect_query_type(message)

            credit_account_id = state_dict.get("credit_account_id")

            if not credit_account_id:
                return self._handle_no_account()

            # Process based on query type
            if query_type == "make_payment":
                amount = self._extract_amount(message)
                response_text = self._handle_payment_request(credit_account_id, amount)
            elif query_type == "payment_history":
                response_text = self._handle_payment_history(credit_account_id)
            elif query_type == "payment_methods":
                response_text = self._handle_payment_methods()
            elif query_type == "payment_confirmation":
                response_text = self._handle_payment_confirmation()
            else:
                response_text = self._handle_general_payment_query()

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "query_type": query_type,
                    "credit_account_id": credit_account_id,
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in payment node: {str(e)}")

            error_response = (
                "Disculpa, tuve un problema procesando tu solicitud de pago. "
                "Por favor intenta de nuevo."
            )

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    def _detect_query_type(self, message: str) -> str:
        """Detect the type of payment query."""
        message_lower = message.lower()

        query_patterns = {
            "make_payment": ["pagar", "realizar pago", "abonar", "quiero pagar"],
            "payment_history": ["historial", "pagos anteriores", "mis pagos", "ultimos pagos"],
            "payment_methods": ["metodos", "formas de pago", "como pagar", "donde pago"],
            "payment_confirmation": ["comprobante", "confirmacion", "recibo"],
        }

        for query_type, keywords in query_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return query_type

        return "general"

    def _extract_amount(self, message: str) -> float | None:
        """Extract payment amount from message."""
        patterns = [
            r"\$?([\d,]+(?:\.\d{2})?)",
            r"(\d+(?:,\d{3})*(?:\.\d{2})?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    return float(amount_str)
                except ValueError:
                    continue

        return None

    def _handle_no_account(self) -> dict[str, Any]:
        """Handle when no credit account is found."""
        response = """**Pagos de Crédito**

Para procesar tu pago necesito identificar tu cuenta.

Por favor proporciona:
- Tu número de cuenta
- O tu número de cliente

¿Cuál es tu información?"""

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "is_complete": False,
        }

    def _handle_payment_request(self, account_id: str, amount: float | None) -> str:
        """Handle payment request."""
        if not amount:
            return """**Realizar Pago**

Para procesar tu pago, necesito saber el monto.

**Opciones disponibles:**
- Pago mínimo: $2,500.00
- Pago para no generar intereses: $15,000.00
- Pago total: $15,000.00

¿Qué monto deseas pagar?"""

        # Simulate payment processing
        return f"""**Confirmación de Pago**

[PROCESSING] Procesando tu pago...

**Detalles del pago:**
- Cuenta: {account_id}
- Monto: ${amount:,.2f}
- Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}

**Métodos disponibles:**
1. **Tarjeta de débito** - Procesamiento inmediato
2. **Transferencia SPEI** - 5-10 minutos
3. **Pago en tienda** - Genera referencia

¿Con qué método deseas pagar?"""

    def _handle_payment_history(self, account_id: str) -> str:
        """Handle payment history request."""
        _ = account_id  # unused in simulation

        return """**Historial de Pagos**

**Últimos 5 pagos:**

1. **15/11/2024** - $2,500.00
   [PAID] Tarjeta de débito

2. **15/10/2024** - $3,000.00
   [PAID] Transferencia SPEI

3. **15/09/2024** - $2,500.00
   [PAID] Pago en tienda

4. **15/08/2024** - $5,000.00
   [PAID] Tarjeta de débito

5. **15/07/2024** - $2,500.00
   [PAID] Transferencia SPEI

**Resumen:**
- Total pagado (últimos 6 meses): $15,500.00
- Pagos a tiempo: 5/5 (100%)

¿Necesitas el comprobante de algún pago específico?"""

    def _handle_payment_methods(self) -> str:
        """Handle payment methods query."""
        return """**Métodos de Pago Disponibles**

**Pagos en Línea:**
- Tarjeta de débito/crédito
- Transferencia SPEI
- Pago con QR

**Pagos en Tienda:**
- OXXO (referencia de pago)
- 7-Eleven
- Farmacias del Ahorro

**Domiciliación Bancaria:**
- Cargo automático mensual
- Evita recargos y comisiones
- Actívala sin costo

**Pago por Teléfono:**
- Línea de atención: 800-XXX-XXXX
- Horario: 24/7

¿Cuál método prefieres utilizar?"""

    def _handle_payment_confirmation(self) -> str:
        """Handle payment confirmation request."""
        return """**Comprobante de Pago**

Para obtener tu comprobante, selecciona una opción:

1. **Por correo electrónico**
   Te enviamos el comprobante a tu email registrado

2. **Descargar PDF**
   Genera el comprobante para descargar

3. **Ver en pantalla**
   Muestra los detalles del pago

¿Cuál pago necesitas comprobar?
(Indica la fecha o el monto)"""

    def _handle_general_payment_query(self) -> str:
        """Handle general payment queries."""
        return """**Centro de Pagos**

¿En qué puedo ayudarte?

- **Realizar un pago** - Pagar tu saldo
- **Ver historial** - Consultar pagos anteriores
- **Métodos de pago** - Opciones disponibles
- **Comprobantes** - Obtener recibos

¿Qué necesitas hacer?"""


# Alias for backward compatibility
PaymentAgent = PaymentNode
