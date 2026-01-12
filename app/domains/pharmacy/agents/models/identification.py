"""Identification state model."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.domains.pharmacy.agents.models.base import PharmacyStateModel


class IdentificationState(PharmacyStateModel):
    """
    Identification flow state fields.

    Tracks the progress of customer identification through the flow,
    from initial contact to confirmed Plex customer.
    """

    # Customer identification result
    customer_identified: bool = Field(
        default=False,
        description="True if Plex customer is resolved"
    )
    plex_customer_id: int | None = Field(
        default=None,
        description="Plex internal customer ID (e.g., 70)"
    )
    plex_customer: dict[str, Any] | None = Field(
        default=None,
        description="Full PlexCustomer data as dict"
    )
    customer_name: str | None = Field(
        default=None,
        description="Customer display name (from Plex or registration)"
    )

    # Identification flow state
    identification_step: str | None = Field(
        default=None,
        description="Current step: 'awaiting_welcome', 'awaiting_identifier', 'name'"
    )
    identification_retries: int = Field(
        default=0,
        description="Number of identification attempts (max 3)"
    )
    just_identified: bool = Field(
        default=False,
        description="True if customer was just identified this turn"
    )

    # Pending confirmation
    plex_customer_to_confirm: dict[str, Any] | None = Field(
        default=None,
        description="PLEX customer pending confirmation"
    )
    provided_name_to_confirm: str | None = Field(
        default=None,
        description="Name provided by user pending confirmation"
    )
    name_mismatch_count: int = Field(
        default=0,
        description="Count of name mismatches for retry limiting"
    )

    # Person resolution state
    is_self: bool = Field(
        default=False,
        description="True if current customer is the phone owner"
    )
    is_querying_for_other: bool = Field(
        default=False,
        description="True if querying debt for someone else"
    )
    awaiting_own_or_other: bool = Field(
        default=False,
        description="Waiting for 'own debt' or 'other's debt' answer"
    )
    awaiting_person_selection: bool = Field(
        default=False,
        description="Waiting for user to select a person from list"
    )

    def is_complete(self) -> bool:
        """Check if identification is complete."""
        return self.customer_identified and self.plex_customer_id is not None


__all__ = ["IdentificationState"]
