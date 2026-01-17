# ============================================================================
# SCOPE: MULTI-TENANT
# Description: LangGraph node for payment processing operations.
#              REFACTORED: Extracted utilities into utils/payment/.
# Tenant-Aware: Yes - organization context for config and patterns.
# ============================================================================
"""
Payment Processor Node - V2 Payment Handling Node.

Handles payment confirmation and Mercado Pago link generation.

REFACTORED: Extracted responsibilities into utils/payment/:
- payment_link_service.py: MP preference creation
- confirmation_handler.py: YES/NO pattern loading and matching
- amount_validator.py: Amount parsing and validation
- payment_state_builder.py: State dict builders
- error_handlers.py: Consolidated error response generation
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from app.database.async_db import get_async_db_context
from app.domains.pharmacy.agents.utils.debt import OrganizationResolver
from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor
from app.domains.pharmacy.agents.utils.payment import (
    AmountValidator,
    ConfirmationMatcher,
    ConfirmationPatternLoader,
    PaymentErrorHandler,
    PaymentErrorType,
    PaymentLinkService,
    PaymentStateBuilder,
)
from app.domains.pharmacy.agents.utils.response_helper import generate_response

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.tenancy.pharmacy_config_service import PharmacyConfig
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


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
        _config: Optional configuration (unused)

    Returns:
        State updates
    """
    message = MessageExtractor.extract_last_human_message(state) or ""
    awaiting = state.get("awaiting_input")
    organization_id = OrganizationResolver.resolve_safe(state.get("organization_id"))

    async with get_async_db_context() as db:
        # Handle payment amount input
        if awaiting in ("amount", "pay_debt_action"):
            return await _handle_amount_input(message, state, db, organization_id)

        # Handle payment confirmation (YES/NO)
        if awaiting == "payment_confirmation" or state.get("awaiting_payment_confirmation"):
            return await _handle_confirmation(message, state, db, organization_id)

        # Handle initial payment intents
        intent = state.get("intent")
        if intent == "pay_partial" and not state.get("payment_amount"):
            return await _handle_initial_pay_partial(state, db, organization_id)

        if intent == "pay_half" and not state.get("payment_amount"):
            return await _handle_pay_half(state, db, organization_id)

        if intent == "pay_full" and not state.get("payment_amount"):
            return await _handle_initial_pay_full(state, db, organization_id)

        # If we have a payment amount and are authenticated, request confirmation
        if state.get("payment_amount") and state.get("plex_user_id"):
            return await _request_payment_confirmation(state, db, organization_id)

        # Otherwise, redirect to debt check
        content = await generate_response(db, organization_id, "payment_redirect_to_debt", state)
        return {
            "messages": [{"role": "assistant", "content": content}],
            **PaymentStateBuilder.redirect_to_debt(),
        }


# =============================================================================
# Confirmation Handling
# =============================================================================


async def _handle_confirmation(
    message: str,
    state: "PharmacyStateV2",
    db: "AsyncSession",
    organization_id: UUID,
) -> dict[str, Any]:
    """Handle YES/NO payment confirmation using database patterns."""
    yes_patterns, no_patterns = await ConfirmationPatternLoader.load(db, organization_id)
    result = ConfirmationMatcher.match(message, yes_patterns, no_patterns)

    if result.result == "yes":
        return await _process_payment_link(state, db, organization_id)

    if result.result == "no":
        # Check if user also provided a new amount (e.g., "no, quiero pagar 20 mil")
        new_amount = AmountValidator.extract_amount(message)
        if new_amount is not None and new_amount > 0:
            # User wants to change amount - validate and show new confirmation
            total_debt = state.get("total_debt") or 0
            if new_amount <= total_debt:
                is_partial = AmountValidator.is_partial_payment(new_amount, total_debt)
                remaining = AmountValidator.calculate_remaining(new_amount, total_debt)

                template_state = {
                    **state,
                    "payment_amount": f"{new_amount:,.2f}",
                    "total_debt": f"{total_debt:,.2f}",
                    "remaining_balance": f"{remaining:,.2f}",
                }

                intent = "payment_partial_confirm" if is_partial else "payment_total_request"
                msg = await generate_response(db, organization_id, intent, template_state)

                return {
                    "messages": [{"role": "assistant", "content": msg}],
                    **PaymentStateBuilder.confirmation_request(new_amount, total_debt, is_partial),
                }

        # No new amount or invalid - just cancel
        content = await generate_response(db, organization_id, "payment_cancelled", {})
        return {
            "messages": [{"role": "assistant", "content": content}],
            **PaymentStateBuilder.cancellation(),
        }

    # Unclear response
    return await PaymentErrorHandler.handle(
        db, organization_id, PaymentErrorType.YES_NO_UNCLEAR, dict(state)
    )


