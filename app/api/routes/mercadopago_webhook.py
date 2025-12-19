"""
Mercado Pago Webhook Handler

Receives payment notifications from Mercado Pago and registers
payments in PLEX ERP, then sends confirmation to customer via WhatsApp.

Webhook Flow:
1. MP sends POST notification when payment status changes
2. Validate webhook authenticity (optional signature check)
3. Fetch full payment details from MP API
4. For approved payments: Register in PLEX with REGISTRAR_PAGO_CLIENTE
5. Send WhatsApp confirmation to customer with PLEX receipt number

Endpoint: POST /api/v1/webhooks/mercadopago
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.clients.mercado_pago_client import MercadoPagoClient, MercadoPagoError
from app.clients.plex_client import PlexAPIError, PlexClient
from app.config.settings import get_settings
from app.integrations.whatsapp.service import WhatsAppService

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
):
    """
    Handle Mercado Pago payment notifications.

    This webhook is called by Mercado Pago when a payment status changes.
    For approved payments, it:
    1. Fetches payment details from MP
    2. Registers the payment in PLEX ERP
    3. Sends a WhatsApp confirmation to the customer

    Args:
        request: FastAPI request object
        payload: Webhook payload from Mercado Pago

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

        # Check if MP integration is enabled
        if not settings.MERCADO_PAGO_ENABLED:
            logger.warning("MP webhook received but MERCADO_PAGO_ENABLED=false")
            return {"status": "ignored", "reason": "integration_disabled"}

        # Only process payment notifications
        if payload.type != "payment":
            logger.info(f"Ignoring non-payment notification: type={payload.type}")
            return {"status": "ignored", "reason": f"type={payload.type}"}

        # Get payment ID from payload
        payment_id = payload.data.get("id")
        if not payment_id:
            logger.warning("MP webhook missing payment ID in data")
            return {"status": "ignored", "reason": "missing_payment_id"}

        # Fetch full payment details from Mercado Pago
        mp_client = MercadoPagoClient()
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

        # Parse external_reference: "customer_id:debt_id:uuid"
        external_ref = payment.get("external_reference", "")
        parts = external_ref.split(":")
        if len(parts) < 2:
            logger.error(f"Invalid external_reference format: {external_ref}")
            return {
                "status": "error",
                "reason": "invalid_external_reference",
                "external_reference": external_ref,
            }

        plex_customer_id = int(parts[0])
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

        # Try to send WhatsApp confirmation
        payer_phone = _extract_payer_phone(payment)
        if payer_phone:
            await _send_payment_confirmation(
                phone=payer_phone,
                amount=amount,
                receipt=plex_receipt,
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
    """
    settings = get_settings()
    return {
        "status": "ok",
        "enabled": settings.MERCADO_PAGO_ENABLED,
        "sandbox": settings.MERCADO_PAGO_SANDBOX,
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


async def _send_payment_confirmation(
    phone: str,
    amount: float,
    receipt: str,
    new_balance: str,
) -> None:
    """
    Send payment confirmation via WhatsApp.

    Args:
        phone: Customer's WhatsApp phone number
        amount: Amount paid
        receipt: PLEX receipt number (e.g., "RC X 0001-00016790")
        new_balance: Customer's new balance after payment
    """
    try:
        # Format balance for display
        try:
            balance_float = float(new_balance.replace(",", ".").replace(" ", ""))
            balance_str = f"${balance_float:,.2f}"
        except (ValueError, AttributeError):
            balance_str = f"${new_balance}"

        message = f"""**Pago Recibido**

Tu pago ha sido procesado exitosamente.

**Monto pagado:** ${amount:,.2f}
**Comprobante:** {receipt}
**Nuevo saldo:** {balance_str}

Gracias por tu pago. Si tienes alguna pregunta, escribe *AYUDA*."""

        whatsapp = WhatsAppService()
        await whatsapp.send_message(phone, message)
        logger.info(f"WhatsApp confirmation sent to {phone}")

    except Exception as e:
        # Don't fail the webhook for WhatsApp errors
        logger.error(f"Error sending WhatsApp confirmation to {phone}: {e}")
