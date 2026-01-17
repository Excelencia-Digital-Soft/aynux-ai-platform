# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Payment processing utilities for pharmacy domain.
#              Extracted from payment_processor_node.py for SRP compliance.
# Tenant-Aware: Yes - organization_id handling and config loading.
# ============================================================================
"""
Payment processing utilities for pharmacy domain.

This module provides:
- payment_link_service: Mercado Pago payment link creation
- confirmation_handler: YES/NO pattern loading and matching
- amount_validator: Payment amount parsing and validation
- payment_state_builder: State dictionary builders for responses
- error_handlers: Consolidated error response generation
"""

from app.domains.pharmacy.agents.utils.payment.amount_validator import (
    AmountValidationResult,
    AmountValidator,
)
from app.domains.pharmacy.agents.utils.payment.confirmation_handler import (
    ConfirmationMatcher,
    ConfirmationPatternLoader,
    ConfirmationResult,
)
from app.domains.pharmacy.agents.utils.payment.error_handlers import (
    PaymentErrorHandler,
    PaymentErrorType,
)
from app.domains.pharmacy.agents.utils.payment.payment_link_service import (
    PaymentLinkResult,
    PaymentLinkService,
)
from app.domains.pharmacy.agents.utils.payment.payment_state_builder import (
    PaymentStateBuilder,
)

__all__ = [
    # Payment Link
    "PaymentLinkService",
    "PaymentLinkResult",
    # Confirmation
    "ConfirmationPatternLoader",
    "ConfirmationMatcher",
    "ConfirmationResult",
    # Amount Validation
    "AmountValidator",
    "AmountValidationResult",
    # State Builder
    "PaymentStateBuilder",
    # Error Handling
    "PaymentErrorHandler",
    "PaymentErrorType",
]
