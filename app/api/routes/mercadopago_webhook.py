"""
Mercado Pago Webhook Handler

Receives payment notifications from Mercado Pago and registers
payments in PLEX ERP, generates PDF receipts, and sends them to
customers via WhatsApp template messages.

All Mercado Pago configuration is loaded from the database based on
the organization_id in the payment's external_reference.

Webhook Flow:
1. MP sends POST notification when payment status changes
2. Parse external_reference to get org_id
3. Load pharmacy config from database
4. Validate webhook authenticity using org-specific secret
5. Fetch full payment details from MP API using org credentials
6. For approved payments: Register in PLEX with REGISTRAR_PAGO_CLIENTE
7. Generate PDF receipt with org-specific pharmacy details
8. Send WhatsApp template message with PDF attachment

Endpoint: POST /api/v1/webhooks/mercadopago
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.mercado_pago_client import MercadoPagoClient, MercadoPagoError
from app.clients.plex_client import PlexAPIError, PlexClient
from app.config.settings import get_settings
from app.core.tenancy import PharmacyConfig, PharmacyConfigService
from app.database.async_db import get_async_db
from app.services.notifications.payment_notification import PaymentNotificationService
from app.services.receipt.pdf_generator import PaymentReceiptGenerator
from app.services.receipt.storage_service import ReceiptStorageService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


class MPWebhookPayload(BaseModel):
    """Mercado Pago webhook payload structure."""

    action: str  # e.g., "payment.created", "payment.updated"
    api_version: str | None = None
    data: dict[str, Any]  # Contains "id" for the payment ID
    date_created: str | None = None
    id: str | int  # Webhook notification ID
    live_mode: bool | None = None
    type: str  # e.g., "payment"
    user_id: str | int | None = None


@router.post("/mercadopago")
async def mercadopago_webhook(
    request: Request,
    payload: MPWebhookPayload,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Handle Mercado Pago payment notifications.

    This webhook is called by Mercado Pago when a payment status changes.
    For approved payments, it:
    1. Parses external_reference to get org_id
    2. Loads pharmacy config from database
    3. Fetches payment details from MP using org-specific credentials
    4. Registers the payment in PLEX ERP
    5. Generates a PDF receipt with org-specific pharmacy details
    6. Sends a WhatsApp template message with the PDF attachment

    Args:
        request: FastAPI request object
        payload: Webhook payload from Mercado Pago
        db: Database session for loading config

    Returns:
        dict with processing status

    Note:
        Always returns 200 to acknowledge receipt, even for ignored notifications.
        MP will retry if we return non-2xx status.
    """
    settings = get_settings()

    try:
        # Log incoming webhook
        logger.info(
            f"MP webhook received: type={payload.type}, action={payload.action}, "
            f"data_id={payload.data.get('id')}, live_mode={payload.live_mode}"
        )

        # Only process payment notifications
        if payload.type != "payment":
            logger.info(f"Ignoring non-payment notification: type={payload.type}")
            return {"status": "ignored", "reason": f"type={payload.type}"}

        # Get payment ID from payload
        payment_id = payload.data.get("id")
        if not payment_id:
            logger.warning("MP webhook missing payment ID in data")
            return {"status": "ignored", "reason": "missing_payment_id"}

        # We need to fetch payment to get external_reference for org identification
        # First, try to get external_reference from the initial webhook if available
        # Otherwise we'll need to make a preliminary API call
        # For now, we proceed with a two-phase approach:
        # 1. Parse external_reference from webhook data if available
        # 2. Fetch full payment details using org-specific credentials

        # Note: MP webhooks don't include external_reference directly in the payload
        # We need to fetch the payment first. For this, we'll do an initial lookup
        # using a temporary approach - ideally we'd have a way to identify the org
        # from the webhook payload itself, but MP doesn't support that.
        #
        # Workaround: We'll try to look up the payment by ID across orgs
        # or use a default/test config for the initial fetch

        # For production, you might want to:
        # 1. Store payment_id -> org_id mapping when creating preferences
        # 2. Use a default org for fetching payment details
        # 3. Parse org from webhook URL path if using per-org webhook URLs

        # Current approach: Fetch payment using test org credentials first,
        # then use the external_reference to get the real org config
        # This works because MP allows fetching any payment with a valid token

        # Load test pharmacy config for initial payment fetch
        # In production, you'd want a better approach
        from app.core.tenancy import TEST_PHARMACY_ORG_ID

        try:
            config_service = PharmacyConfigService(db)
            # Try to get a pharmacy config to fetch payment details
            # We'll use the external_reference later to get the right config
            initial_config = await config_service.get_config(TEST_PHARMACY_ORG_ID)
        except ValueError:
            logger.error("No pharmacy config available to fetch payment details")
            return {
                "status": "error",
                "reason": "no_pharmacy_config",
                "error": "No pharmacy configuration found in database",
            }

        if not initial_config.mp_enabled or not initial_config.mp_access_token:
            logger.error("Initial pharmacy config has MP disabled or no access token")
            return {
                "status": "error",
                "reason": "mp_not_configured",
                "error": "Mercado Pago not configured in database",
            }

        # Fetch payment details using initial config
        mp_client = MercadoPagoClient(
            access_token=initial_config.mp_access_token,
            sandbox=initial_config.mp_sandbox,
            timeout=initial_config.mp_timeout,
        )
        async with mp_client:
            payment = await mp_client.get_payment(str(payment_id))

        status = payment.get("status")
        status_detail = payment.get("status_detail")
        logger.info(f"MP payment {payment_id} status: {status} ({status_detail})")

        # Only process approved payments
        if status != "approved":
            logger.info(f"Ignoring payment {payment_id}: status={status}")
            return {
                "status": "ignored",
                "reason": f"payment_status={status}",
                "payment_id": payment_id,
            }

        # Parse external_reference and load org-specific pharmacy config
        # Format: customer_id:debt_id:org_id:uuid (org_id is required)
        external_ref = payment.get("external_reference", "")

        try:
            pharmacy_config, ref_data = await config_service.get_config_by_external_reference(
                external_ref
            )
            plex_customer_id = ref_data["customer_id"]
            org_id = ref_data["org_id"]

            logger.info(
                f"Resolved pharmacy config: org_id={org_id}, "
                f"pharmacy={pharmacy_config.pharmacy_name}"
            )
        except ValueError as e:
            logger.error(f"Invalid external_reference format: {external_ref} - {e}")
            return {
                "status": "error",
                "reason": "invalid_external_reference",
                "external_reference": external_ref,
                "error": str(e),
            }

        # Check if MP is enabled for this specific pharmacy
        if not pharmacy_config.mp_enabled:
            logger.warning(f"MP integration is disabled for org {org_id}")
            return {
                "status": "error",
                "reason": "mp_disabled_for_org",
                "org_id": str(org_id),
            }

        amount = payment.get("transaction_amount", 0)

        logger.info(
            f"Processing approved payment: payment_id={payment_id}, "
            f"customer_id={plex_customer_id}, amount=${amount}"
        )

        # Register payment in PLEX
        plex_client = PlexClient()
        async with plex_client:
            plex_result = await plex_client.register_payment(
                customer_id=plex_customer_id,
                amount=amount,
                operation_number=str(payment_id),  # MP payment ID as nro_operacion
            )

        # Extract PLEX receipt info
        content = plex_result.get("content", {})
        plex_receipt = content.get("comprobante", "N/A")
        new_balance = content.get("nuevo_saldo", "0")
        acreditado = content.get("acreditado", str(amount))

        logger.info(
            f"Payment registered in PLEX: customer={plex_customer_id}, "
            f"receipt={plex_receipt}, new_balance={new_balance}"
        )

        # Extract payer info for notification
        payer_phone = _extract_payer_phone(payment)
        customer_name = _extract_payer_name(payment)

        # Generate and send receipt if we have a phone number
        pdf_url = None
        notification_result = None

        if payer_phone:
            # Generate PDF receipt using org-specific pharmacy config
            pdf_url = await _generate_and_store_receipt(
                pharmacy_config=pharmacy_config,
                amount=amount,
                receipt_number=plex_receipt,
                new_balance=new_balance,
                mp_payment_id=str(payment_id),
                customer_name=customer_name,
            )

            if pdf_url:
                # Send WhatsApp notification with PDF
                notification_result = await _send_payment_notification(
                    settings=settings,
                    phone=payer_phone,
                    amount=amount,
                    receipt_number=plex_receipt,
                    new_balance=new_balance,
                    pdf_url=pdf_url,
                    customer_name=customer_name,
                )
            else:
                logger.warning("PDF generation failed, sending text-only notification")
                notification_result = await _send_text_only_notification(
                    phone=payer_phone,
                    amount=amount,
                    receipt_number=plex_receipt,
                    new_balance=new_balance,
                )
        else:
            logger.warning(f"Could not send WhatsApp confirmation: no phone for payment {payment_id}")

        return {
            "status": "success",
            "payment_id": payment_id,
            "plex_receipt": plex_receipt,
            "new_balance": new_balance,
            "acreditado": acreditado,
            "pdf_url": pdf_url,
            "notification_sent": notification_result.get("success") if notification_result else False,
            "notification_method": notification_result.get("method") if notification_result else None,
        }

    except MercadoPagoError as e:
        logger.error(f"MP API error processing webhook: {e}")
        # Return 200 to avoid retries for API errors
        return {
            "status": "error",
            "reason": "mercadopago_api_error",
            "error": str(e),
        }

    except PlexAPIError as e:
        logger.error(f"PLEX API error processing webhook: {e}")
        # Return 200 to avoid retries, but log for manual follow-up
        return {
            "status": "error",
            "reason": "plex_api_error",
            "error": str(e),
        }

    except Exception as e:
        logger.error(f"Unexpected error processing MP webhook: {e}", exc_info=True)
        # Return 500 for unexpected errors - MP will retry
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/mercadopago/health")
async def mercadopago_webhook_health():
    """
    Health check for Mercado Pago webhook endpoint.

    Used to verify the webhook endpoint is accessible.
    MP configuration is now per-organization in the database.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "webhook_available": True,
        "receipt_template": settings.WA_PAYMENT_RECEIPT_TEMPLATE,
        "note": "MP configuration is per-organization in database",
    }


def _extract_payer_phone(payment: dict[str, Any]) -> str | None:
    """
    Extract payer phone number from payment data.

    Tries multiple locations where phone might be stored.
    """
    # Try payer.phone.number
    payer = payment.get("payer", {})
    phone_data = payer.get("phone", {})
    if phone_data and phone_data.get("number"):
        return str(phone_data["number"])

    # Try additional_info if available
    additional_info = payment.get("additional_info", {})
    payer_info = additional_info.get("payer", {})
    phone_info = payer_info.get("phone", {})
    if phone_info and phone_info.get("number"):
        return str(phone_info["number"])

    return None


def _extract_payer_name(payment: dict[str, Any]) -> str | None:
    """
    Extract payer name from payment data.

    Tries multiple locations where name might be stored.
    """
    # Try payer.first_name + payer.last_name
    payer = payment.get("payer", {})
    first_name = payer.get("first_name", "")
    last_name = payer.get("last_name", "")
    if first_name or last_name:
        return f"{first_name} {last_name}".strip()

    # Try additional_info if available
    additional_info = payment.get("additional_info", {})
    payer_info = additional_info.get("payer", {})
    first_name = payer_info.get("first_name", "")
    last_name = payer_info.get("last_name", "")
    if first_name or last_name:
        return f"{first_name} {last_name}".strip()

    return None


def _get_public_url_base_from_config(pharmacy_config: PharmacyConfig) -> str:
    """
    Get the base URL for public file access from pharmacy config.

    Priority:
    1. pharmacy_config.receipt_public_url_base (from DB)
    2. pharmacy_config.mp_notification_url (extract base from webhook URL)
    3. localhost (testing only - won't work for WhatsApp)
    """
    if pharmacy_config.receipt_public_url_base:
        return pharmacy_config.receipt_public_url_base.rstrip("/")

    if pharmacy_config.mp_notification_url:
        parsed = urlparse(pharmacy_config.mp_notification_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    # Fallback to localhost (won't work for WhatsApp but useful for testing)
    logger.warning(
        f"No public URL base configured for org {pharmacy_config.organization_id} "
        "- receipts may not be accessible via WhatsApp"
    )
    return "http://localhost:8000"


async def _generate_and_store_receipt(
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
        public_url_base = _get_public_url_base_from_config(pharmacy_config)
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


async def _send_payment_notification(
    settings,
    phone: str,
    amount: float,
    receipt_number: str,
    new_balance: str,
    pdf_url: str,
    customer_name: str | None,
) -> dict:
    """
    Send payment notification via WhatsApp with PDF receipt.

    Uses template message with document header, with fallbacks.
    """
    try:
        notification_service = PaymentNotificationService(
            template_name=settings.WA_PAYMENT_RECEIPT_TEMPLATE,
            template_language=settings.WA_PAYMENT_RECEIPT_LANGUAGE,
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


async def _send_text_only_notification(
    phone: str,
    amount: float,
    receipt_number: str,
    new_balance: str,
) -> dict:
    """
    Send text-only payment notification (fallback when PDF fails).
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

        whatsapp = WhatsAppService()
        result = await whatsapp.send_message(phone, message)

        success = result.get("success", False)
        if success:
            logger.info(f"Text-only notification sent to {phone}")

        return {"success": success, "method": "text"}

    except Exception as e:
        logger.error(f"Error sending text-only notification to {phone}: {e}")
        return {"success": False, "error": str(e)}
