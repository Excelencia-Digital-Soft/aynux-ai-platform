# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Mercado Pago payment link creation service.
#              Extracted from payment_processor_node.py for SRP compliance.
# Tenant-Aware: Yes - uses pharmacy config for MP credentials.
# ============================================================================
"""
Mercado Pago payment link creation service.

Single Responsibility: Create Mercado Pago payment preferences and links.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.tenancy.pharmacy_config_service import PharmacyConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaymentLinkResult:
    """
    Result of payment link creation.

    Attributes:
        preference_id: Mercado Pago preference ID
        init_point: Payment URL for the customer
        external_reference: Unique reference for webhook correlation
    """

    preference_id: str
    init_point: str
    external_reference: str


class PaymentLinkService:
    """
    Service for creating Mercado Pago payment links.

    Single Responsibility: MP preference creation and link generation.

    This service handles:
    - MP client initialization with pharmacy credentials
    - Preference creation with customer details
    - External reference generation for webhook correlation
    """

    async def create_link(
        self,
        config: "PharmacyConfig",
        amount: Decimal,
        customer_name: str,
        customer_phone: str | None,
        plex_customer_id: int,
        debt_id: str,
        pharmacy_id: str,
    ) -> PaymentLinkResult | None:
        """
        Create Mercado Pago payment preference.

        Args:
            config: Pharmacy configuration with MP credentials
            amount: Payment amount
            customer_name: Customer name for preference
            customer_phone: Optional customer phone
            plex_customer_id: PLEX customer ID for reference
            debt_id: Debt identifier for reference
            pharmacy_id: Pharmacy identifier for reference

        Returns:
            PaymentLinkResult with preference details or None on error
        """
        try:
            if not config.mp_access_token:
                logger.error("Missing mp_access_token in pharmacy config")
                return None

            # Create external reference for webhook correlation
            # Format: customer_id:debt_id:pharmacy_id:uuid:phone (phone for WhatsApp notification)
            unique_id = uuid.uuid4().hex[:8]
            # Normalize phone: remove non-digits, ensure it's safe for : separator
            safe_phone = "".join(c for c in (customer_phone or "") if c.isdigit()) or "0"
            external_reference = f"{plex_customer_id}:{debt_id}:{pharmacy_id}:{unique_id}:{safe_phone}"

            logger.info(
                f"Creating MP payment link: customer={plex_customer_id}, "
                f"amount=${amount}, ref={external_reference}"
            )

            # Create Mercado Pago client
            from app.clients.mercado_pago_client import MercadoPagoClient

            mp_client = MercadoPagoClient(
                access_token=config.mp_access_token,
                notification_url=config.mp_notification_url,
                sandbox=config.mp_sandbox,
                timeout=config.mp_timeout,
            )

            async with mp_client:
                preference = await mp_client.create_preference(
                    amount=amount,
                    description=f"Pago de deuda - {customer_name}",
                    external_reference=external_reference,
                    payer_phone=customer_phone,
                    payer_name=customer_name,
                )

            init_point = preference["init_point"]
            preference_id = preference["preference_id"]

            # Use sandbox URL in sandbox mode
            if config.mp_sandbox and preference.get("sandbox_init_point"):
                init_point = preference["sandbox_init_point"]

            logger.info(f"MP preference created: {preference_id}")

            return PaymentLinkResult(
                preference_id=preference_id,
                init_point=init_point,
                external_reference=external_reference,
            )

        except Exception as e:
            logger.error(f"Error creating MP payment link: {e}", exc_info=True)
            return None
