# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Intent-to-format routing for response generation.
#              Extracted from response_formatter_node() to reduce complexity.
# Tenant-Aware: Yes - state contains organization-specific data.
# ============================================================================
"""
Intent-to-format routing for response generation.

This module maps intents to format decisions, extracting the routing logic
from response_formatter_node() to reduce cyclomatic complexity.

Single Responsibility: Intent → FormatDecision mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2


@dataclass
class FormatDecision:
    """
    Represents a formatting decision.

    Contains the template key and any additional configuration
    needed for formatting the response.
    """

    template_key: str
    """Template key to use for formatting."""

    extra_variables: dict[str, Any] | None = field(default=None)
    """Additional variables to merge into template context."""

    response_type_override: str | None = field(default=None)
    """Override the template's default response type."""


class IntentFormatRouter:
    """
    Routes intents to appropriate format decisions.

    Single Responsibility: Intent → FormatDecision mapping.

    This class extracts the intent routing logic from response_formatter_node()
    to reduce cyclomatic complexity and improve testability.
    """

    def route(self, state: "PharmacyStateV2") -> FormatDecision:
        """
        Determine format decision based on state.

        Priority order:
        1. validation_failed - contact pharmacy message
        2. awaiting_input (account_number, account_not_found, dni, name) - auth flow
        3. intent-specific routing (farewell when intent == "farewell")
        4. default - main_menu

        Note: is_complete is NOT used for routing to avoid stale checkpoint values.
        Farewell is only shown when intent is explicitly "farewell".

        Args:
            state: Current conversation state

        Returns:
            FormatDecision with template_key and options
        """
        awaiting_input = state.get("awaiting_input")
        intent = state.get("intent")
        has_debt = state.get("has_debt", False)
        validation_failed = state.get("validation_failed", False)

        # Priority 0: Skip formatting if a previous node already set the response
        # (e.g., error handlers that generate their own error messages)
        if state.get("skip_response_formatting"):
            return FormatDecision(template_key="skip_formatting")

        # Priority 1: Validation failed - contact pharmacy
        if validation_failed:
            return FormatDecision(template_key="validation_failed")

        # Priority 2: awaiting_input for auth flow
        if awaiting_input == "account_number":
            return FormatDecision(template_key="request_account_number")
        if awaiting_input == "account_not_found":
            return FormatDecision(template_key="account_not_found")
        if awaiting_input == "dni":
            return FormatDecision(template_key="request_dni")
        if awaiting_input == "name":
            return FormatDecision(template_key="request_name")

        # Priority 2.4: Payment link already generated - show it!
        # Must come BEFORE payment_confirmation check to avoid showing
        # confirmation dialog again after successful payment processing.
        # IMPORTANT: Only show payment link if the current intent is payment-related.
        # This prevents an infinite loop where ANY message after payment link generation
        # would show the payment link again, ignoring new intents like "cancelar".
        payment_intents = {"pay_full", "pay_partial", "payment_link", "pay_debt_menu"}
        if state.get("mp_payment_link") and intent in payment_intents:
            return FormatDecision(template_key="payment_link")

        # Priority 2.5: awaiting_input for payment flow (before intent routing)
        # This ensures payment confirmation is shown even when intent is still "pay_debt_menu"
        # Only reached if no payment link exists yet.
        if awaiting_input == "payment_confirmation":
            is_partial = state.get("is_partial_payment", False)
            template = "payment_confirmation_partial" if is_partial else "payment_confirmation_full"
            return FormatDecision(template_key=template)

        # NOTE: Removed is_complete check - farewell is now only used when intent == "farewell"
        # This prevents stale checkpoint values from redirecting all responses to farewell

        # Priority 3: Intent-specific routing
        return self._route_by_intent(intent, state, has_debt)

    def _route_by_intent(
        self,
        intent: str | None,
        state: "PharmacyStateV2",
        has_debt: bool,
    ) -> FormatDecision:
        """
        Route based on intent value.

        Args:
            intent: Current intent from state
            state: Full conversation state
            has_debt: Whether customer has debt

        Returns:
            FormatDecision for the intent
        """
        # Debt query intents
        if intent in ("check_debt", "debt_query"):
            template = "debt_response" if has_debt else "no_debt"
            return FormatDecision(template_key=template)

        # Pay debt menu flow
        if intent == "pay_debt_menu":
            template = "pay_debt_menu" if has_debt else "no_debt"
            return FormatDecision(template_key=template)

        # Invoice detail
        if intent == "view_invoice_detail":
            return FormatDecision(template_key="invoice_detail")

        # Payment intents
        if intent in ("pay_full", "pay_partial", "payment_link"):
            return self._route_payment_intent(state)

        # Account switching
        if intent == "switch_account":
            if state.get("awaiting_account_selection"):
                return FormatDecision(template_key="account_selection")
            return FormatDecision(template_key="own_or_other")

        # Auth success - post-validation menu with verification message
        if intent == "auth_success":
            return FormatDecision(template_key="auth_success_menu")

        # Menu and farewell
        if intent == "show_menu":
            return FormatDecision(template_key="main_menu")
        if intent == "farewell":
            return FormatDecision(template_key="farewell")

        # Default: main menu
        return FormatDecision(template_key="main_menu")

    def _route_payment_intent(self, state: "PharmacyStateV2") -> FormatDecision:
        """
        Route payment-related intents.

        Determines the appropriate template based on payment state:
        - Has payment link → payment_link template
        - Awaiting confirmation → confirmation template (full or partial)
        - Awaiting amount input → skip formatting (node already sent response)
        - Otherwise → debt_response template

        Args:
            state: Current conversation state

        Returns:
            FormatDecision for payment flow
        """
        if state.get("mp_payment_link"):
            return FormatDecision(template_key="payment_link")

        if state.get("awaiting_payment_confirmation"):
            is_partial = state.get("is_partial_payment", False)
            template = "payment_confirmation_partial" if is_partial else "payment_confirmation_full"
            return FormatDecision(template_key=template)

        # If awaiting amount input, show partial payment template with 50% suggestion
        if state.get("awaiting_input") == "amount":
            return FormatDecision(template_key="payment_amount_request")

        return FormatDecision(template_key="debt_response")
