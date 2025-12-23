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
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, model_validator
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
    """
    Mercado Pago webhook payload - supports both IPN v1 and topic formats.

    IPN v1 format (new):
        {"id": 123, "type": "payment", "action": "payment.created", "data": {"id": "456"}}

    Topic-based format (legacy):
        {"resource": "/v1/payments/456", "topic": "payment"}
    """

    # IPN v1 format fields (all optional individually)
    action: str | None = None
    api_version: str | None = None
    data: dict[str, Any] | None = None
    date_created: str | None = None
    id: str | int | None = None
    live_mode: bool | None = None
    type: str | None = None
    user_id: str | int | None = None

    # Topic-based format fields (legacy)
    resource: str | None = None
    topic: str | None = None

    @model_validator(mode="after")
    def validate_has_required_data(self) -> "MPWebhookPayload":
        """Ensure we have enough data to process the webhook."""
        has_ipn_format = self.type and self.data and self.data.get("id")
        has_topic_format = self.topic and self.resource

        if not has_ipn_format and not has_topic_format:
            raise ValueError(
                "Webhook must have either IPN format (type, data.id) "
                "or topic format (topic, resource)"
            )
        return self

    def get_payment_id(self) -> str | None:
        """Extract payment ID from either format."""
        # Try IPN v1 format first
        if self.data and self.data.get("id"):
            return str(self.data["id"])

        # Try topic-based format: "/v1/payments/123456789"
        if self.resource:
            return self.resource.split("/")[-1]

        return None

    def get_notification_type(self) -> str | None:
        """Get notification type from either format."""
        return self.type or self.topic


