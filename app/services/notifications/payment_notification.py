"""
Payment Notification Service

Handles sending payment confirmation notifications via WhatsApp.
Supports both template messages (with document header) and fallback to regular messages.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from app.integrations.whatsapp.service import WhatsAppService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PaymentNotificationService:
    """
    Service for sending payment confirmation notifications.

    Provides methods to send payment receipts via WhatsApp using:
    1. Template messages with document header (primary)
    2. Regular document message (fallback)
    3. Text-only message (last resort fallback)
    """

    def __init__(
        self,
        whatsapp_service: WhatsAppService | None = None,
        template_name: str = "payment_receipt",
        template_language: str = "es",
        db_session: "AsyncSession | None" = None,
        chattigo_did: str | None = None,
    ):
        """
        Initialize the payment notification service.

        Args:
            whatsapp_service: WhatsApp service instance (creates new if None)
            template_name: Name of the WhatsApp template for payment receipts
            template_language: Language code for the template
            db_session: Database session for WhatsApp credential lookup
            chattigo_did: Chattigo DID for sending messages
        """
        if whatsapp_service:
            self._whatsapp = whatsapp_service
        elif db_session and chattigo_did:
            # Create WhatsApp service with credentials
            chattigo_context = {"did": chattigo_did}
            self._whatsapp = WhatsAppService(
                chattigo_context=chattigo_context,
                db_session=db_session,
            )
        else:
            raise ValueError(
                "Either whatsapp_service or (db_session and chattigo_did) must be provided"
            )
        self.template_name = template_name
        self.template_language = template_language

    async def send_payment_receipt(
        self,
        phone: str,
        amount: float | Decimal,
        receipt_number: str,
        new_balance: float | Decimal | str,
        pdf_url: str,
        customer_name: str | None = None,
    ) -> dict:
        """
        Send a payment receipt notification via WhatsApp.

        Tries template message first, falls back to document message if template fails.

        Args:
            phone: Customer's WhatsApp phone number
            amount: Payment amount
            receipt_number: PLEX receipt number (e.g., "RC X 0001-00016790")
            new_balance: Customer's new balance after payment
            pdf_url: Public URL of the PDF receipt
            customer_name: Optional customer name

        Returns:
            Dict with success status and details
        """
        # Format amounts for display
        amount_str = self._format_amount(amount)
        balance_str = self._format_balance(new_balance)

        # Create safe filename
        safe_receipt_number = receipt_number.replace(" ", "_").replace("/", "-")
        filename = f"Recibo_{safe_receipt_number}.pdf"

        logger.info(
            f"Sending payment receipt to {phone}: "
            f"amount={amount_str}, receipt={receipt_number}"
        )

        # Try template message first (preferred)
        try:
            result = await self._send_template_receipt(
                phone=phone,
                amount_str=amount_str,
                receipt_number=receipt_number,
                balance_str=balance_str,
                pdf_url=pdf_url,
                filename=filename,
            )

            if result.get("success"):
                logger.info(f"Payment receipt sent via template to {phone}")
                return {
                    "success": True,
                    "method": "template",
                    "phone": phone,
                    "receipt_number": receipt_number,
                }

            logger.warning(f"Template send failed: {result.get('error')}, trying document fallback")

        except Exception as e:
            logger.warning(f"Template send error: {e}, trying document fallback")

        # Fallback to regular document message
        try:
            result = await self._send_document_receipt(
                phone=phone,
                amount_str=amount_str,
                receipt_number=receipt_number,
                balance_str=balance_str,
                pdf_url=pdf_url,
                filename=filename,
                customer_name=customer_name,
            )

            if result.get("success"):
                logger.info(f"Payment receipt sent via document to {phone}")
                return {
                    "success": True,
                    "method": "document",
                    "phone": phone,
                    "receipt_number": receipt_number,
                }

            logger.warning(f"Document send failed: {result.get('error')}, trying text fallback")

        except Exception as e:
            logger.warning(f"Document send error: {e}, trying text fallback")

        # Last resort: text-only message
        try:
            result = await self._send_text_receipt(
                phone=phone,
                amount_str=amount_str,
                receipt_number=receipt_number,
                balance_str=balance_str,
                pdf_url=pdf_url,
            )

            if result.get("success"):
                logger.info(f"Payment receipt sent via text to {phone}")
                return {
                    "success": True,
                    "method": "text",
                    "phone": phone,
                    "receipt_number": receipt_number,
                }

        except Exception as e:
            logger.error(f"Text send error: {e}")

        # All methods failed
        logger.error(f"Failed to send payment receipt to {phone}")
        return {
            "success": False,
            "method": None,
            "phone": phone,
            "receipt_number": receipt_number,
            "error": "All notification methods failed",
        }

    async def _send_template_receipt(
        self,
        phone: str,
        amount_str: str,
        receipt_number: str,
        balance_str: str,
        pdf_url: str,
        filename: str,
    ) -> dict:
        """Send receipt using WhatsApp template with document header."""
        body_params = [amount_str, receipt_number, balance_str]

        return await self._whatsapp.enviar_template_con_documento(
            numero=phone,
            template_name=self.template_name,
            document_url=pdf_url,
            document_filename=filename,
            body_params=body_params,
            language_code=self.template_language,
        )

    async def _send_document_receipt(
        self,
        phone: str,
        amount_str: str,
        receipt_number: str,
        balance_str: str,
        pdf_url: str,
        filename: str,
        customer_name: str | None = None,
    ) -> dict:
        """Send receipt as document message with caption."""
        # First send text summary
        greeting = f"Hola{' ' + customer_name if customer_name else ''}!"
        text_message = f"""{greeting}

Tu pago ha sido procesado exitosamente.

**Monto pagado:** {amount_str}
**Comprobante:** {receipt_number}
**Nuevo saldo:** {balance_str}

Te adjuntamos tu comprobante de pago."""

        await self._whatsapp.enviar_mensaje_texto(phone, text_message)

        # Then send document
        caption = f"Comprobante de pago - {receipt_number}"
        return await self._whatsapp.enviar_documento(
            numero=phone,
            nombre=filename,
            document_url=pdf_url,
            caption=caption,
        )

    async def _send_text_receipt(
        self,
        phone: str,
        amount_str: str,
        receipt_number: str,
        balance_str: str,
        pdf_url: str,
    ) -> dict:
        """Send text-only receipt notification (last resort)."""
        message = f"""**Pago Recibido**

Tu pago ha sido procesado exitosamente.

**Monto pagado:** {amount_str}
**Comprobante:** {receipt_number}
**Nuevo saldo:** {balance_str}

Puedes descargar tu comprobante en:
{pdf_url}

Gracias por tu pago. Si tienes alguna pregunta, escribe *AYUDA*."""

        return await self._whatsapp.enviar_mensaje_texto(phone, message)

    def _format_amount(self, amount: float | Decimal) -> str:
        """Format amount for display."""
        try:
            amount_float = float(amount) if isinstance(amount, Decimal) else amount
            return f"${amount_float:,.2f}"
        except (ValueError, TypeError):
            return f"${amount}"

    def _format_balance(self, balance: float | Decimal | str) -> str:
        """Format balance for display."""
        try:
            if isinstance(balance, str):
                balance = float(balance.replace(",", ".").replace(" ", ""))
            balance_float = float(balance) if isinstance(balance, Decimal) else balance

            if balance_float < 0:
                return f"-${abs(balance_float):,.2f}"
            return f"${balance_float:,.2f}"
        except (ValueError, TypeError):
            return f"${balance}"
