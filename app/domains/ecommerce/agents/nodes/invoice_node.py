"""
Invoice Node - E-commerce domain node for billing and payment queries.
"""

import logging
import random
import re
from datetime import datetime, timedelta
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method

logger = logging.getLogger(__name__)


class InvoiceNode(BaseAgent):
    """E-commerce node specialized in billing, payments and financial queries"""

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        super().__init__("invoice_node", config or {}, ollama=ollama)

    @trace_async_method(
        name="invoice_node_process",
        run_type="chain",
        metadata={"agent_type": "invoice_node", "domain": "ecommerce"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process billing and payment queries."""
        try:
            # Detect query type
            query_type = self._detect_query_type(message)

            # Extract relevant information
            invoice_number = self._extract_invoice_number(message)
            order_number = self._extract_order_number(message)

            # Process based on query type
            if query_type == "invoice_status" and (invoice_number or order_number):
                response_text = self._handle_invoice_status(invoice_number, order_number)
            elif query_type == "payment_methods":
                response_text = self._handle_payment_methods()
            elif query_type == "payment_issue":
                response_text = self._handle_payment_issue(message)
            elif query_type == "refund":
                response_text = self._handle_refund_request(message)
            elif query_type == "tax_info":
                response_text = self._handle_tax_info()
            else:
                response_text = self._handle_general_invoice_query()

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "query_type": query_type,
                    "invoice_number": invoice_number,
                    "order_number": order_number,
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in invoice node: {str(e)}")

            error_response = (
                "Disculpa, tuve un problema procesando tu consulta de facturacion. "
                "Podrias intentar de nuevo?"
            )

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    def _detect_query_type(self, message: str) -> str:
        """Detect the type of billing query."""
        message_lower = message.lower()

        query_patterns = {
            "invoice_status": ["factura", "invoice", "estado", "pago", "cobro"],
            "payment_methods": ["metodos de pago", "formas de pago", "como pagar", "tarjeta"],
            "payment_issue": ["problema pago", "rechazada", "error", "no paso"],
            "refund": ["reembolso", "devolver dinero", "reintegro", "cancelar pago"],
            "tax_info": ["impuesto", "iva", "afip", "cuit", "fiscal"],
        }

        for query_type, keywords in query_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return query_type

        return "general"

    def _extract_invoice_number(self, message: str) -> str | None:
        """Extract invoice number from message."""
        patterns = [
            r"factura\s*#?(\d+)",
            r"invoice\s*#?(\d+)",
            r"#(\d{6,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_order_number(self, message: str) -> str | None:
        """Extract order number from message."""
        patterns = [
            r"orden\s*#?(\d{6,})",
            r"pedido\s*#?(\d{6,})",
            r"order\s*#?(\d{6,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _handle_invoice_status(
        self, invoice_number: str | None, order_number: str | None
    ) -> str:
        """Handle invoice status queries."""
        # Simulate invoice information
        number = invoice_number or order_number
        if not number:
            return "No se proporciono numero de factura u orden. Por favor proporciona un numero valido."
        invoice_info = self._get_invoice_info(number)

        if not invoice_info:
            return """No encontre informacion de factura con ese numero.

Por favor verifica:
- Que el numero sea correcto
- Que la compra este asociada a tu cuenta
- Que hayan pasado al menos 24hs desde la compra

Necesitas ayuda con algo mas?"""

        status_indicator = {
            "pendiente": "[PENDING]",
            "pagada": "[PAID]",
            "vencida": "[OVERDUE]",
            "cancelada": "[CANCELLED]",
        }

        indicator = status_indicator.get(invoice_info["status"], "[INVOICE]")

        response = f"""**Factura #{invoice_info["number"]}**

{indicator} **Estado**: {invoice_info["status"].capitalize()}
**Monto**: ${invoice_info["amount"]:,}
**Fecha de emision**: {invoice_info["issue_date"]}
**Vencimiento**: {invoice_info["due_date"]}

"""

        if invoice_info["status"] == "pendiente":
            response += """**Opciones de pago**:
- Transferencia bancaria
- Tarjeta de credito/debito
- Mercado Pago
- PayPal

Necesitas ayuda para realizar el pago?"""

        elif invoice_info["status"] == "pagada":
            response += f"""**Pago confirmado**
Fecha de pago: {invoice_info.get("payment_date", "No disponible")}
Metodo: {invoice_info.get("payment_method", "No especificado")}

Necesitas el comprobante de pago?"""

        elif invoice_info["status"] == "vencida":
            response += """**Factura vencida**

Puedes realizar el pago con recargo minimo.
Te ayudo a procesar el pago ahora?"""

        return response

    def _handle_payment_methods(self) -> str:
        """Handle payment methods queries."""
        return """**Metodos de Pago Disponibles**

**Tarjetas de Credito/Debito**
- Visa, Mastercard, American Express
- Hasta 12 cuotas sin interes
- Procesamiento inmediato

**Transferencia Bancaria**
- Descuento 5% por pago contado
- Acreditacion en 24-48hs
- CBU: 1234567890123456789012

**Billeteras Digitales**
- Mercado Pago
- PayPal
- Todo Pago

**Efectivo**
- Rapipago, Pago Facil
- Comision 2%
- Hasta 48hs para acreditacion

Te interesa algun metodo en particular?"""

    def _handle_payment_issue(self, message: str) -> str:
        """Handle payment issues."""
        _ = message  # unused
        return """**Solucion de Problemas de Pago**

**Si tu tarjeta fue rechazada:**
- Verifica fondos disponibles
- Confirma datos ingresados
- Contacta a tu banco
- Intenta con otra tarjeta

**Si el pago no se proceso:**
- Espera 10-15 minutos
- Revisa tu email de confirmacion
- Verifica debito en tu cuenta

**Errores comunes:**
- CVV incorrecto
- Fecha de vencimiento incorrecta
- Limite de compras online

Cual es especificamente tu problema? Puedo ayudarte a resolverlo."""

    def _handle_refund_request(self, message: str) -> str:
        """Handle refund requests."""
        _ = message  # unused
        return """**Proceso de Reembolso**

**Requisitos:**
- Solicitud dentro de 30 dias
- Producto sin uso (condiciones originales)
- Comprobante de compra

**Tiempo de procesamiento:**
- Tarjeta de credito: 5-10 dias habiles
- Transferencia: 2-3 dias habiles
- Efectivo: Inmediato en sucursal

**Informacion necesaria:**
- Numero de orden
- Motivo del reembolso
- Fotos del producto (si aplica)

Tienes el numero de orden para iniciar el proceso?"""

    def _handle_tax_info(self) -> str:
        """Handle tax information queries."""
        return """**Informacion Fiscal**

**Facturacion:**
- Facturas A, B o C segun tu condicion
- CUIT/CUIL requerido para Factura A
- Consumidor Final para Factura C

**Impuestos incluidos:**
- IVA 21% (productos gravados)
- Impuesto PAIS (productos importados)
- Todos los precios mostrados incluyen impuestos

**Para empresas:**
- Factura A con retenciones aplicables
- Comprobante de inscripcion en AFIP
- Condicion fiscal actualizada

Necesitas modificar tu informacion fiscal?"""

    def _handle_general_invoice_query(self) -> str:
        """Handle general billing queries."""
        return """**Centro de Facturacion**

Puedo ayudarte con:

- **Estado de facturas**
- **Metodos de pago**
- **Problemas de pago**
- **Reembolsos**
- **Informacion fiscal**
- **Descargar comprobantes**

En que especificamente puedo ayudarte?

Para consultas especificas, proporciona:
- Numero de factura o pedido
- Fecha aproximada de compra
- Email asociado a la cuenta"""

    def _get_invoice_info(self, number: str) -> dict[str, Any] | None:
        """Get invoice information (simulated)."""
        if not number:
            return None

        # Simulate invoice data
        today = datetime.now()
        issue_date = today - timedelta(days=5)
        due_date = issue_date + timedelta(days=30)

        # Simulate different statuses
        statuses = ["pendiente", "pagada", "vencida"]
        status = random.choice(statuses)

        invoice_data = {
            "number": number,
            "status": status,
            "amount": random.randint(5000, 50000),
            "issue_date": issue_date.strftime("%d/%m/%Y"),
            "due_date": due_date.strftime("%d/%m/%Y"),
        }

        if status == "pagada":
            payment_date = issue_date + timedelta(days=random.randint(1, 10))
            invoice_data.update(
                {
                    "payment_date": payment_date.strftime("%d/%m/%Y"),
                    "payment_method": "Tarjeta de credito",
                }
            )

        return invoice_data


# Alias for backward compatibility
InvoiceAgent = InvoiceNode
