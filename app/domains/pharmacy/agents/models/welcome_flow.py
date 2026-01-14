"""WelcomeFlowState model for typed state management in welcome flow."""

from __future__ import annotations

from pydantic import Field

from .base import PharmacyStateModel


class WelcomeFlowState(PharmacyStateModel):
    """
    Typed state model for the welcome flow handler.

    Provides type-safe access to welcome flow state fields,
    validation methods, and state extraction utilities.
    """

    # Pharmacy context (multi-tenant)
    pharmacy_name: str | None = Field(default=None, description="Pharmacy name")
    pharmacy_id: str | None = Field(default=None, description="Pharmacy ID")
    organization_id: str | None = Field(default=None, description="Organization ID for multi-tenancy")

    # Welcome flow state
    identification_step: str | None = Field(default=None, description="Current identification step")
    identification_retries: int = Field(default=0, description="Number of identification retries")

    # Payment context (preserved from router)
    payment_amount: float | None = Field(default=None, description="Payment amount from user intent")

    # Registration flow
    awaiting_registration_data: bool = Field(default=False, description="Whether awaiting registration data")
    registration_step: str | None = Field(default=None, description="Current registration step")

    # Routing
    next_node: str | None = Field(default=None, description="Next node to route to")
    pharmacy_intent_type: str | None = Field(default=None, description="Detected pharmacy intent type")

    def has_payment_context(self) -> bool:
        """Check if payment context is present."""
        return self.payment_amount is not None and self.payment_amount > 0

    def validate_org_id(self) -> None:
        """
        Validate that organization_id is present.

        Raises:
            ValueError: If organization_id is None or empty
        """
        if not self.organization_id:
            raise ValueError("organization_id required for welcome flow")


__all__ = ["WelcomeFlowState"]