# =============================================================================
# Payment Link Processing
# =============================================================================


async def _process_payment_link(
    state: "PharmacyStateV2",
    db: "AsyncSession",
    organization_id: UUID,
) -> dict[str, Any]:
    """Generate payment link after confirmation."""
    # Validate prerequisites
    pharmacy_id = state.get("pharmacy_id")
    if not pharmacy_id:
        return await PaymentErrorHandler.handle(db, organization_id, PaymentErrorType.NO_PHARMACY)

    # Load pharmacy config
    config = await _load_pharmacy_config(pharmacy_id)
    if not config:
        return await PaymentErrorHandler.handle(db, organization_id, PaymentErrorType.CONFIG_NOT_FOUND)

    if not config.mp_enabled:
        return await PaymentErrorHandler.handle(db, organization_id, PaymentErrorType.MP_DISABLED)

    if not config.mp_access_token:
        return await PaymentErrorHandler.handle(db, organization_id, PaymentErrorType.MP_NOT_CONFIGURED)

    # Get payment details
    plex_customer_id = state.get("plex_user_id")
    if not plex_customer_id:
        return await PaymentErrorHandler.handle(db, organization_id, PaymentErrorType.NOT_AUTHENTICATED)

    total_debt = Decimal(str(state.get("total_debt") or 0))
    payment_amount = state.get("payment_amount") or float(total_debt)
    amount = Decimal(str(payment_amount))

    if amount <= 0:
        return await PaymentErrorHandler.handle(db, organization_id, PaymentErrorType.INVALID_AMOUNT)

    customer_name = state.get("customer_name") or "Cliente"
    customer_phone = state.get("user_phone")
    debt_id = state.get("debt_id") or "unknown"
    is_partial = state.get("is_partial_payment", False)
    pharmacy_name = config.pharmacy_name or "Farmacia"

    # Create payment link
    link_service = PaymentLinkService()
    result = await link_service.create_link(
        config=config,
        amount=amount,
        customer_name=customer_name,
        customer_phone=customer_phone,
        plex_customer_id=plex_customer_id,
        debt_id=debt_id,
        pharmacy_id=str(pharmacy_id),
    )

    if not result:
        return await PaymentErrorHandler.handle(
            db, organization_id, PaymentErrorType.LINK_FAILED, dict(state)
        )

    # Build success state
    success_state = PaymentStateBuilder.payment_link_success(
        result=result,
        customer_name=customer_name,
        amount=float(amount),
        total_debt=float(total_debt),
        is_partial=is_partial,
        pharmacy_name=pharmacy_name,
    )

    # Generate response
    intent = "payment_link_partial" if is_partial else "payment_link_generated"
    template_state = {**state, **success_state.get("_template_vars", {})}
    response_text = await generate_response(db, organization_id, intent, template_state)

    return {
        "messages": [{"role": "assistant", "content": response_text}],
        **{k: v for k, v in success_state.items() if k != "_template_vars"},
    }


# =============================================================================
# Amount Input Handling
# =============================================================================


