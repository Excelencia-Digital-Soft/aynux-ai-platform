"""
Agente especializado en generación de facturas
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class InvoiceAgent(BaseAgent):
    """Agente especializado en facturación, pagos y consultas financieras"""

    def __init__(self, ollama=None, chroma=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("invoice_agent", config or {}, ollama=ollama, chroma=chroma)

    @trace_async_method(
        name="invoice_agent_process",
        run_type="agent",
        metadata={"agent_type": "invoice", "payment_processing": "enabled"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa consultas sobre facturación y pagos."""
        try:
            # Detectar tipo de consulta
            query_type = self._detect_query_type(message)

            # Extraer información relevante
            invoice_number = self._extract_invoice_number(message)
            order_number = self._extract_order_number(message)

            # Procesar según el tipo de consulta
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
            logger.error(f"Error in invoice agent: {str(e)}")

            error_response = (
                "Disculpa, tuve un problema procesando tu consulta de facturación. ¿Podrías intentar de nuevo?"
            )

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    def _detect_query_type(self, message: str) -> str:
        """Detecta el tipo de consulta sobre facturación."""
        message_lower = message.lower()

        query_patterns = {
            "invoice_status": ["factura", "invoice", "estado", "pago", "cobro"],
            "payment_methods": ["métodos de pago", "formas de pago", "cómo pagar", "tarjeta"],
            "payment_issue": ["problema pago", "rechazada", "error", "no pasó"],
            "refund": ["reembolso", "devolver dinero", "reintegro", "cancelar pago"],
            "tax_info": ["impuesto", "iva", "afip", "cuit", "fiscal"],
        }

        for query_type, keywords in query_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return query_type

        return "general"

    def _extract_invoice_number(self, message: str) -> Optional[str]:
        """Extrae número de factura del mensaje."""
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

    def _extract_order_number(self, message: str) -> Optional[str]:
        """Extrae número de orden del mensaje."""
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

    def _handle_invoice_status(self, invoice_number: Optional[str], order_number: Optional[str]) -> str:
        """Maneja consultas sobre estado de factura."""
        # Simular información de factura
        invoice_info = self._get_invoice_info(invoice_number or order_number)

        if not invoice_info:
            return """No encontré información de factura con ese número.

Por favor verifica:
• Que el número sea correcto
• Que la compra esté asociada a tu cuenta
• Que hayan pasado al menos 24hs desde la compra

¿Necesitas ayuda con algo más?"""

        status_emoji = {"pendiente": "⏳", "pagada": "✅", "vencida": "⚠️", "cancelada": "❌"}

        emoji = status_emoji.get(invoice_info["status"], "📄")

        response = f"""📄 **Factura #{invoice_info["number"]}**

{emoji} **Estado**: {invoice_info["status"].capitalize()}
💰 **Monto**: ${invoice_info["amount"]:,}
📅 **Fecha de emisión**: {invoice_info["issue_date"]}
🗓️ **Vencimiento**: {invoice_info["due_date"]}

"""

        if invoice_info["status"] == "pendiente":
            response += """💡 **Opciones de pago**:
• Transferencia bancaria
• Tarjeta de crédito/débito
• Mercado Pago
• PayPal

¿Necesitas ayuda para realizar el pago?"""

        elif invoice_info["status"] == "pagada":
            response += f"""✅ **Pago confirmado**
📅 Fecha de pago: {invoice_info.get("payment_date", "No disponible")}
💳 Método: {invoice_info.get("payment_method", "No especificado")}

¿Necesitas el comprobante de pago?"""

        elif invoice_info["status"] == "vencida":
            response += """⚠️ **Factura vencida**

Puedes realizar el pago con recargo mínimo.
¿Te ayudo a procesar el pago ahora?"""

        return response

    def _handle_payment_methods(self) -> str:
        """Maneja consultas sobre métodos de pago."""
        return """💳 **Métodos de Pago Disponibles**

**Tarjetas de Crédito/Débito**
• Visa, Mastercard, American Express
• Hasta 12 cuotas sin interés
• Procesamiento inmediato

**Transferencia Bancaria**
• Descuento 5% por pago contado
• Acreditación en 24-48hs
• CBU: 1234567890123456789012

**Billeteras Digitales**
• 💰 Mercado Pago
• 📱 PayPal
• 🏦 Todo Pago

**Efectivo**
• Rapipago, Pago Fácil
• Comisión 2%
• Hasta 48hs para acreditación

¿Te interesa algún método en particular?"""

    def _handle_payment_issue(self, message: str) -> str:
        """Maneja problemas con pagos."""
        print("message", message)
        return """🔧 **Solución de Problemas de Pago**

**Si tu tarjeta fue rechazada:**
• Verifica fondos disponibles
• Confirma datos ingresados
• Contacta a tu banco
• Intenta con otra tarjeta

**Si el pago no se procesó:**
• Espera 10-15 minutos
• Revisa tu email de confirmación
• Verifica débito en tu cuenta

**Errores comunes:**
• CVV incorrecto
• Fecha de vencimiento incorrecta
• Límite de compras online

¿Cuál es específicamente tu problema? Puedo ayudarte a resolverlo."""

    def _handle_refund_request(self, message: str) -> str:
        print("reembolso", message)
        """Maneja solicitudes de reembolso."""
        return """💰 **Proceso de Reembolso**

**Requisitos:**
• Solicitud dentro de 30 días
• Producto sin uso (condiciones originales)
• Comprobante de compra

**Tiempo de procesamiento:**
• Tarjeta de crédito: 5-10 días hábiles
• Transferencia: 2-3 días hábiles
• Efectivo: Inmediato en sucursal

**Información necesaria:**
• Número de orden
• Motivo del reembolso
• Fotos del producto (si aplica)

¿Tienes el número de orden para iniciar el proceso?"""

    def _handle_tax_info(self) -> str:
        """Maneja consultas sobre información fiscal."""
        return """📊 **Información Fiscal**

**Facturación:**
• Facturas A, B o C según tu condición
• CUIT/CUIL requerido para Factura A
• Consumidor Final para Factura C

**Impuestos incluidos:**
• IVA 21% (productos gravados)
• Impuesto PAIS (productos importados)
• Todos los precios mostrados incluyen impuestos

**Para empresas:**
• Factura A con retenciones aplicables
• Comprobante de inscripción en AFIP
• Condición fiscal actualizada

¿Necesitas modificar tu información fiscal?"""

    def _handle_general_invoice_query(self) -> str:
        """Maneja consultas generales sobre facturación."""
        return """📄 **Centro de Facturación**

Puedo ayudarte con:

• 📊 **Estado de facturas**
• 💳 **Métodos de pago**
• 🔧 **Problemas de pago**
• 💰 **Reembolsos**
• 📋 **Información fiscal**
• 🧾 **Descargar comprobantes**

¿En qué específicamente puedo ayudarte?

Para consultas específicas, proporciona:
• Número de factura o pedido
• Fecha aproximada de compra
• Email asociado a la cuenta"""

    def _get_invoice_info(self, number: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de factura (simulada)."""
        if not number:
            return None

        # Simular datos de factura
        today = datetime.now()
        issue_date = today - timedelta(days=5)
        due_date = issue_date + timedelta(days=30)

        # Simular diferentes estados
        import random

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
                {"payment_date": payment_date.strftime("%d/%m/%Y"), "payment_method": "Tarjeta de crédito"}
            )

        return invoice_data
