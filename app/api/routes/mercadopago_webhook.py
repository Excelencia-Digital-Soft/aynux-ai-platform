"""
Mercado Pago Webhook Handler

Receives payment notifications from Mercado Pago and registers
payments in PLEX ERP, generates PDF receipts, and sends them to
customers via WhatsApp template messages.

All Mercado Pago configuration is loaded from the database based on
the pharmacy_id in the payment's external_reference.

Webhook Flow:
1. MP sends POST notification when payment status changes
2. Parse external_reference to get pharmacy_id
3. Load pharmacy config from database by pharmacy_id
4. Validate webhook authenticity using org-specific secret
5. Fetch full payment details from MP API using org credentials
6. For approved payments: Register in PLEX with REGISTRAR_PAGO_CLIENTE
7. Generate PDF receipt with org-specific pharmacy details
8. Send WhatsApp template message with PDF attachment

Endpoint: POST /api/v1/webhooks/mercadopago
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.mercado_pago_client import MercadoPagoClient, MercadoPagoError
from app.clients.plex_client import PlexAPIError, PlexClient
from app.config.settings import get_settings
from app.core.tenancy import PharmacyConfigService
from app.database.async_db import get_async_db
from app.services.mercadopago import (
    MercadoPagoPaymentMapper,
    MercadoPagoResponsePages,
    generate_and_store_receipt,
    get_idempotency_service,
    send_payment_notification,
    send_text_only_notification,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


def validate_mp_signature(
    payload: bytes,
    signature_header: str | None,
    secret: str | None,
    data_id: str | None = None,
) -> bool:
    """
    Validate Mercado Pago webhook signature.

    MP sends signature in x-signature header with format:
    ts=<timestamp>,v1=<hmac_hash>

    The signed template varies by webhook type. For payment notifications:
    - template_id: manifest_id.payment_id (or just data.id)
    - signed_data: "id:{template_id};request-id:{x-request-id};ts:{ts};"

    Note: We use a simplified validation that checks the data.id and timestamp.

    Args:
        payload: Raw request body
        signature_header: Value of x-signature header
        secret: Webhook secret from pharmacy config
        data_id: The data.id from the webhook payload

    Returns:
        True if signature is valid or validation is disabled, False otherwise
    """
    # If no secret configured, skip validation (but log warning)
    if not secret:
        logger.warning("[MP-WEBHOOK] No webhook secret configured, skipping signature validation")
        return True

    # If no signature header, fail if secret is configured
    if not signature_header:
        logger.warning("[MP-WEBHOOK] Missing x-signature header but secret is configured")
        return False

    # Parse signature header: ts=<timestamp>,v1=<hash>
    try:
        sig_parts: dict[str, str] = {}
        for part in signature_header.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                sig_parts[key.strip()] = value.strip()

        ts = sig_parts.get("ts")
        v1 = sig_parts.get("v1")

        if not ts or not v1:
            logger.warning(f"[MP-WEBHOOK] Invalid signature format: {signature_header}")
            return False

        # Build the signed template
        # MP signs: "id:{data_id};request-id:{request_id};ts:{ts};"
        # Simplified: We use just the data_id and timestamp
        if data_id:
            template = f"id:{data_id};ts:{ts};"
        else:
            template = f"ts:{ts};"

        # Calculate expected HMAC-SHA256
        expected = hmac.new(
            secret.encode("utf-8"),
            template.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Compare signatures (constant-time comparison)
        is_valid = hmac.compare_digest(expected, v1)

        if not is_valid:
            logger.warning(
                f"[MP-WEBHOOK] Signature mismatch. Expected: {expected[:16]}..., Got: {v1[:16]}..."
            )
        else:
            logger.debug("[MP-WEBHOOK] Signature validation successful")

        return is_valid

    except Exception as e:
        logger.error(f"[MP-WEBHOOK] Signature validation error: {e}")
        return False


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
        if self.data and self.data.get("id"):
            return str(self.data["id"])
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

    For approved payments:
    1. Parses external_reference to get org_id
    2. Loads pharmacy config from database
    3. Fetches payment details from MP
    4. Registers the payment in PLEX ERP
    5. Generates a PDF receipt
    6. Sends a WhatsApp notification

    Note: Always returns 200 to acknowledge receipt. MP retries on non-2xx.
    """
    settings = get_settings()

    raw_body = await request.body()
    logger.info(f"[MP-WEBHOOK] Raw payload received: {raw_body.decode()[:500]}")

    try:
        payload = MPWebhookPayload.model_validate_json(raw_body)
    except Exception as e:
        logger.error(f"[MP-WEBHOOK] Payload validation failed: {e}")
        return {
            "status": "error",
            "reason": "validation_failed",
            "error": str(e),
            "raw_sample": raw_body.decode()[:200],
        }

    # Initialize variables for exception handlers
    idempotency = None
    payment_id: str | None = None

    try:
        notification_type = payload.get_notification_type()
        payment_id = payload.get_payment_id()

        logger.info(
            f"[MP-WEBHOOK] Parsed: type={notification_type}, action={payload.action}, "
            f"payment_id={payment_id}, live_mode={payload.live_mode}"
        )

        if notification_type != "payment":
            logger.info(f"[MP-WEBHOOK] Ignoring non-payment: type={notification_type}")
            return {"status": "ignored", "reason": f"type={notification_type}"}

        if not payment_id:
            logger.warning("[MP-WEBHOOK] Missing payment ID in payload")
            return {"status": "ignored", "reason": "missing_payment_id"}

        # Load any active MP config for initial payment fetch
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

        # Fetch payment details
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

        if status != "approved":
            logger.info(f"[MP-WEBHOOK] Ignoring payment {payment_id}: status={status}")
            return {"status": "ignored", "reason": f"payment_status={status}", "payment_id": payment_id}

        # Parse external_reference and load pharmacy-specific config
        external_ref = payment.get("external_reference", "")

        try:
            pharmacy_config, ref_data = await config_service.get_config_by_external_reference(
                external_ref
            )
            plex_customer_id = ref_data["customer_id"]
            org_id = pharmacy_config.organization_id  # Get org_id from config
            logger.info(f"[MP-WEBHOOK] Org resolved: {org_id} ({pharmacy_config.pharmacy_name})")
        except ValueError as e:
            logger.error(f"[MP-WEBHOOK] Invalid external_reference: {external_ref} - {e}")
            return {
                "status": "error",
                "reason": "invalid_external_reference",
                "external_reference": external_ref,
                "error": str(e),
            }

        # Validate webhook signature (Security Improvement)
        signature_header = request.headers.get("x-signature")
        if not validate_mp_signature(
            payload=raw_body,
            signature_header=signature_header,
            secret=pharmacy_config.mp_webhook_secret,
            data_id=payment_id,
        ):
            logger.warning(f"[MP-WEBHOOK] Invalid signature for payment {payment_id}")
            return {
                "status": "error",
                "reason": "invalid_signature",
                "payment_id": payment_id,
            }

        if not pharmacy_config.mp_enabled:
            logger.warning(f"[MP-WEBHOOK] MP disabled for org {org_id}")
            return {"status": "error", "reason": "mp_disabled_for_org", "org_id": str(org_id)}

        # Check for duplicate payment (idempotency)
        try:
            idempotency = await get_idempotency_service()
            is_duplicate, previous_receipt = await idempotency.check_and_lock(str(payment_id))

            if is_duplicate:
                logger.info(
                    f"[MP-WEBHOOK] Duplicate payment {payment_id}, "
                    f"previous receipt: {previous_receipt}"
                )
                return {
                    "status": "duplicate",
                    "payment_id": payment_id,
                    "previous_receipt": previous_receipt,
                    "reason": "already_processed",
                }
        except Exception as e:
            # Log but don't fail - idempotency is a safety net, not critical
            logger.warning(f"[MP-WEBHOOK] Idempotency check failed: {e}")
            idempotency = None

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
                operation_number=str(payment_id),
            )

        content = plex_result.get("content", {})
        plex_receipt = content.get("comprobante", "N/A")
        new_balance = content.get("nuevo_saldo", "0")
        acreditado = content.get("acreditado", str(amount))

        logger.info(
            f"[MP-WEBHOOK] PLEX registered: receipt={plex_receipt}, "
            f"balance={new_balance}, acreditado={acreditado}"
        )

        # Extract payer info and send notification
        payer_phone = MercadoPagoPaymentMapper.extract_payer_phone(payment)
        customer_name = MercadoPagoPaymentMapper.extract_payer_name(payment)

        pdf_url = None
        notification_result = None

        if payer_phone:
            pdf_url = await generate_and_store_receipt(
                pharmacy_config=pharmacy_config,
                amount=amount,
                receipt_number=plex_receipt,
                new_balance=new_balance,
                mp_payment_id=str(payment_id),
                customer_name=customer_name,
            )

            if pdf_url:
                logger.info(f"[MP-WEBHOOK] PDF generated: {pdf_url}")
                notification_result = await send_payment_notification(
                    phone=payer_phone,
                    amount=amount,
                    receipt_number=plex_receipt,
                    new_balance=new_balance,
                    pdf_url=pdf_url,
                    customer_name=customer_name,
                    template_name=settings.WA_PAYMENT_RECEIPT_TEMPLATE,
                    template_language=settings.WA_PAYMENT_RECEIPT_LANGUAGE,
                )
                logger.info(f"[MP-WEBHOOK] WhatsApp sent: {notification_result.get('method', 'unknown')}")
            else:
                logger.warning("[MP-WEBHOOK] PDF generation failed, sending text-only")
                notification_result = await send_text_only_notification(
                    phone=payer_phone,
                    amount=amount,
                    receipt_number=plex_receipt,
                    new_balance=new_balance,
                )
        else:
            logger.warning(f"[MP-WEBHOOK] No phone for payment {payment_id}, skipping notification")

        # Mark payment as successfully processed (idempotency)
        if idempotency:
            try:
                await idempotency.mark_complete(str(payment_id), plex_receipt)
            except Exception as e:
                logger.warning(f"[MP-WEBHOOK] Failed to mark payment complete: {e}")

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
        # Release idempotency lock to allow retry
        if idempotency and payment_id:
            try:
                await idempotency.mark_failed(str(payment_id), str(e))
            except Exception:
                pass
        return {"status": "error", "reason": "mercadopago_api_error", "error": str(e)}

    except PlexAPIError as e:
        logger.error(f"[MP-WEBHOOK] PLEX API error: {e}")
        # Release idempotency lock to allow retry
        if idempotency and payment_id:
            try:
                await idempotency.mark_failed(str(payment_id), str(e))
            except Exception:
                pass
        return {"status": "error", "reason": "plex_api_error", "error": str(e)}

    except Exception as e:
        logger.error(f"[MP-WEBHOOK] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/mercadopago/health")
async def mercadopago_webhook_health():
    """Health check for Mercado Pago webhook endpoint."""
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
    """Handle user redirect after successful MP payment."""
    logger.info(
        f"[MP-REDIRECT] Success: payment_id={payment_id or collection_id}, "
        f"status={status or collection_status}, ref={external_reference}"
    )
    return HTMLResponse(
        content=MercadoPagoResponsePages.success(
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
    """Handle user redirect after failed/rejected MP payment."""
    logger.info(
        f"[MP-REDIRECT] Failure: payment_id={payment_id or collection_id}, "
        f"status={status or collection_status}, ref={external_reference}"
    )
    return HTMLResponse(
        content=MercadoPagoResponsePages.failure(
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
    """Handle user redirect when MP payment is pending."""
    logger.info(
        f"[MP-REDIRECT] Pending: payment_id={payment_id or collection_id}, "
        f"status={status or collection_status}, ref={external_reference}"
    )
    return HTMLResponse(
        content=MercadoPagoResponsePages.pending(
            payment_id=payment_id or collection_id,
            status=status or collection_status,
            external_reference=external_reference,
        )
    )
