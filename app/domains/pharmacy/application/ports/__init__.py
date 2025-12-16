"""
Pharmacy Application Ports

Protocol interfaces defining the contracts for external services.
These ports enable dependency inversion - use cases depend on abstractions,
not concrete implementations.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.domains.pharmacy.domain.entities.plex_customer import PlexCustomer


@runtime_checkable
class IPlexERPPort(Protocol):
    """
    Port interface for Plex ERP integration.

    Defines the contract for external Plex ERP communication.
    Implemented by PlexClient in app/clients/plex_client.py.

    The Plex API uses HTTP Basic Auth and requires a 2-step flow:
    1. Search customer by phone/document to get internal ID
    2. Query balance/create receipt using the internal ID
    """

    # =========================================================================
    # Customer Search Methods
    # =========================================================================

    async def search_customer(
        self,
        phone: str | None = None,
        document: str | None = None,
        email: str | None = None,
        cuit: str | None = None,
        customer_id: int | None = None,
    ) -> list[PlexCustomer]:
        """
        Search for customers by criteria.

        Args:
            phone: Phone number (will be normalized from WhatsApp format)
            document: Document number (DNI)
            email: Email address
            cuit: Tax ID
            customer_id: Direct Plex customer ID

        Returns:
            List of matching PlexCustomer entities.
            May be empty (no matches) or contain multiple (disambiguation needed).
        """
        ...

    # =========================================================================
    # Balance Query Methods
    # =========================================================================

    async def get_customer_balance(
        self,
        customer_id: int,
        detailed: bool = True,
        fecha_hasta: date | None = None,
    ) -> dict | None:
        """
        Get customer balance/debt details.

        Args:
            customer_id: Plex internal customer ID (from search_customer)
            detailed: True for line items, False for summary only
            fecha_hasta: Balance cutoff date (defaults to today)

        Returns:
            Balance data dict with saldo, detalle, etc.
            None if no balance found.
        """
        ...

    # =========================================================================
    # Receipt/Payment Methods
    # =========================================================================

    async def create_receipt(
        self,
        customer_id: int,
        amount: Decimal,
        items: list[dict] | None = None,
        fecha: date | None = None,
    ) -> dict:
        """
        Create a payment receipt in Plex ERP.

        Args:
            customer_id: Plex internal customer ID
            amount: Total payment amount
            items: List of payment items/details (optional)
            fecha: Receipt date (defaults to today)

        Returns:
            Receipt confirmation data including receipt number
        """
        ...

    # =========================================================================
    # Customer Registration Methods
    # =========================================================================

    async def create_customer(
        self,
        nombre: str,
        documento: str,
        telefono: str,
        email: str | None = None,
        direccion: str | None = None,
    ) -> PlexCustomer:
        """
        Register a new customer in Plex ERP.

        Args:
            nombre: Customer full name
            documento: Document number (DNI)
            telefono: Phone number
            email: Email address (optional)
            direccion: Address (optional)

        Returns:
            Created PlexCustomer instance with assigned ID
        """
        ...

    # =========================================================================
    # Connection Test
    # =========================================================================

    async def test_connection(self) -> bool:
        """
        Test Plex ERP connectivity.

        Returns:
            True if connection successful, False otherwise
        """
        ...


# Backward compatibility alias
IPharmacyERPPort = IPlexERPPort

__all__ = ["IPlexERPPort", "IPharmacyERPPort"]
