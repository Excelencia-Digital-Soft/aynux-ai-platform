# ============================================================================
# SCOPE: MULTI-TENANT
# Description: State dictionary builders for payment responses.
#              Extracted from payment_processor_node.py for SRP compliance.
# Tenant-Aware: No - pure state construction logic.
# ============================================================================
"""
State dictionary builders for payment responses.

Single Responsibility: Build consistent state dictionaries for payment operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.utils.payment.payment_link_service import PaymentLinkResult


class PaymentStateBuilder:
    """
    Builds state dictionaries for payment responses.

    Single Responsibility: Construct consistent state updates for payment flows.

    This class provides static methods to build state dictionaries for:
    - Payment confirmation requests
    - Payment link success responses
    - Payment cancellation
    - Amount input awaiting
    """

    @staticmethod
    def confirmation_request(
        amount: float,
        total_debt: float,
        is_partial: bool,
        current_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build state for payment confirmation request.

        Args:
            amount: Payment amount
            total_debt: Total debt amount
            is_partial: Whether this is a partial payment
            current_state: Optional current state to merge

        Returns:
            State dict for confirmation request
        """
        remaining = total_debt - amount if is_partial else 0

        return {
            "current_node": "payment_processor",
            "payment_amount": amount,
            "is_partial_payment": is_partial,
            "awaiting_input": "payment_confirmation",
            "awaiting_payment_confirmation": True,
            # Template variables
            "_template_vars": {
                "payment_amount": f"{amount:,.2f}",
                "total_debt": f"{total_debt:,.2f}",
                "remaining_balance": f"{remaining:,.2f}",
            },
        }

    @staticmethod
    def payment_link_success(
        result: "PaymentLinkResult",
        customer_name: str,
        amount: float,
        total_debt: float,
        is_partial: bool,
        pharmacy_name: str,
    ) -> dict[str, Any]:
        """
        Build state for successful payment link generation.

        Args:
            result: PaymentLinkResult from link creation
            customer_name: Customer name for response
            amount: Payment amount
            total_debt: Total debt amount
            is_partial: Whether this is a partial payment
            pharmacy_name: Pharmacy name for response

        Returns:
            State dict for payment link success
        """
        remaining = total_debt - amount if is_partial else 0

        return {
            "current_node": "payment_processor",
            "agent_history": ["payment_processor"],
            # Mercado Pago data
            "mp_payment_link": result.init_point,
            "mp_payment_status": "pending",
            "mp_external_reference": result.external_reference,
            # Clear awaiting flags
            "awaiting_payment_confirmation": False,
            "awaiting_input": None,
            # Complete conversation
            "is_complete": True,
            "next_node": "__end__",
            # Template variables
            "_template_vars": {
                "customer_name": customer_name,
                "payment_amount": f"{amount:,.2f}",
                "total_debt": f"{total_debt:,.2f}",
                "remaining_balance": f"{remaining:,.2f}",
                "payment_link": result.init_point,
                "pharmacy_name": pharmacy_name,
            },
        }

    @staticmethod
    def cancellation() -> dict[str, Any]:
        """
        Build state for payment cancellation.

        Returns:
            State dict for cancellation
        """
        return {
            "current_node": "payment_processor",
            "awaiting_payment_confirmation": False,
            "awaiting_input": None,
            "payment_amount": None,
            "is_partial_payment": False,
            "is_complete": True,
        }

    @staticmethod
    def awaiting_amount(is_partial: bool = True) -> dict[str, Any]:
        """
        Build state for awaiting amount input.

        Args:
            is_partial: Whether we expect a partial payment

        Returns:
            State dict for awaiting amount
        """
        return {
            "current_node": "payment_processor",
            "awaiting_input": "amount",
            "is_partial_payment": is_partial,
        }

    @staticmethod
    def unclear_confirmation() -> dict[str, Any]:
        """
        Build state for unclear confirmation response.

        Returns:
            State dict for unclear confirmation
        """
        return {
            "current_node": "payment_processor",
            "awaiting_input": "payment_confirmation",
            "awaiting_payment_confirmation": True,
        }

    @staticmethod
    def error_state(
        error_count: int = 0,
        is_complete: bool = True,
    ) -> dict[str, Any]:
        """
        Build state for error scenarios.

        Args:
            error_count: Current error count (will be incremented)
            is_complete: Whether to mark conversation as complete

        Returns:
            State dict for error
        """
        return {
            "current_node": "payment_processor",
            "error_count": error_count + 1,
            "is_complete": is_complete,
            "awaiting_input": None,
        }

    @staticmethod
    def redirect_to_debt() -> dict[str, Any]:
        """
        Build state for redirecting to debt manager.

        Returns:
            State dict for debt redirect
        """
        return {
            "current_node": "payment_processor",
            "next_node": "debt_manager",
        }
