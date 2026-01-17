# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Debt data fetching and preparation utilities.
#              Extracted from debt_manager_node.py to eliminate code duplication.
# Tenant-Aware: Yes - loads pharmacy config per organization.
# ============================================================================
"""
Debt data preparation utilities.

This module provides the DebtDataPreparer class that consolidates the
repeated fetch-prepare-format pattern from debt_manager_node.py.

Single Responsibility: Fetch and prepare debt data for display.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.tenancy.pharmacy_config_service import PharmacyConfig
from app.domains.pharmacy.domain.services.payment_options_service import PaymentOptionsService

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.debt_manager_node import DebtManagerService

logger = logging.getLogger(__name__)


@dataclass
class PreparedDebtData:
    """
    Container for prepared debt data.

    Groups all debt-related data needed for response formatting.
    """

    debt_data: dict[str, Any]
    """Raw debt data from PLEX."""

    pharmacy_config: PharmacyConfig | None
    """Pharmacy configuration for payment options."""

    payment_options: dict[str, Any]
    """Calculated payment options."""

    total_debt: float
    """Total debt amount."""

    @property
    def debt(self) -> Any:
        """Get the debt domain entity."""
        return self.debt_data.get("debt")

    @property
    def debt_items(self) -> list[dict[str, Any]]:
        """Get debt items list."""
        return self.debt_data.get("debt_items", [])

    @property
    def debt_id(self) -> str:
        """Get debt ID."""
        return self.debt_data.get("debt_id", "")


class DebtDataPreparer:
    """
    Prepares debt data for display.

    Single Responsibility: Fetch debt, load config, calculate payment options.

    This class consolidates the fetch-prepare pattern that was repeated
    in _handle_show_debt(), _handle_pay_debt_menu(), and _handle_invoice_detail().
    """

    def __init__(self, service: "DebtManagerService") -> None:
        """
        Initialize with debt manager service.

        Args:
            service: DebtManagerService instance for PLEX operations
        """
        self._service = service

    async def prepare(
        self,
        plex_user_id: int,
        customer_name: str,
        organization_id: str | UUID | None,
    ) -> PreparedDebtData | None:
        """
        Fetch and prepare debt data.

        Consolidates the repeated pattern:
        1. Fetch debt from PLEX
        2. Load pharmacy config
        3. Calculate payment options

        Args:
            plex_user_id: PLEX customer ID
            customer_name: Customer name for formatting
            organization_id: Organization UUID for config loading

        Returns:
            PreparedDebtData if customer has debt, None otherwise
        """
        # Fetch debt from PLEX
        debt_data = await self._service.get_customer_debt(plex_user_id, customer_name)

        if not debt_data:
            logger.debug(f"No debt found for PLEX user {plex_user_id}")
            return None

        # Load pharmacy config
        pharmacy_config = await self._service.load_pharmacy_config(organization_id)

        # Calculate payment options
        total_debt = debt_data["total_debt"]
        payment_options = PaymentOptionsService.calculate_options(total_debt, pharmacy_config)

        return PreparedDebtData(
            debt_data=debt_data,
            pharmacy_config=pharmacy_config,
            payment_options=payment_options,
            total_debt=total_debt,
        )

    async def prepare_or_cached(
        self,
        plex_user_id: int,
        customer_name: str,
        organization_id: str | UUID | None,
        cached_debt_items: list[Any] | None = None,
    ) -> PreparedDebtData | None:
        """
        Prepare debt data, using cached items if available.

        For invoice detail flow where debt_items may already be in state.

        Args:
            plex_user_id: PLEX customer ID
            customer_name: Customer name for formatting
            organization_id: Organization UUID for config loading
            cached_debt_items: Optional cached debt items from state

        Returns:
            PreparedDebtData if available, None otherwise
        """
        if cached_debt_items:
            # Use cached items, but still need config for formatting
            pharmacy_config = await self._service.load_pharmacy_config(organization_id)

            # Calculate total from cached items
            total_debt = sum(
                float(item.get("amount") or getattr(item, "amount", 0) or 0)
                for item in cached_debt_items
            )

            return PreparedDebtData(
                debt_data={
                    "debt_items": cached_debt_items,
                    "total_debt": total_debt,
                    "debt_id": "",
                },
                pharmacy_config=pharmacy_config,
                payment_options=PaymentOptionsService.calculate_options(total_debt, pharmacy_config),
                total_debt=total_debt,
            )

        # Fall back to fresh fetch
        return await self.prepare(plex_user_id, customer_name, organization_id)
