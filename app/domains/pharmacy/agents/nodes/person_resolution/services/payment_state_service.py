"""Payment state management service - Zombie payment detection."""

from __future__ import annotations

import logging
from typing import Any

from app.services.mercadopago import get_idempotency_service

logger = logging.getLogger(__name__)


class PaymentStateService:
    """
    Service for payment state management.

    Responsibilities:
    - Detect zombie (stale) payment states
    - Check payment completion status
    - Generate appropriate resume responses
    """

    async def check_zombie_payment(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Check for zombie payment state on session resume.

        If awaiting_payment=True but the payment link has expired (24h TTL) or
        was already processed, clear the stale state.

        Args:
            state_dict: Current state dictionary

        Returns:
            State updates if zombie state detected, None otherwise
        """
        if not state_dict.get("awaiting_payment"):
            return None

        mp_preference_id = state_dict.get("mp_preference_id")
        payment_id = state_dict.get("mp_payment_id")

        if not mp_preference_id and not payment_id:
            logger.info(
                "[ZOMBIE] No payment reference in awaiting_payment state, clearing"
            )
            return {
                "awaiting_payment": False,
                "mp_preference_id": None,
                "mp_payment_id": None,
                "mp_init_point": None,
            }

        # Check if payment was already processed
        if payment_id:
            try:
                idempotency = await get_idempotency_service()
                receipt = await idempotency.get_receipt(str(payment_id))

                if receipt:
                    logger.info(
                        f"[ZOMBIE] Payment {payment_id} already processed, receipt: {receipt}"
                    )
                    customer_name = state_dict.get("customer_name", "Cliente")

                    return {
                        "awaiting_payment": False,
                        "mp_payment_status": "approved",
                        "plex_receipt_number": receipt,
                        "messages": [
                            {
                                "role": "assistant",
                                "content": (
                                    f"Hola {customer_name}! Tu pago ya fue procesado exitosamente.\n\n"
                                    f"Recibo: *{receipt}*\n\n"
                                    "El comprobante fue enviado a tu WhatsApp.\n"
                                    "Hay algo mas en que pueda ayudarte?"
                                ),
                            }
                        ],
                    }
            except Exception as e:
                logger.warning(f"[ZOMBIE] Failed to check payment status: {e}")

        # Stale payment state - offer to resend
        logger.info(f"[ZOMBIE] Found stale payment state for preference {mp_preference_id}")
        customer_name = state_dict.get("customer_name", "Cliente")

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Hola {customer_name}! Veo que tenias un pago pendiente.\n\n"
                        "El link de pago anterior puede haber expirado.\n"
                        "Queres que genere un nuevo link de pago?\n\n"
                        "Responde *SI* para nuevo link o *NO* para cancelar."
                    ),
                }
            ],
            "zombie_payment_check": True,
        }


__all__ = ["PaymentStateService"]
