"""
Preserved context model and utilities for state preservation.

This module provides the main interface for preserving state across
node transitions in the pharmacy LangGraph.

Usage:
    from app.domains.pharmacy.agents.models import StatePreserver

    # In a node or handler:
    def _some_method(self, state_dict: dict) -> dict:
        preserved = StatePreserver.extract_all(state_dict)
        return {
            "customer_identified": True,
            "messages": [...],
            **preserved,  # Preserves payment_amount, pharmacy_config, etc.
        }
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import Field

from app.domains.pharmacy.agents.models.base import PharmacyStateModel

logger = logging.getLogger(__name__)


class PreservedContext(PharmacyStateModel):
    """
    Context fields that must be preserved across node transitions.

    These fields capture important information from the initial router
    classification that should not be lost during node transitions.

    This is a focused subset of state fields that are commonly lost
    when nodes return partial state updates. By explicitly preserving
    these, we ensure critical context like payment_amount survives
    through flows like person identification.

    Example flow:
        User: "quiero pagar 3000"
        → Router: payment_amount=3000
        → PersonResolutionNode: Identification flow
        → _complete_identification(): Uses PreservedContext
        → DebtCheckNode: Receives payment_amount=3000
    """

    # Payment context - CRITICAL for preserving amount from initial message
    payment_amount: float | None = Field(
        default=None, description="Amount customer wants to pay (from initial message like 'pagar 3000')"
    )
    is_partial_payment: bool = Field(default=False, description="True if payment_amount < total_debt")
    remaining_balance: float | None = Field(default=None, description="Balance after payment")
    selected_payment_option: str | None = Field(
        default=None, description="Selected option: 'full', 'half', 'minimum', 'custom'"
    )

    # Intent context
    pharmacy_intent_type: str | None = Field(
        default=None, description="Intent type: debt_query, confirm, invoice, payment_link, etc."
    )
    extracted_entities: dict[str, Any] | None = Field(
        default=None, description="Entities extracted from message (amount, date, etc.)"
    )

    # Auto-flow flags
    auto_proceed_to_invoice: bool = Field(default=False, description="Auto-fetch debt then proceed to invoice")
    auto_return_to_query: bool = Field(default=False, description="Return to data_query after debt fetch")
    pending_data_query: str | None = Field(default=None, description="Pending question to answer after debt fetch")

    # Pharmacy config - for multi-tenant context
    pharmacy_id: str | None = Field(default=None, description="Pharmacy UUID")
    pharmacy_name: str | None = Field(default=None, description="Pharmacy name for personalized responses")
    pharmacy_phone: str | None = Field(default=None, description="Pharmacy phone for contact redirection")
    organization_id: str | None = Field(default=None, description="Organization UUID for multi-tenant config")

    # Identification flow state (CRITICAL for multi-turn identification)
    identification_step: str | None = Field(
        default=None, description="Current step in identification flow: awaiting_welcome, awaiting_identifier, name"
    )
    plex_customer_to_confirm: dict[str, Any] | None = Field(
        default=None, description="Customer from PLEX awaiting name verification"
    )
    name_mismatch_count: int = Field(default=0, description="Number of name verification failures")
    awaiting_own_or_other: bool = Field(default=False, description="Waiting for user to confirm own account or other")
    validation_step: str | None = Field(default=None, description="Legacy validation step identifier")

    # Registration flow state
    awaiting_registration_data: bool = Field(
        default=False, description="Waiting for registration data (name, document, etc.)"
    )
    registration_step: str | None = Field(
        default=None, description="Current step in registration flow: nombre, documento, confirmar"
    )

    # Account selection state
    registered_accounts_for_selection: list[dict[str, Any]] | None = Field(
        default=None, description="List of registered accounts available for selection"
    )
    account_count: int | None = Field(default=None, description="Number of registered accounts")

    def has_payment_context(self) -> bool:
        """Check if this context has payment information."""
        return self.payment_amount is not None or self.selected_payment_option is not None

    def has_pharmacy_context(self) -> bool:
        """Check if pharmacy configuration is present."""
        return self.pharmacy_id is not None or self.pharmacy_name is not None


class StatePreserver:
    """
    Utility class for preserving state across node transitions.

    Provides static methods to extract and validate preserved state,
    making it easy to ensure context is not lost during graph execution.

    Usage:
        # Get all preserved fields as a dict for state merging
        preserved = StatePreserver.extract_all(state_dict)
        return {
            "customer_identified": True,
            **preserved,
        }

        # Validate required fields are present
        is_valid, missing = StatePreserver.validate_required(
            state_dict,
            ["payment_amount", "pharmacy_id"]
        )
    """

    @staticmethod
    def extract_all(state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Extract all preserved fields from state.

        This is the main method to use in nodes and handlers to
        ensure all important context is preserved across transitions.

        Args:
            state_dict: Current state dictionary

        Returns:
            Dictionary with all preserved fields (non-None only)
        """
        ctx = PreservedContext.from_state(state_dict)
        return ctx.to_state_update()

    @staticmethod
    def extract_payment_context(state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Extract only payment-related preserved fields.

        Args:
            state_dict: Current state dictionary

        Returns:
            Dictionary with payment context fields (non-None only)
        """
        ctx = PreservedContext.from_state(state_dict)
        payment_fields = {
            "payment_amount",
            "is_partial_payment",
            "remaining_balance",
            "selected_payment_option",
        }
        full_dict = ctx.to_state_update()
        return {k: v for k, v in full_dict.items() if k in payment_fields}

    @staticmethod
    def extract_pharmacy_config(state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Extract only pharmacy configuration fields.

        Args:
            state_dict: Current state dictionary

        Returns:
            Dictionary with pharmacy config fields (non-None only)
        """
        ctx = PreservedContext.from_state(state_dict)
        config_fields = {
            "pharmacy_id",
            "pharmacy_name",
            "pharmacy_phone",
            "organization_id",
        }
        full_dict = ctx.to_state_update()
        return {k: v for k, v in full_dict.items() if k in config_fields}

    @staticmethod
    def get_model(state_dict: dict[str, Any]) -> PreservedContext:
        """
        Get the PreservedContext model instance.

        Useful when you need to use model methods like has_payment_context().

        Args:
            state_dict: Current state dictionary

        Returns:
            PreservedContext model instance
        """
        return PreservedContext.from_state(state_dict)

    @staticmethod
    def validate_required(
        state_dict: dict[str, Any],
        required_fields: list[str],
    ) -> tuple[bool, list[str]]:
        """
        Validate that required context fields are present.

        Useful for debugging missing state issues.

        Args:
            state_dict: Current state dictionary
            required_fields: List of field names that must have non-None values

        Returns:
            Tuple of (is_valid, missing_fields)

        Example:
            is_valid, missing = StatePreserver.validate_required(
                state_dict, ["payment_amount", "pharmacy_id"]
            )
            if not is_valid:
                logger.warning(f"Missing required fields: {missing}")
        """
        ctx = PreservedContext.from_state(state_dict)
        ctx_dict = ctx.model_dump()

        missing = [field for field in required_fields if ctx_dict.get(field) is None]

        return len(missing) == 0, missing

    @staticmethod
    def log_preserved_state(
        state_dict: dict[str, Any],
        context: str = "",
    ) -> None:
        """
        Log the current preserved state for debugging.

        Args:
            state_dict: Current state dictionary
            context: Optional context string for the log message
        """
        ctx = PreservedContext.from_state(state_dict)
        preserved = ctx.to_state_update()

        prefix = f"[{context}] " if context else ""
        logger.debug(
            f"{prefix}Preserved state: payment_amount={ctx.payment_amount}, "
            f"pharmacy_intent={ctx.pharmacy_intent_type}, "
            f"pharmacy_id={ctx.pharmacy_id}, "
            f"fields_count={len(preserved)}"
        )


__all__ = [
    "PreservedContext",
    "StatePreserver",
]
