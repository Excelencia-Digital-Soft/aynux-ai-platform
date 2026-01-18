"""
Receipt generation and notification workflow for MercadoPago payments.

Orchestrates the PDF receipt generation, storage, and WhatsApp notification
delivery for approved payments.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.config.settings import get_settings
from app.services.mercadopago.payment_mapper import MercadoPagoPaymentMapper
from app.services.notifications.payment_notification import PaymentNotificationService
from app.services.receipt.pdf_generator import PaymentReceiptGenerator
from app.services.receipt.storage_service import ReceiptStorageService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.tenancy import PharmacyConfig

logger = logging.getLogger(__name__)


async def generate_and_store_receipt(
    pharmacy_config: PharmacyConfig,
    amount: float,
    receipt_number: str,
    new_balance: str,
    mp_payment_id: str,
    customer_name: str | None,
) -> str | None:
    """
    Generate a PDF receipt and store it.

    Args:
        pharmacy_config: Pharmacy configuration from database
        amount: Payment amount
        receipt_number: PLEX receipt number
        new_balance: Customer's new balance after payment
        mp_payment_id: MercadoPago payment ID
        customer_name: Optional customer name

    Returns:
        Public URL of the stored PDF, or None if generation failed
    """
    try:
        # Create PDF generator with org-specific pharmacy info
        pdf_generator = PaymentReceiptGenerator(
            pharmacy_name=pharmacy_config.pharmacy_name,
            pharmacy_address=pharmacy_config.pharmacy_address,
            pharmacy_phone=pharmacy_config.pharmacy_phone,
            logo_path=pharmacy_config.pharmacy_logo_path,
        )

        # Generate PDF
        pdf_bytes = pdf_generator.generate(
            amount=amount,
            receipt_number=receipt_number,
            new_balance=new_balance,
            mp_payment_id=mp_payment_id,
            customer_name=customer_name,
            payment_date=datetime.now(UTC),
        )

        # Store PDF and get URL from pharmacy config
        settings = get_settings()
        public_url_base = MercadoPagoPaymentMapper.get_public_url_base(pharmacy_config)
        storage = ReceiptStorageService(
            storage_path=settings.RECEIPT_STORAGE_PATH,
            public_url_base=public_url_base,
        )

        pdf_url = storage.store(pdf_bytes, mp_payment_id)
        logger.info(f"Receipt PDF stored: {pdf_url}")

        return pdf_url

    except Exception as e:
        logger.error(f"Error generating/storing receipt PDF: {e}", exc_info=True)
        return None


async def send_payment_notification(
    phone: str,
    amount: float,
    receipt_number: str,
    new_balance: str,
    pdf_url: str,
    customer_name: str | None,
    db_session: "AsyncSession",
    chattigo_did: str,
    template_name: str | None = None,
    template_language: str | None = None,
) -> dict[str, Any]:
    """
    Send payment notification via WhatsApp with PDF receipt.

    Uses template message with document header, with fallbacks.

    Args:
        phone: Customer phone number
        amount: Payment amount
        receipt_number: PLEX receipt number
        new_balance: Customer's new balance
        pdf_url: URL to the PDF receipt
        customer_name: Optional customer name
        db_session: Database session for WhatsApp credential lookup
        chattigo_did: Chattigo DID for sending messages
        template_name: WhatsApp template name (optional, uses settings default)
        template_language: Template language (optional, uses settings default)

    Returns:
        Dict with success status and method used
    """
    try:
        settings = get_settings()
        notification_service = PaymentNotificationService(
            template_name=template_name or settings.WA_PAYMENT_RECEIPT_TEMPLATE,
            template_language=template_language or settings.WA_PAYMENT_RECEIPT_LANGUAGE,
            db_session=db_session,
            chattigo_did=chattigo_did,
        )

        result = await notification_service.send_payment_receipt(
            phone=phone,
            amount=amount,
            receipt_number=receipt_number,
            new_balance=new_balance,
            pdf_url=pdf_url,
            customer_name=customer_name,
        )

        if result.get("success"):
            logger.info(f"Payment notification sent to {phone} via {result.get('method')}")
        else:
            logger.warning(f"Payment notification failed for {phone}: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"Error sending payment notification to {phone}: {e}")
        return {"success": False, "error": str(e)}


async def send_text_only_notification(
    phone: str,
    amount: float,
    receipt_number: str,
    new_balance: str,
    db_session: "AsyncSession",
    chattigo_did: str,
) -> dict[str, Any]:
    """
    Send text-only payment notification (fallback when PDF fails).

    Args:
        phone: Customer phone number
        amount: Payment amount
        receipt_number: PLEX receipt number
        new_balance: Customer's new balance
        db_session: Database session for WhatsApp credential lookup
        chattigo_did: Chattigo DID for sending messages

    Returns:
        Dict with success status and method used
    """
    try:
        from app.integrations.whatsapp.service import WhatsAppService

        # Format balance for display
        try:
            balance_float = float(str(new_balance).replace(",", ".").replace(" ", ""))
            balance_str = f"${balance_float:,.2f}"
        except (ValueError, AttributeError):
            balance_str = f"${new_balance}"

        message = f"""**Pago Recibido**

Tu pago ha sido procesado exitosamente.

**Monto pagado:** ${amount:,.2f}
**Comprobante:** {receipt_number}
**Nuevo saldo:** {balance_str}

Gracias por tu pago. Si tienes alguna pregunta, escribe *AYUDA*."""

        # Create WhatsApp service with credentials
        chattigo_context = {"did": chattigo_did}
        whatsapp = WhatsAppService(
            chattigo_context=chattigo_context,
            db_session=db_session,
        )
        result = await whatsapp.send_message(phone, message)

        success = result.get("success", False)
        if success:
            logger.info(f"Text-only notification sent to {phone}")

        return {"success": success, "method": "text"}

    except Exception as e:
        logger.error(f"Error sending text-only notification to {phone}: {e}")
        return {"success": False, "error": str(e)}
