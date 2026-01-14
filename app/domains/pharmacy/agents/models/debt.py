"""Debt context state model."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.domains.pharmacy.agents.models.base import PharmacyStateModel


class DebtContext(PharmacyStateModel):
    """
    Debt context fields.

    Tracks debt-related state including amounts, status, and invoice details.
    """

    # Debt identification
    debt_id: str | None = Field(default=None, description="Current debt being processed")
    debt_data: dict[str, Any] | None = Field(default=None, description="Full debt information from Plex")
    debt_status: str | None = Field(default=None, description="pending, confirmed, invoiced")

    # Debt amounts
    total_debt: float | None = Field(default=None, description="Total debt amount")
    has_debt: bool = Field(default=False, description="True if customer has outstanding debt")

    # Debt details
    debt_items: list[dict[str, Any]] | None = Field(default=None, description="Detailed invoice items from PLEX")
    debt_fetched_at: str | None = Field(default=None, description="ISO timestamp when debt was fetched")

    # Debt action menu
    awaiting_debt_action: bool = Field(
        default=False, description="Waiting for user to select 1/2/3/4 after debt display"
    )

    # Confirmation
    awaiting_confirmation: bool = Field(default=False, description="Waiting for user to confirm debt")
    confirmation_received: bool = Field(default=False, description="User confirmed")

    # Invoice/Receipt
    invoice_id: str | None = Field(default=None, description="Generated invoice ID")
    invoice_number: str | None = Field(default=None, description="Invoice number")
    receipt_number: str | None = Field(default=None, description="For payment receipts")
    pdf_url: str | None = Field(default=None, description="PDF download URL")

    # Auth level for context-based obfuscation
    auth_level: str | None = Field(default=None, description="STRONG, MEDIUM, WEAK - for context-based obfuscation")

    def has_outstanding_debt(self) -> bool:
        """Check if there's outstanding debt."""
        return self.has_debt and self.total_debt is not None and self.total_debt > 0


__all__ = ["DebtContext"]