async def _handle_amount_input(
    message: str,
    state: "PharmacyStateV2",
    db: "AsyncSession",
    organization_id: UUID,
) -> dict[str, Any]:
    """Handle custom payment amount input."""
    total_debt = state.get("total_debt") or 0
    validation = AmountValidator.validate(message, total_debt)

    if not validation.is_valid:
        return await PaymentErrorHandler.handle_amount_error(
            db=db,
            organization_id=organization_id,
            error_message=validation.error_message or "Monto inválido",
            state=dict(state),
            total_debt=total_debt if validation.error_type and validation.error_type.value == "exceeds_debt" else None,
        )

    # Valid amount - request confirmation
    amount = validation.amount or 0.0  # Type narrowing: amount is valid here
    is_partial = AmountValidator.is_partial_payment(amount, total_debt)
    remaining = AmountValidator.calculate_remaining(amount, total_debt)

    template_state = {
        **state,
        "payment_amount": f"{amount:,.2f}",
        "total_debt": f"{total_debt:,.2f}",
        "remaining_balance": f"{remaining:,.2f}",
    }

    intent = "payment_partial_confirm" if is_partial else "payment_total_request"
    msg = await generate_response(db, organization_id, intent, template_state)

    return {
        "messages": [{"role": "assistant", "content": msg}],
        **PaymentStateBuilder.confirmation_request(amount, total_debt, is_partial),
    }


# =============================================================================
# Initial Intent Handlers
# =============================================================================


async def _handle_initial_pay_partial(
    state: "PharmacyStateV2",
    db: "AsyncSession",
    organization_id: UUID,
) -> dict[str, Any]:
    """Handle initial pay_partial intent - ask for amount."""
    total_debt = state.get("total_debt") or 0
    customer_name = state.get("customer_name") or "Cliente"

    template_state = {
        **state,
        "customer_name": customer_name,
        "total_debt": f"{total_debt:,.2f}",
    }

    content = await generate_response(db, organization_id, "payment_request_amount", template_state)
    return {
        "messages": [{"role": "assistant", "content": content}],
        **PaymentStateBuilder.awaiting_amount(is_partial=True),
    }


async def _handle_pay_half(
    state: "PharmacyStateV2",
    db: "AsyncSession",
    organization_id: UUID,
) -> dict[str, Any]:
    """Handle pay_half intent - 50% of debt shortcut."""
    total_debt = state.get("total_debt") or 0
    half_amount = total_debt / 2
    customer_name = state.get("customer_name") or "Cliente"
    remaining = total_debt - half_amount

    template_state = {
        **state,
        "customer_name": customer_name,
        "payment_amount": f"{half_amount:,.2f}",
        "total_debt": f"{total_debt:,.2f}",
        "remaining_balance": f"{remaining:,.2f}",
    }

    content = await generate_response(db, organization_id, "payment_partial_confirm", template_state)
    return {
        "messages": [{"role": "assistant", "content": content}],
        **PaymentStateBuilder.confirmation_request(half_amount, total_debt, is_partial=True),
    }


async def _handle_initial_pay_full(
    state: "PharmacyStateV2",
    db: "AsyncSession",
    organization_id: UUID,
) -> dict[str, Any]:
    """Handle initial pay_full intent - set full amount and request confirmation."""
    total_debt = state.get("total_debt") or 0
    customer_name = state.get("customer_name") or "Cliente"

    template_state = {
        **state,
        "customer_name": customer_name,
        "payment_amount": f"{total_debt:,.2f}",
        "total_debt": f"{total_debt:,.2f}",
        "remaining_balance": "0.00",
    }

    content = await generate_response(db, organization_id, "payment_total_request", template_state)
    return {
        "messages": [{"role": "assistant", "content": content}],
        **PaymentStateBuilder.confirmation_request(total_debt, total_debt, is_partial=False),
    }


async def _request_payment_confirmation(
    state: "PharmacyStateV2",
    db: "AsyncSession",
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
    msg = await generate_response(db, organization_id, intent, template_state)

    return {
        "messages": [{"role": "assistant", "content": msg}],
        **PaymentStateBuilder.confirmation_request(amount, total, is_partial),
    }


# =============================================================================
# Config Loading Helper
# =============================================================================


async def _load_pharmacy_config(pharmacy_id: str | UUID) -> "PharmacyConfig | None":
    """Load pharmacy configuration by pharmacy_id."""
    try:
        from app.core.tenancy.pharmacy_config_service import PharmacyConfigService

        pharmacy_uuid = UUID(str(pharmacy_id)) if not isinstance(pharmacy_id, UUID) else pharmacy_id

        async with get_async_db_context() as db:
            config_service = PharmacyConfigService(db)
            return await config_service.get_config_by_id(pharmacy_uuid)

    except Exception as e:
        logger.error(f"Failed to load pharmacy config: {e}")
        return None


__all__ = ["payment_processor_node"]
