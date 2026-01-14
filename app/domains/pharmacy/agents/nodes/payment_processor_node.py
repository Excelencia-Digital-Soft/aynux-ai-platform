"""
Payment Processor Node - V2 Payment Handling Node.

Handles payment confirmation and Mercado Pago link generation.
Merges functionality from payment_link_node.py and confirmation_node.py.

Uses V2 state fields: payment_amount, mp_payment_link, awaiting_payment_confirmation, etc.

NOTE: All confirmation patterns and messages are loaded from database.
- YES/NO patterns: core.domain_intents (payment_confirm, payment_reject)
- Messages: core.response_configs + YAML templates
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.mercado_pago_client import MercadoPagoClient
from app.core.tenancy.pharmacy_config_service import PharmacyConfig, PharmacyConfigService
from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


# NOTE: Confirmation keywords are now loaded from database via domain_intent_cache
# See _load_confirmation_patterns() function below


class PaymentProcessorService:
    """
    Service for payment processing operations.

    Responsibilities:
    - Payment confirmation handling
    - Mercado Pago preference creation
    - Payment link generation
    """

    def __init__(self):
        self._pharmacy_config: PharmacyConfig | None = None

    async def load_pharmacy_config(
        self,
        pharmacy_id: str | UUID | None,
    ) -> PharmacyConfig | None:
        """Load pharmacy configuration by pharmacy_id."""
        if self._pharmacy_config is not None:
            return self._pharmacy_config

        if not pharmacy_id:
            logger.warning("No pharmacy_id provided for config lookup")
            return None

        try:
            pharmacy_uuid = UUID(str(pharmacy_id)) if not isinstance(pharmacy_id, UUID) else pharmacy_id

            from app.database.async_db import get_async_db_context

            async with get_async_db_context() as db:
                config_service = PharmacyConfigService(db)
                self._pharmacy_config = await config_service.get_config_by_id(pharmacy_uuid)
                return self._pharmacy_config

        except Exception as e:
            logger.error(f"Failed to load pharmacy config: {e}")
            return None

    async def create_payment_link(
        self,
        pharmacy_config: PharmacyConfig,
        amount: Decimal,
        customer_name: str,
        customer_phone: str | None,
        plex_customer_id: int,
        debt_id: str,
        pharmacy_id: str,
    ) -> dict[str, Any] | None:
        """
        Create Mercado Pago payment preference.

        Args:
            pharmacy_config: Pharmacy configuration with MP credentials
            amount: Payment amount
            customer_name: Customer name
            customer_phone: Customer phone
            plex_customer_id: PLEX customer ID
            debt_id: Debt identifier
            pharmacy_id: Pharmacy identifier

        Returns:
            Payment link data dict or None on error
        """
        try:
            # Validate access token is present (caller should check, but type-guard here)
            if not pharmacy_config.mp_access_token:
                logger.error("Missing mp_access_token in pharmacy config")
                return None

            # Create external reference for webhook correlation
            unique_id = uuid.uuid4().hex[:8]
            external_reference = f"{plex_customer_id}:{debt_id}:{pharmacy_id}:{unique_id}"

            logger.info(
                f"Creating MP payment link: customer={plex_customer_id}, " f"amount=${amount}, ref={external_reference}"
            )

            # Create Mercado Pago client
            mp_client = MercadoPagoClient(
                access_token=pharmacy_config.mp_access_token,
                notification_url=pharmacy_config.mp_notification_url,
                sandbox=pharmacy_config.mp_sandbox,
                timeout=pharmacy_config.mp_timeout,
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
            if pharmacy_config.mp_sandbox and preference.get("sandbox_init_point"):
                init_point = preference["sandbox_init_point"]

            logger.info(f"MP preference created: {preference_id}")

            return {
                "preference_id": preference_id,
                "init_point": init_point,
                "external_reference": external_reference,
            }

        except Exception as e:
            logger.error(f"Error creating MP payment link: {e}", exc_info=True)
            return None


# =============================================================================
# Database-Driven Pattern Loading
# =============================================================================


async def _load_confirmation_patterns(
    db: AsyncSession,
    organization_id: UUID,
) -> tuple[set[str], set[str]]:
    """
    Load YES/NO confirmation patterns from database (3-layer cache).

    Returns:
        Tuple of (yes_patterns, no_patterns) sets
    """
    from app.core.cache.domain_intent_cache import domain_intent_cache

    try:
        patterns = await domain_intent_cache.get_confirmation_patterns(db, organization_id, "pharmacy")

        # Get patterns for confirm and reject intents
        # These use the standard "confirm" and "reject" intents from domain_intents
        confirm = patterns.get("confirm", {})
        reject = patterns.get("reject", {})

        yes_patterns = confirm.get("exact", set()) | confirm.get("contains", set())
        no_patterns = reject.get("exact", set()) | reject.get("contains", set())

        # Fallback to common patterns if database is empty
        if not yes_patterns:
            logger.warning("No YES patterns in database for 'confirm' intent, using fallback")
            yes_patterns = {"si", "sí", "yes", "s", "confirmo", "dale", "ok"}

        if not no_patterns:
            logger.warning("No NO patterns in database for 'reject' intent, using fallback")
            no_patterns = {"no", "n", "cancelar", "cancela", "volver"}

        return yes_patterns, no_patterns

    except Exception as e:
        logger.error(f"Error loading confirmation patterns: {e}", exc_info=True)
        # Fallback patterns for resilience
        return (
            {"si", "sí", "yes", "s", "confirmo", "dale", "ok"},
            {"no", "n", "cancelar", "cancela", "volver"},
        )


async def _generate_response(
    db: AsyncSession,
    organization_id: UUID,
    intent: str,
    state: dict[str, Any] | Any,
) -> str:
    """
    Generate response using PharmacyResponseGenerator.

    Falls back to template-based response if generator fails.

    Args:
        db: Database session
        organization_id: Organization UUID for multi-tenant support
        intent: Intent key for response config lookup
        state: State dict (can be PharmacyStateV2 or plain dict)
    """
    from app.domains.pharmacy.agents.utils.response import get_response_generator

    try:
        generator = get_response_generator()
        response = await generator.generate(
            db=db,
            organization_id=organization_id,
            intent=intent,
            state=state,
            user_message="",
        )
        return response.content
    except Exception as e:
        logger.error(f"Error generating response for intent {intent}: {e}", exc_info=True)
        # Return a generic fallback message
        return "Disculpa, tuve un problema. Por favor intenta de nuevo."


# =============================================================================
# Main Node Function
# =============================================================================


async def payment_processor_node(
    state: "PharmacyStateV2",
    _config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """
    Payment processor node - handles confirmation and link generation.

    Flow:
    1. If awaiting_payment_confirmation: handle YES/NO input
    2. If awaiting_input == "amount": handle custom amount input
    3. If confirmed: generate payment link
    4. Otherwise: request confirmation

    Args:
        state: Current conversation state
        config: Optional configuration

    Returns:
        State updates
    """
    from app.database.async_db import get_async_db_context

    service = PaymentProcessorService()

    # Extract message
    message = MessageExtractor.extract_last_human_message(state) or ""
    message_lower = message.strip().lower()
    awaiting = state.get("awaiting_input")

    # Get organization context for multi-tenant support
    org_id_raw = state.get("organization_id")
    if not org_id_raw:
        logger.warning("No organization_id in state, using default")
        # Use system organization as fallback
        organization_id = UUID("00000000-0000-0000-0000-000000000000")
    elif isinstance(org_id_raw, str):
        organization_id = UUID(org_id_raw)
    else:
        organization_id = org_id_raw

    # Get database session for pattern/config lookups
    async with get_async_db_context() as db:
        # Handle payment amount input
        if awaiting == "amount":
            return await _handle_amount_input(message, state, db, organization_id)

        # Handle payment confirmation (YES/NO)
        if awaiting == "payment_confirmation" or state.get("awaiting_payment_confirmation"):
            return await _handle_confirmation(message_lower, state, service, db, organization_id)

        # If we have a payment amount and are authenticated, request confirmation
        if state.get("payment_amount") and state.get("plex_user_id"):
            return await _request_payment_confirmation(state, db, organization_id)

        # Otherwise, need to go back to debt check
        content = await _generate_response(db, organization_id, "payment_redirect_to_debt", state)
        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_node": "payment_processor",
            "next_node": "debt_manager",
        }


async def _handle_confirmation(
    message_lower: str,
    state: "PharmacyStateV2",
    service: PaymentProcessorService,
    db: AsyncSession,
    organization_id: UUID,
) -> dict[str, Any]:
    """Handle YES/NO payment confirmation using database patterns."""
    # Load confirmation patterns from database (cached)
    yes_patterns, no_patterns = await _load_confirmation_patterns(db, organization_id)

    # Check for YES
    if message_lower in yes_patterns:
        return await _process_payment_link(state, service, db, organization_id)

    # Check for NO
    if message_lower in no_patterns:
        return await _handle_cancellation(state, db, organization_id)

    # Unclear response
    return await _request_clear_response(state, db, organization_id)


async def _process_payment_link(
    state: "PharmacyStateV2",
    service: PaymentProcessorService,
    db: AsyncSession,
    organization_id: UUID,
) -> dict[str, Any]:
    """Generate payment link after confirmation."""
    # Validate prerequisites
    pharmacy_id = state.get("pharmacy_id")
    if not pharmacy_id:
        return await _handle_no_pharmacy(db, organization_id)

    # Load pharmacy config
    pharmacy_config = await service.load_pharmacy_config(pharmacy_id)
    if not pharmacy_config:
        return await _handle_config_not_found(db, organization_id)

    # Check MP is enabled
    if not pharmacy_config.mp_enabled:
        return await _handle_mp_disabled(db, organization_id)

    if not pharmacy_config.mp_access_token:
        return await _handle_mp_not_configured(db, organization_id)

    # Get payment details
    plex_customer_id = state.get("plex_user_id")
    if not plex_customer_id:
        return await _handle_not_authenticated(db, organization_id)

    total_debt = Decimal(str(state.get("total_debt") or 0))
    payment_amount = state.get("payment_amount") or float(total_debt)
    amount = Decimal(str(payment_amount))

    if amount <= 0:
        return await _handle_invalid_amount(db, organization_id)

    customer_name = state.get("customer_name") or "Cliente"
    customer_phone = state.get("user_phone")
    debt_id = state.get("debt_id") or "unknown"
    is_partial = state.get("is_partial_payment", False)
    pharmacy_name = pharmacy_config.pharmacy_name or "Farmacia"

    # Create payment link
    result = await service.create_payment_link(
        pharmacy_config=pharmacy_config,
        amount=amount,
        customer_name=customer_name,
        customer_phone=customer_phone,
        plex_customer_id=plex_customer_id,
        debt_id=debt_id,
        pharmacy_id=str(pharmacy_id),
    )

    if not result:
        return await _handle_link_error(state, db, organization_id)

    # Generate response using template
    template_state = {
        **state,
        "customer_name": customer_name,
        "payment_amount": f"{float(amount):,.2f}",
        "total_debt": f"{float(total_debt):,.2f}",
        "remaining_balance": f"{float(total_debt - amount):,.2f}" if is_partial else "0.00",
        "payment_link": result["init_point"],
        "pharmacy_name": pharmacy_name,
    }

    # Use appropriate intent based on partial or full payment
    intent = "payment_link_partial" if is_partial else "payment_link_generated"
    response_text = await _generate_response(db, organization_id, intent, template_state)

    return {
        "messages": [{"role": "assistant", "content": response_text}],
        "current_node": "payment_processor",
        "agent_history": ["payment_processor"],
        # Mercado Pago data
        "mp_payment_link": result["init_point"],
        "mp_payment_status": "pending",
        "mp_external_reference": result["external_reference"],
        # Clear awaiting flags
        "awaiting_payment_confirmation": False,
        "awaiting_input": None,
        # Complete conversation
        "is_complete": True,
        "next_node": "__end__",
    }


async def _handle_amount_input(
    message: str,
    state: "PharmacyStateV2",
    db: AsyncSession,
    organization_id: UUID,
) -> dict[str, Any]:
    """Handle custom payment amount input."""
    import re

    # Extract amount from message
    cleaned = message.replace(".", "").replace(",", "").replace("$", "").strip()
    match = re.search(r"(\d+)", cleaned)

    if not match:
        content = await _generate_response(db, organization_id, "payment_amount_invalid", state)
        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_node": "payment_processor",
            "awaiting_input": "amount",
        }

    amount = float(match.group(1))
    total_debt = state.get("total_debt") or 0

    # Validate amount
    if amount <= 0:
        template_state = {**state, "range_message": "El monto debe ser mayor a $0."}
        content = await _generate_response(db, organization_id, "payment_amount_out_of_range", template_state)
        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_node": "payment_processor",
            "awaiting_input": "amount",
        }

    if amount > total_debt:
        template_state = {
            **state,
            "range_message": f"El monto (${amount:,.2f}) es mayor que tu deuda (${total_debt:,.2f}).",
            "total_debt": f"{total_debt:,.2f}",
        }
        content = await _generate_response(db, organization_id, "payment_amount_out_of_range", template_state)
        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_node": "payment_processor",
            "awaiting_input": "amount",
            "payment_amount": total_debt,
        }

    # Valid amount - request confirmation
    is_partial = amount < total_debt
    remaining = total_debt - amount if is_partial else 0

    template_state = {
        **state,
        "payment_amount": f"{amount:,.2f}",
        "total_debt": f"{total_debt:,.2f}",
        "remaining_balance": f"{remaining:,.2f}",
    }

    intent = "payment_partial_confirm" if is_partial else "payment_total_request"
    msg = await _generate_response(db, organization_id, intent, template_state)

    return {
        "messages": [{"role": "assistant", "content": msg}],
        "current_node": "payment_processor",
        "payment_amount": amount,
        "is_partial_payment": is_partial,
        "awaiting_input": "payment_confirmation",
        "awaiting_payment_confirmation": True,
    }


async def _request_payment_confirmation(
    state: "PharmacyStateV2",
    db: AsyncSession,
    organization_id: UUID,
) -> dict[str, Any]:
    """Request payment confirmation using database-driven templates."""
    amount = state.get("payment_amount") or 0
    total = state.get("total_debt") or 0
    is_partial = state.get("is_partial_payment", False)
    remaining = total - amount if is_partial else 0

    template_state = {
        **state,
        "payment_amount": f"{amount:,.2f}",
        "total_debt": f"{total:,.2f}",
        "remaining_balance": f"{remaining:,.2f}",
    }

    intent = "payment_partial_confirm" if is_partial else "payment_total_request"
    msg = await _generate_response(db, organization_id, intent, template_state)

    return {
        "messages": [{"role": "assistant", "content": msg}],
        "current_node": "payment_processor",
        "awaiting_input": "payment_confirmation",
        "awaiting_payment_confirmation": True,
    }


async def _handle_cancellation(
    _state: "PharmacyStateV2",
    db: AsyncSession,
    organization_id: UUID,
) -> dict[str, Any]:
    """Handle payment cancellation using database-driven templates."""
    content = await _generate_response(db, organization_id, "payment_cancelled", {})
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "payment_processor",
        "awaiting_payment_confirmation": False,
        "awaiting_input": None,
        "payment_amount": None,
        "is_partial_payment": False,
        "is_complete": True,
    }


async def _request_clear_response(
    _state: "PharmacyStateV2",
    db: AsyncSession,
    organization_id: UUID,
) -> dict[str, Any]:
    """Request clear YES/NO response using database-driven templates."""
    content = await _generate_response(db, organization_id, "payment_yes_no_unclear", {})
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "payment_processor",
        "awaiting_input": "payment_confirmation",
        "awaiting_payment_confirmation": True,
    }


# =============================================================================
# Error Handlers (Database-Driven)
# =============================================================================


async def _handle_no_pharmacy(db: AsyncSession, organization_id: UUID) -> dict[str, Any]:
    """Handle missing pharmacy ID error."""
    content = await _generate_response(db, organization_id, "payment_no_pharmacy", {})
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "payment_processor",
        "is_complete": True,
        "awaiting_input": None,
    }


async def _handle_config_not_found(db: AsyncSession, organization_id: UUID) -> dict[str, Any]:
    """Handle missing pharmacy config error."""
    content = await _generate_response(db, organization_id, "payment_config_not_found", {})
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "payment_processor",
        "is_complete": True,
        "awaiting_input": None,
    }


async def _handle_mp_disabled(db: AsyncSession, organization_id: UUID) -> dict[str, Any]:
    """Handle MP disabled error."""
    content = await _generate_response(db, organization_id, "payment_mp_disabled", {})
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "payment_processor",
        "is_complete": True,
        "awaiting_input": None,
    }


async def _handle_mp_not_configured(db: AsyncSession, organization_id: UUID) -> dict[str, Any]:
    """Handle MP not configured error."""
    content = await _generate_response(db, organization_id, "payment_mp_not_configured", {})
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "payment_processor",
        "is_complete": True,
        "awaiting_input": None,
    }


async def _handle_not_authenticated(db: AsyncSession, organization_id: UUID) -> dict[str, Any]:
    """Handle not authenticated error."""
    content = await _generate_response(db, organization_id, "payment_not_authenticated", {})
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "payment_processor",
        "is_complete": True,
        "awaiting_input": None,
    }


async def _handle_invalid_amount(db: AsyncSession, organization_id: UUID) -> dict[str, Any]:
    """Handle invalid payment amount error."""
    content = await _generate_response(db, organization_id, "payment_invalid_amount", {})
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "payment_processor",
        "is_complete": True,
        "awaiting_input": None,
    }


async def _handle_link_error(
    state: "PharmacyStateV2",
    db: AsyncSession,
    organization_id: UUID,
) -> dict[str, Any]:
    """Handle payment link generation error."""
    content = await _generate_response(db, organization_id, "payment_link_failed", state)
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "payment_processor",
        "error_count": (state.get("error_count") or 0) + 1,
        "is_complete": True,
        "awaiting_input": None,
    }


__all__ = ["payment_processor_node", "PaymentProcessorService"]