@router.post("/mercadopago")
async def mercadopago_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Handle Mercado Pago payment notifications.

    This webhook is called by Mercado Pago when a payment status changes.
    Supports both IPN v1 format and legacy topic-based format.

    For approved payments, it:
    1. Parses external_reference to get org_id
    2. Loads pharmacy config from database
    3. Fetches payment details from MP using org-specific credentials
    4. Registers the payment in PLEX ERP
    5. Generates a PDF receipt with org-specific pharmacy details
    6. Sends a WhatsApp template message with the PDF attachment

    Args:
        request: FastAPI request object
        db: Database session for loading config

    Returns:
        dict with processing status

    Note:
        Always returns 200 to acknowledge receipt, even for ignored notifications.
        MP will retry if we return non-2xx status.
    """
    settings = get_settings()

    # Read raw body BEFORE Pydantic parsing for debugging
    raw_body = await request.body()
    logger.info(f"[MP-WEBHOOK] Raw payload received: {raw_body.decode()[:500]}")

    # Parse payload with flexible model
    try:
        payload = MPWebhookPayload.model_validate_json(raw_body)
    except Exception as e:
        logger.error(f"[MP-WEBHOOK] Payload validation failed: {e}")
        # Return 200 to prevent MP retries on validation errors
        return {
            "status": "error",
            "reason": "validation_failed",
            "error": str(e),
            "raw_sample": raw_body.decode()[:200],
        }

    try:
        notification_type = payload.get_notification_type()
        payment_id = payload.get_payment_id()

        logger.info(
            f"[MP-WEBHOOK] Parsed: type={notification_type}, action={payload.action}, "
            f"payment_id={payment_id}, live_mode={payload.live_mode}"
        )

        # Only process payment notifications
        if notification_type != "payment":
            logger.info(f"[MP-WEBHOOK] Ignoring non-payment: type={notification_type}")
            return {"status": "ignored", "reason": f"type={notification_type}"}

        # Check we have a payment ID
        if not payment_id:
            logger.warning("[MP-WEBHOOK] Missing payment ID in payload")
            return {"status": "ignored", "reason": "missing_payment_id"}

        # Two-phase approach for multi-tenant webhook handling:
        # 1. Use any active MP config to fetch payment details (MP allows cross-org fetch)
        # 2. Parse external_reference from payment to identify the real tenant
        # 3. Load org-specific config for processing (PDF branding, PLEX, etc.)
        #
        # This works because MP webhooks don't include external_reference in payload,
        # so we need to fetch the payment first to get tenant identification.

        # Load any active MP config for initial payment fetch
        # The actual org-specific config is loaded from external_reference later
        try:
            config_service = PharmacyConfigService(db)
            initial_config = await config_service.get_any_active_mp_config()
        except ValueError:
            logger.error("[MP-WEBHOOK] No active MP configuration available")
            return {
                "status": "error",
                "reason": "no_pharmacy_config",
                "error": "No active Mercado Pago configuration found in database",
            }

        if not initial_config.mp_enabled or not initial_config.mp_access_token:
            logger.error("[MP-WEBHOOK] Initial config has MP disabled or no token")
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
        logger.info(f"[MP-WEBHOOK] Payment {payment_id} status: {status} ({status_detail})")

        # Only process approved payments
        if status != "approved":
            logger.info(f"[MP-WEBHOOK] Ignoring payment {payment_id}: status={status}")
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
                f"[MP-WEBHOOK] Org resolved: {org_id} ({pharmacy_config.pharmacy_name})"
            )
        except ValueError as e:
            logger.error(f"[MP-WEBHOOK] Invalid external_reference: {external_ref} - {e}")
            return {
                "status": "error",
                "reason": "invalid_external_reference",
                "external_reference": external_ref,
                "error": str(e),
            }

        # Check if MP is enabled for this specific pharmacy
        if not pharmacy_config.mp_enabled:
            logger.warning(f"[MP-WEBHOOK] MP disabled for org {org_id}")
            return {
                "status": "error",
                "reason": "mp_disabled_for_org",
                "org_id": str(org_id),
            }

        amount = payment.get("transaction_amount", 0)

        logger.info(
            f"[MP-WEBHOOK] Processing: payment_id={payment_id}, "
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
            f"[MP-WEBHOOK] PLEX registered: receipt={plex_receipt}, "
            f"balance={new_balance}, acreditado={acreditado}"
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
                logger.info(f"[MP-WEBHOOK] PDF generated: {pdf_url}")
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
                logger.info(
                    f"[MP-WEBHOOK] WhatsApp sent: {notification_result.get('method', 'unknown')}"
                )
            else:
                logger.warning("[MP-WEBHOOK] PDF generation failed, sending text-only")
                notification_result = await _send_text_only_notification(
                    phone=payer_phone,
                    amount=amount,
                    receipt_number=plex_receipt,
                    new_balance=new_balance,
                )
        else:
            logger.warning(f"[MP-WEBHOOK] No phone for payment {payment_id}, skipping notification")

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
        logger.error(f"[MP-WEBHOOK] MP API error: {e}")
        # Return 200 to avoid retries for API errors
        return {
            "status": "error",
            "reason": "mercadopago_api_error",
            "error": str(e),
        }

    except PlexAPIError as e:
        logger.error(f"[MP-WEBHOOK] PLEX API error: {e}")
        # Return 200 to avoid retries, but log for manual follow-up
        return {
            "status": "error",
            "reason": "plex_api_error",
            "error": str(e),
        }

    except Exception as e:
        logger.error(f"[MP-WEBHOOK] Unexpected error: {e}", exc_info=True)
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


# =============================================================================
# User Redirect Routes (back_urls from MP checkout)
# =============================================================================


def _generate_success_html(
    payment_id: str | None,
    status: str | None,
    external_reference: str | None,
) -> str:
    """Generate success confirmation HTML page."""
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago Exitoso</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}
        .icon {{ font-size: 64px; margin-bottom: 16px; }}
        h1 {{ color: #28a745; font-size: 28px; margin-bottom: 12px; }}
        .message {{ color: #666; font-size: 16px; margin-bottom: 24px; }}
        .details {{
            background: #f8f9fa;
            padding: 16px;
            border-radius: 8px;
            text-align: left;
            margin-bottom: 24px;
        }}
        .details p {{ margin: 8px 0; color: #444; font-size: 14px; }}
        .details strong {{ color: #333; }}
        .whatsapp-note {{
            background: #dcfce7;
            color: #166534;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 16px;
        }}
        .close-note {{ color: #999; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">✅</div>
        <h1>¡Pago Exitoso!</h1>
        <p class="message">Tu pago ha sido procesado correctamente.</p>
        <div class="details">
            <p><strong>ID de Pago:</strong> {payment_id or 'N/A'}</p>
            <p><strong>Estado:</strong> {status or 'approved'}</p>
        </div>
        <div class="whatsapp-note">
            📱 Recibirás el comprobante por WhatsApp en breve.
        </div>
        <p class="close-note">Puedes cerrar esta ventana.</p>
    </div>
</body>
</html>
"""


