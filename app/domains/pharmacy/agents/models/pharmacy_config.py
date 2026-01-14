"""Pharmacy configuration state model."""

from __future__ import annotations

from pydantic import Field

from app.domains.pharmacy.agents.models.base import PharmacyStateModel


class PharmacyConfig(PharmacyStateModel):
    """
    Pharmacy configuration fields that must be preserved.

    These fields identify the pharmacy context for multi-tenant support
    and personalized responses.
    """

    pharmacy_id: str | None = Field(
        default=None, description="Pharmacy UUID for pharmacy-specific config (MP credentials, etc.)"
    )
    pharmacy_name: str | None = Field(default=None, description="Pharmacy name for personalized responses")
    pharmacy_phone: str | None = Field(default=None, description="Pharmacy phone for contact redirection")
    organization_id: str | None = Field(default=None, description="Organization UUID for multi-tenant config lookup")
    emergency_phone: str | None = Field(default=None, description="Emergency contact number")


__all__ = ["PharmacyConfig"]
