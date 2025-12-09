"""
Confirm Debt Use Case

Application use case for confirming customer debt in pharmacy ERP.
"""

from dataclasses import dataclass
from typing import Any

from app.domains.pharmacy.application.ports import IPharmacyERPPort
from app.domains.pharmacy.domain.entities.pharmacy_debt import PharmacyDebt


@dataclass
class ConfirmDebtRequest:
    """Request to confirm debt."""

    debt_id: str
    customer_id: str


@dataclass
class ConfirmDebtResponse:
    """Response from debt confirmation operation."""

    success: bool
    confirmed: bool = False
    debt: PharmacyDebt | None = None
    error: str | None = None


class ConfirmDebtUseCase:
    """
    Use case for confirming debt in pharmacy ERP.

    Single Responsibility: Handle debt confirmation workflow
    Dependency Inversion: Depends on IPharmacyERPPort abstraction
    """

    def __init__(self, erp_client: IPharmacyERPPort):
        """
        Initialize use case with ERP client.

        Args:
            erp_client: Implementation of IPharmacyERPPort
        """
        self._erp = erp_client

    async def execute(self, request: ConfirmDebtRequest) -> ConfirmDebtResponse:
        """
        Execute debt confirmation use case.

        Args:
            request: ConfirmDebtRequest with debt_id and customer_id

        Returns:
            ConfirmDebtResponse with confirmation status or error
        """
        try:
            if not request.debt_id:
                return ConfirmDebtResponse(
                    success=False,
                    error="Debt ID is required",
                )

            if not request.customer_id:
                return ConfirmDebtResponse(
                    success=False,
                    error="Customer ID is required",
                )

            result = await self._erp.confirm_debt(
                request.debt_id,
                request.customer_id,
            )

            # Check if confirmation was successful
            if result.get("status") == "confirmed" or result.get("confirmed", False):
                # Map updated debt if provided
                debt = None
                if result.get("debt"):
                    debt = PharmacyDebt.from_dict(result["debt"])

                return ConfirmDebtResponse(
                    success=True,
                    confirmed=True,
                    debt=debt,
                )

            # Handle failed confirmation
            error_message = result.get("error", result.get("message", "Confirmation failed"))
            return ConfirmDebtResponse(
                success=False,
                confirmed=False,
                error=error_message,
            )

        except Exception as e:
            return ConfirmDebtResponse(
                success=False,
                confirmed=False,
                error=str(e),
            )
