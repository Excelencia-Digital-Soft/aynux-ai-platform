"""
Pharmacy Application Ports

Protocol interfaces defining the contracts for external services.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class IPharmacyERPPort(Protocol):
    """
    Port interface for Pharmacy ERP integration.

    Defines the contract for external ERP communication.
    Implemented by PharmacyERPClient in infrastructure.
    """

    async def get_customer_debt(self, customer_id: str) -> dict | None:
        """
        Fetch customer's current debt from ERP.

        Args:
            customer_id: Customer phone number or ERP ID

        Returns:
            Debt data dict or None if no debt found
        """
        ...

    async def confirm_debt(self, debt_id: str, customer_id: str) -> dict:
        """
        Confirm a debt in the ERP system.

        Args:
            debt_id: Debt identifier
            customer_id: Customer identifier

        Returns:
            Confirmation result with status
        """
        ...

    async def generate_invoice(self, debt_id: str, customer_id: str) -> dict:
        """
        Generate invoice for confirmed debt.

        Args:
            debt_id: Confirmed debt identifier
            customer_id: Customer identifier

        Returns:
            Invoice data including invoice_number and optional pdf_url
        """
        ...

    async def test_connection(self) -> bool:
        """Test ERP connectivity."""
        ...


__all__ = ["IPharmacyERPPort"]
