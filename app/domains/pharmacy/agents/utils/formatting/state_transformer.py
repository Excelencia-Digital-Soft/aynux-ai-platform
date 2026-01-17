# ============================================================================
# SCOPE: MULTI-TENANT
# Description: State transformation for template variable building.
#              Extracted from ResponseFormatter._build_variables().
# Tenant-Aware: Yes - state contains organization-specific data.
# ============================================================================
"""
State transformation for template variable building.

This module handles the conversion of PharmacyStateV2 into a dictionary
of template variables for rendering WhatsApp messages.

Single Responsibility: State → Template Variables transformation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.utils.formatting.constants import (
    DEFAULT_CUSTOMER_NAME,
    DEFAULT_PHARMACY_NAME,
    FormattingLimits,
)

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2


class StateTransformer:
    """
    Transforms conversation state into template variables.

    Single Responsibility: State → Variables transformation.

    This class extracts data from PharmacyStateV2 and formats it
    for use in WhatsApp message templates.
    """

    def build_variables(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Build variables dictionary from state.

        Extracts relevant fields from state and formats them
        for template rendering.

        Args:
            state: Current conversation state

        Returns:
            Variables dictionary for template rendering
        """
        total_debt = state.get("total_debt") or 0
        payment_amount = state.get("payment_amount") or 0
        customer_name = state.get("customer_name") or ""

        debt_items = state.get("debt_items") or []
        debt_details = self._aggregate_debt_details(debt_items)

        return {
            "pharmacy_name": state.get("pharmacy_name") or DEFAULT_PHARMACY_NAME,
            "customer_name": customer_name or DEFAULT_CUSTOMER_NAME,
            "customer_name_greeting": f" {customer_name}" if customer_name else "",
            "total_debt": self._format_monetary_value(total_debt),
            "half_debt": self._format_monetary_value(total_debt / 2),
            "payment_amount": self._format_monetary_value(payment_amount),
            "remaining_balance": self._format_monetary_value(total_debt - payment_amount),
            "mp_payment_link": state.get("mp_payment_link") or "",
            "debt_details": debt_details,
        }

    def _aggregate_debt_details(
        self,
        debt_items: list[Any],
        max_invoices: int = FormattingLimits.MAX_INVOICES_DISPLAYED,
    ) -> str:
        """
        Aggregate debt items into formatted string.

        Groups items by invoice number and formats them for display.

        Args:
            debt_items: List of debt item dictionaries or objects
            max_invoices: Maximum invoices to display

        Returns:
            Formatted debt details string with invoice breakdown
        """
        if not debt_items:
            return ""

        invoices: dict[str, float] = {}
        for item in debt_items:
            if isinstance(item, dict):
                inv_num = item.get("invoice_number") or "Sin comprobante"
                amount = float(item.get("amount") or 0)
            else:
                inv_num = getattr(item, "invoice_number", "Sin comprobante")
                amount = float(getattr(item, "amount", 0))
            invoices[inv_num] = invoices.get(inv_num, 0) + amount

        lines = []
        for inv_num, inv_total in list(invoices.items())[:max_invoices]:
            lines.append(f"📄 {inv_num}: {self._format_monetary_value(inv_total)}")

        if len(invoices) > max_invoices:
            lines.append(f"... y {len(invoices) - max_invoices} comprobantes más")

        return "\n".join(lines)

    def _format_monetary_value(self, value: float | None) -> str:
        """
        Format monetary value as currency string.

        Args:
            value: Numeric value to format

        Returns:
            Formatted currency string (e.g., "$1,234.56")
        """
        if value is None:
            value = 0
        return f"${value:,.2f}"

    def build_invoice_variables(
        self,
        state: "PharmacyStateV2",
        base_variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build variables including invoice-specific data.

        Extends base variables with selected invoice details.

        Args:
            state: Current conversation state
            base_variables: Base variables dict to extend (builds if None)

        Returns:
            Extended variables with invoice data
        """
        variables = base_variables or self.build_variables(state)

        variables["invoice_number"] = state.get("selected_invoice_number") or "N/A"
        variables["invoice_date"] = state.get("selected_invoice_date") or "N/A"
        invoice_amount = state.get("selected_invoice_amount") or 0
        variables["invoice_amount"] = self._format_monetary_value(invoice_amount)

        return variables
