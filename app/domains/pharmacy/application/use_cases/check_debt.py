"""
Check Debt Use Case

Application use case for querying customer debt from pharmacy ERP.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domains.pharmacy.application.ports import IPharmacyERPPort
from app.domains.pharmacy.domain.entities.pharmacy_debt import DebtItem, PharmacyDebt
from app.domains.pharmacy.domain.value_objects.debt_status import DebtStatus


@dataclass
class CheckDebtRequest:
    """Request to check customer debt."""

    customer_id: str  # Phone number or ERP customer ID


@dataclass
class CheckDebtResponse:
    """Response from debt check operation."""

    success: bool
    debt: PharmacyDebt | None = None
    error: str | None = None
    has_debt: bool = False


class CheckDebtUseCase:
    """
    Use case for checking customer debt from pharmacy ERP.

    Single Responsibility: Query and transform debt data
    Dependency Inversion: Depends on IPharmacyERPPort abstraction
    """

    def __init__(self, erp_client: IPharmacyERPPort):
        """
        Initialize use case with ERP client.

        Args:
            erp_client: Implementation of IPharmacyERPPort
        """
        self._erp = erp_client

    async def execute(self, request: CheckDebtRequest) -> CheckDebtResponse:
        """
        Execute debt check use case.

        Args:
            request: CheckDebtRequest with customer_id

        Returns:
            CheckDebtResponse with debt information or error
        """
        try:
            if not request.customer_id:
                return CheckDebtResponse(
                    success=False,
                    error="Customer ID is required",
                )

            debt_data = await self._erp.get_customer_debt(request.customer_id)

            if not debt_data:
                return CheckDebtResponse(
                    success=True,
                    has_debt=False,
                    debt=None,
                )

            # Check if response indicates no debt
            if not debt_data.get("has_debt", True):
                return CheckDebtResponse(
                    success=True,
                    has_debt=False,
                    debt=None,
                )

            # Transform ERP response to domain entity
            debt = self._map_to_entity(debt_data)

            return CheckDebtResponse(
                success=True,
                debt=debt,
                has_debt=debt.total_debt > 0,
            )

        except Exception as e:
            return CheckDebtResponse(
                success=False,
                error=str(e),
            )

    def _map_to_entity(self, data: dict[str, Any]) -> PharmacyDebt:
        """
        Map ERP response to domain entity.

        Args:
            data: Raw ERP response data

        Returns:
            PharmacyDebt entity
        """
        # Map items from ERP format
        items: list[DebtItem] = []
        for item_data in data.get("items", []):
            items.append(
                DebtItem(
                    description=item_data.get("description", "Item"),
                    amount=Decimal(str(item_data.get("amount", 0))),
                    quantity=item_data.get("quantity", 1),
                    unit_price=(
                        Decimal(str(item_data["unit_price"]))
                        if item_data.get("unit_price")
                        else None
                    ),
                    product_code=item_data.get("product_code"),
                )
            )

        # Map status from ERP format
        status_value = data.get("status", "pending")
        try:
            status = DebtStatus(status_value)
        except ValueError:
            status = DebtStatus.PENDING

        return PharmacyDebt.from_dict(
            {
                "id": data.get("id", data.get("debt_id", "")),
                "customer_id": data.get("customer_id", ""),
                "customer_name": data.get("customer_name", "Cliente"),
                "total_debt": data.get("total_debt", data.get("total", 0)),
                "status": status.value,
                "due_date": data.get("due_date"),
                "items": [item.to_dict() for item in items],
                "created_at": data.get("created_at"),
                "notes": data.get("notes"),
            }
        )
