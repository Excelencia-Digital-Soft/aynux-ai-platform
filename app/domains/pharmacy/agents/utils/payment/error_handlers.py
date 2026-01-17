# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Consolidated error response generation for payments.
#              Extracted from payment_processor_node.py for SRP compliance.
# Tenant-Aware: Yes - uses database-driven response generation.
# ============================================================================
"""
Consolidated error response generation for payments.

Single Responsibility: Generate error responses for payment failures.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PaymentErrorType(str, Enum):
    """Types of payment errors."""

    NO_PHARMACY = "payment_no_pharmacy"
    CONFIG_NOT_FOUND = "payment_config_not_found"
    MP_DISABLED = "payment_mp_disabled"
    MP_NOT_CONFIGURED = "payment_mp_not_configured"
    NOT_AUTHENTICATED = "payment_not_authenticated"
    INVALID_AMOUNT = "payment_invalid_amount"
    AMOUNT_OUT_OF_RANGE = "payment_amount_out_of_range"
    AMOUNT_INVALID_FORMAT = "payment_amount_invalid"
    LINK_FAILED = "payment_link_failed"
    YES_NO_UNCLEAR = "payment_yes_no_unclear"


class PaymentErrorHandler:
    """
    Handles error responses for payment operations.

    Single Responsibility: Generate consistent error responses.

    This class consolidates all payment error handling into a single
    pattern, reducing code duplication and ensuring consistent responses.
    """

    # Error configurations: (is_complete, clear_awaiting)
    ERROR_CONFIG: dict[PaymentErrorType, tuple[bool, bool]] = {
        PaymentErrorType.NO_PHARMACY: (True, True),
        PaymentErrorType.CONFIG_NOT_FOUND: (True, True),
        PaymentErrorType.MP_DISABLED: (True, True),
        PaymentErrorType.MP_NOT_CONFIGURED: (True, True),
        PaymentErrorType.NOT_AUTHENTICATED: (True, True),
        PaymentErrorType.INVALID_AMOUNT: (True, True),
        PaymentErrorType.AMOUNT_OUT_OF_RANGE: (False, False),  # Keep awaiting for retry
        PaymentErrorType.AMOUNT_INVALID_FORMAT: (False, False),  # Keep awaiting for retry
        PaymentErrorType.LINK_FAILED: (True, True),
        PaymentErrorType.YES_NO_UNCLEAR: (False, False),  # Keep awaiting for retry
    }

    @classmethod
    async def handle(
        cls,
        db: "AsyncSession",
        organization_id: "UUID",
        error_type: PaymentErrorType,
        state: dict[str, Any] | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate error response for payment failure.

        Args:
            db: Database session
            organization_id: Organization UUID for multi-tenant support
            error_type: Type of error to handle
            state: Optional current state for context
            extra_context: Optional extra context for response template

        Returns:
            State dict with error response
        """
        from app.domains.pharmacy.agents.utils.response_helper import generate_response

        # Build context for response
        context = dict(state) if state else {}
        if extra_context:
            context.update(extra_context)

        # Generate response using database-driven templates
        content = await generate_response(
            db=db,
            organization_id=organization_id,
            intent=error_type.value,
            state=context,
        )

        # Get error configuration
        is_complete, clear_awaiting = cls.ERROR_CONFIG.get(
            error_type, (True, True)
        )

        # Build response state
        result: dict[str, Any] = {
            "messages": [{"role": "assistant", "content": content}],
            "current_node": "payment_processor",
            # Tell response_formatter to skip - we already have the error message
            "skip_response_formatting": True,
        }

        if is_complete:
            result["is_complete"] = True

        if clear_awaiting:
            result["awaiting_input"] = None
            result["awaiting_payment_confirmation"] = False  # Also clear this flag
        elif error_type == PaymentErrorType.AMOUNT_OUT_OF_RANGE:
            result["awaiting_input"] = "amount"
        elif error_type == PaymentErrorType.AMOUNT_INVALID_FORMAT:
            result["awaiting_input"] = "amount"
        elif error_type == PaymentErrorType.YES_NO_UNCLEAR:
            result["awaiting_input"] = "payment_confirmation"
            result["awaiting_payment_confirmation"] = True

        # Special handling for link failures - increment error count
        if error_type == PaymentErrorType.LINK_FAILED and state:
            result["error_count"] = (state.get("error_count") or 0) + 1

        return result

    @classmethod
    async def handle_amount_error(
        cls,
        db: "AsyncSession",
        organization_id: "UUID",
        error_message: str,
        state: dict[str, Any] | None = None,
        total_debt: float | None = None,
    ) -> dict[str, Any]:
        """
        Handle amount validation error with custom message.

        Args:
            db: Database session
            organization_id: Organization UUID
            error_message: Custom error message
            state: Optional current state
            total_debt: Optional total debt for context

        Returns:
            State dict with error response
        """
        extra_context = {"range_message": error_message}
        if total_debt is not None:
            extra_context["total_debt"] = f"{total_debt:,.2f}"

        return await cls.handle(
            db=db,
            organization_id=organization_id,
            error_type=PaymentErrorType.AMOUNT_OUT_OF_RANGE,
            state=state,
            extra_context=extra_context,
        )
