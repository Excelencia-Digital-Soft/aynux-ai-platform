# ============================================================================
# SCOPE: MULTI-TENANT
# Description: LangGraph node for WhatsApp message formatting.
#              REFACTORED: Extracted responsibilities into utils/formatting/.
# Tenant-Aware: Yes - state contains organization-specific data.
# ============================================================================
"""
Response Formatter Node - LangGraph node for WhatsApp message formatting.

This module provides the LangGraph node function for formatting responses
for WhatsApp delivery. All formatting logic is delegated to specialized
components in utils/formatting/.

REFACTORED: Extracted responsibilities into:
- constants.py: Magic numbers and enums
- state_transformer.py: State → Variables transformation
- template_formatter.py: Generic template-based formatting
- intent_router.py: Intent → Format routing

Response Types Supported:
- text: Simple text message
- buttons: Up to 3 reply buttons
- list: Interactive list with up to 10 items
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from app.domains.pharmacy.agents.utils.formatting import (
    IntentFormatRouter,
    TemplateBasedFormatter,
)

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


# Singleton instances
_formatter: TemplateBasedFormatter | None = None
_router: IntentFormatRouter | None = None


def get_formatter() -> TemplateBasedFormatter:
    """Get or create singleton formatter instance."""
    global _formatter
    if _formatter is None:
        _formatter = TemplateBasedFormatter()
    return _formatter


def get_intent_router() -> IntentFormatRouter:
    """Get or create singleton router instance."""
    global _router
    if _router is None:
        _router = IntentFormatRouter()
    return _router


def invalidate_response_formatter_cache() -> None:
    """
    Invalidate the response formatter singleton and template cache.

    Forces templates to be reloaded on next access.
    Call this after modifying whatsapp_formatter.yaml.
    """
    global _formatter
    from app.domains.pharmacy.agents.utils.whatsapp_template_loader import (
        invalidate_whatsapp_template_cache,
    )

    invalidate_whatsapp_template_cache()
    if _formatter is not None:
        _formatter.invalidate_cache()
    _formatter = None
    logger.info("Response formatter cache invalidated")


async def response_formatter_node(
    state: "PharmacyStateV2",
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """
    LangGraph node function for response formatting.

    This node determines the appropriate format based on state and intent,
    then delegates to the template-based formatter.

    Args:
        state: Current conversation state
        config: Optional configuration

    Returns:
        State updates with response formatting and AIMessage
    """
    router = get_intent_router()
    formatter = get_formatter()

    # Get format decision from router
    decision = router.route(state)

    logger.info(
        f"[RESPONSE_FORMATTER] Routing to template={decision.template_key}, "
        f"intent={state.get('intent')}, awaiting={state.get('awaiting_input')}"
    )

    # Skip formatting if the previous node already provided a response
    if decision.template_key == "skip_formatting":
        logger.info("[RESPONSE_FORMATTER] Skipping formatting - preserving node response")
        # Return minimal state update to preserve existing messages
        # Don't set is_complete=True since we're awaiting user input
        return {
            "current_node": "response_formatter",
        }

    # Format using template
    result = await formatter.format(
        template_key=decision.template_key,
        state=state,
        extra_variables=decision.extra_variables,
        response_type_override=decision.response_type_override,
    )

    # Add AIMessage for extract_bot_response()
    body = result.get("_formatted_body", "")
    if body:
        result["messages"] = [AIMessage(content=body)]

    logger.info(
        f"[RESPONSE_FORMATTER] Formatted response_type={result.get('response_type')}, "
        f"buttons_count={len(result.get('response_buttons') or [])}"
    )

    return result


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================
# The following code provides backward compatibility for code that uses
# the old ResponseFormatter class directly. New code should use the
# components from utils/formatting/ directly.


class ResponseFormatter:
    """
    Backward compatibility wrapper for ResponseFormatter.

    DEPRECATED: Use TemplateBasedFormatter from utils/formatting/ directly.

    This class provides the same interface as the original ResponseFormatter
    but delegates to the new TemplateBasedFormatter internally.
    """

    def __init__(self) -> None:
        """Initialize with TemplateBasedFormatter."""
        self._formatter = get_formatter()

    async def _ensure_templates_loaded(self) -> Any:
        """Ensure templates are loaded."""
        return await self._formatter._ensure_templates_loaded()

    async def format_debt_response(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format debt display with action buttons."""
        return await self._formatter.format("debt_response", state)

    async def format_payment_confirmation(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format payment confirmation with Yes/No buttons."""
        is_partial = state.get("is_partial_payment", False)
        template_key = "payment_confirmation_partial" if is_partial else "payment_confirmation_full"
        return await self._formatter.format(template_key, state)

    async def format_payment_link(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format payment link message."""
        return await self._formatter.format("payment_link", state)

    async def format_account_selection(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format account selection list."""
        return await self._formatter.format("account_selection", state)

    async def format_own_or_other(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format own/other debt selection."""
        return await self._formatter.format("own_or_other", state)

    async def format_main_menu(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format main menu message with WhatsApp interactive buttons."""
        return await self._formatter.format("main_menu", state)

    async def format_pay_debt_menu(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format PAY_DEBT_MENU response."""
        return await self._formatter.format("pay_debt_menu", state)

    async def format_invoice_detail(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format INVOICE_DETAIL response."""
        return await self._formatter.format("invoice_detail", state)

    async def format_no_debt(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format no debt message."""
        return await self._formatter.format("no_debt", state)

    async def format_error(
        self,
        error_type: str,
        state: "PharmacyStateV2",
    ) -> dict[str, Any]:
        """Format error message."""
        template_key = f"error_{error_type}"
        result = await self._formatter.format(template_key, state)
        # Handle error_count increment
        result["error_count"] = (state.get("error_count") or 0) + 1
        return result

    async def format_farewell(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format farewell message."""
        return await self._formatter.format("farewell", state)

    async def format_request_dni(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format DNI request message."""
        return await self._formatter.format("request_dni", state)

    async def format_request_name(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Format name request message."""
        return await self._formatter.format("request_name", state)


def get_response_formatter() -> ResponseFormatter:
    """
    Get response formatter instance.

    DEPRECATED: Use get_formatter() or TemplateBasedFormatter directly.
    """
    return ResponseFormatter()
