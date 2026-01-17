# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Formatting utilities for WhatsApp response generation.
#              Extracted from response_formatter.py for SRP compliance.
# Tenant-Aware: Yes - state contains organization-specific data.
# ============================================================================
"""
Formatting utilities for pharmacy domain WhatsApp responses.

This module provides:
- constants: Magic numbers, enums for response types
- state_transformer: State → template variables transformation
- template_formatter: Generic template-based formatting
- intent_router: Intent → format decision routing
"""

from app.domains.pharmacy.agents.utils.formatting.constants import (
    DEFAULT_CUSTOMER_NAME,
    DEFAULT_PHARMACY_NAME,
    FormattingLimits,
    ResponseType,
)
from app.domains.pharmacy.agents.utils.formatting.intent_router import (
    FormatDecision,
    IntentFormatRouter,
)
from app.domains.pharmacy.agents.utils.formatting.state_transformer import (
    StateTransformer,
)
from app.domains.pharmacy.agents.utils.formatting.template_formatter import (
    TemplateBasedFormatter,
)

__all__ = [
    # Constants
    "FormattingLimits",
    "ResponseType",
    "DEFAULT_PHARMACY_NAME",
    "DEFAULT_CUSTOMER_NAME",
    # Classes
    "StateTransformer",
    "TemplateBasedFormatter",
    "IntentFormatRouter",
    "FormatDecision",
]