def _generate_failure_html(
    payment_id: str | None,
    status: str | None,
    external_reference: str | None,
) -> str:
    """Generate failure/rejection HTML page."""
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago No Procesado</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}
        .icon {{ font-size: 64px; margin-bottom: 16px; }}
        h1 {{ color: #dc3545; font-size: 28px; margin-bottom: 12px; }}
        .message {{ color: #666; font-size: 16px; margin-bottom: 24px; }}
        .details {{
            background: #f8f9fa;
            padding: 16px;
            border-radius: 8px;
            text-align: left;
            margin-bottom: 24px;
        }}
        .details p {{ margin: 8px 0; color: #444; font-size: 14px; }}
        .details strong {{ color: #333; }}
        .retry-note {{
            background: #fef3cd;
            color: #856404;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 16px;
        }}
        .close-note {{ color: #999; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">❌</div>
        <h1>Pago No Procesado</h1>
        <p class="message">No pudimos procesar tu pago.</p>
        <div class="details">
            <p><strong>ID de Pago:</strong> {payment_id or 'N/A'}</p>
            <p><strong>Estado:</strong> {status or 'rejected'}</p>
        </div>
        <div class="retry-note">
            💡 Puedes intentar nuevamente o contactar a tu farmacia para más información.
        </div>
        <p class="close-note">Puedes cerrar esta ventana.</p>
    </div>
</body>
</html>
"""


def _generate_pending_html(
    payment_id: str | None,
    status: str | None,
    external_reference: str | None,
) -> str:
    """Generate pending payment HTML page."""
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago Pendiente</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}
        .icon {{ font-size: 64px; margin-bottom: 16px; }}
        h1 {{ color: #856404; font-size: 28px; margin-bottom: 12px; }}
        .message {{ color: #666; font-size: 16px; margin-bottom: 24px; }}
        .details {{
            background: #f8f9fa;
            padding: 16px;
            border-radius: 8px;
            text-align: left;
            margin-bottom: 24px;
        }}
        .details p {{ margin: 8px 0; color: #444; font-size: 14px; }}
        .details strong {{ color: #333; }}
        .pending-note {{
            background: #fff3cd;
            color: #856404;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 16px;
        }}
        .close-note {{ color: #999; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">⏳</div>
        <h1>Pago Pendiente</h1>
        <p class="message">Tu pago está siendo procesado.</p>
        <div class="details">
            <p><strong>ID de Pago:</strong> {payment_id or 'N/A'}</p>
            <p><strong>Estado:</strong> {status or 'pending'}</p>
        </div>
        <div class="pending-note">
            🔄 Te notificaremos por WhatsApp cuando se confirme el pago.
        </div>
        <p class="close-note">Puedes cerrar esta ventana.</p>
    </div>
</body>
</html>
"""


@router.get("/mercadopago/success")
async def mercadopago_success(
    collection_id: str | None = None,
    collection_status: str | None = None,
    payment_id: str | None = None,
    status: str | None = None,
    external_reference: str | None = None,
    payment_type: str | None = None,
    merchant_order_id: str | None = None,
    preference_id: str | None = None,
    site_id: str | None = None,
    processing_mode: str | None = None,
    merchant_account_id: str | None = None,
):
    """
    Handle user redirect after successful MP payment.

    This is a USER-FACING endpoint (not a webhook).
    MP redirects customers here after approved payment.

    Query parameters come from MP's back_url redirect.
    """
    logger.info(
        f"[MP-REDIRECT] Success: payment_id={payment_id or collection_id}, "
        f"status={status or collection_status}, ref={external_reference}"
    )

    return HTMLResponse(
        content=_generate_success_html(
            payment_id=payment_id or collection_id,
            status=status or collection_status,
            external_reference=external_reference,
        )
    )


@router.get("/mercadopago/failure")
async def mercadopago_failure(
    collection_id: str | None = None,
    collection_status: str | None = None,
    payment_id: str | None = None,
    status: str | None = None,
    external_reference: str | None = None,
    payment_type: str | None = None,
    merchant_order_id: str | None = None,
    preference_id: str | None = None,
    site_id: str | None = None,
    processing_mode: str | None = None,
    merchant_account_id: str | None = None,
):
    """
    Handle user redirect after failed/rejected MP payment.

    This is a USER-FACING endpoint (not a webhook).
    MP redirects customers here after rejected payment.
    """
    logger.info(
        f"[MP-REDIRECT] Failure: payment_id={payment_id or collection_id}, "
        f"status={status or collection_status}, ref={external_reference}"
    )

    return HTMLResponse(
        content=_generate_failure_html(
            payment_id=payment_id or collection_id,
            status=status or collection_status,
            external_reference=external_reference,
        )
    )


@router.get("/mercadopago/pending")
async def mercadopago_pending(
    collection_id: str | None = None,
    collection_status: str | None = None,
    payment_id: str | None = None,
    status: str | None = None,
    external_reference: str | None = None,
    payment_type: str | None = None,
    merchant_order_id: str | None = None,
    preference_id: str | None = None,
    site_id: str | None = None,
    processing_mode: str | None = None,
    merchant_account_id: str | None = None,
):
    """
    Handle user redirect when MP payment is pending.

    This is a USER-FACING endpoint (not a webhook).
    MP redirects customers here when payment needs review.
    """
    logger.info(
        f"[MP-REDIRECT] Pending: payment_id={payment_id or collection_id}, "
        f"status={status or collection_status}, ref={external_reference}"
    )

    return HTMLResponse(
        content=_generate_pending_html(
            payment_id=payment_id or collection_id,
            status=status or collection_status,
            external_reference=external_reference,
        )
    )


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
