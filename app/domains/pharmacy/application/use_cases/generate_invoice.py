"""
Generate Invoice Use Case

Application use case for generating invoice from confirmed debt.
"""

from dataclasses import dataclass
from typing import Any

from app.domains.pharmacy.application.ports import IPharmacyERPPort
from app.domains.pharmacy.domain.entities.pharmacy_invoice import PharmacyInvoice


@dataclass
class GenerateInvoiceRequest:
    """Request to generate invoice."""

    debt_id: str
    customer_id: str


@dataclass
class GenerateInvoiceResponse:
    """Response from invoice generation operation."""

    success: bool
    invoice: PharmacyInvoice | None = None
    invoice_number: str | None = None
    pdf_url: str | None = None
    error: str | None = None


class GenerateInvoiceUseCase:
    """
    Use case for generating invoice from confirmed debt.

    Single Responsibility: Handle invoice generation workflow
    Dependency Inversion: Depends on IPharmacyERPPort abstraction
    """

    def __init__(self, erp_client: IPharmacyERPPort):
        """
        Initialize use case with ERP client.

        Args:
            erp_client: Implementation of IPharmacyERPPort
        """
        self._erp = erp_client

    async def execute(self, request: GenerateInvoiceRequest) -> GenerateInvoiceResponse:
        """
        Execute invoice generation use case.

        Args:
            request: GenerateInvoiceRequest with debt_id and customer_id

        Returns:
            GenerateInvoiceResponse with invoice details or error
        """
        try:
            if not request.debt_id:
                return GenerateInvoiceResponse(
                    success=False,
                    error="Debt ID is required",
                )

            if not request.customer_id:
                return GenerateInvoiceResponse(
                    success=False,
                    error="Customer ID is required",
                )

            result = await self._erp.generate_invoice(
                request.debt_id,
                request.customer_id,
            )

            # Check if invoice was generated successfully
            invoice_number = result.get("invoice_number")
            if invoice_number:
                # Map invoice from response
                invoice = self._map_to_entity(result)

                return GenerateInvoiceResponse(
                    success=True,
                    invoice=invoice,
                    invoice_number=invoice.invoice_number,
                    pdf_url=invoice.pdf_url,
                )

            # Handle failed generation
            error_message = result.get("error", result.get("message", "Invoice generation failed"))
            return GenerateInvoiceResponse(
                success=False,
                error=error_message,
            )

        except Exception as e:
            return GenerateInvoiceResponse(
                success=False,
                error=str(e),
            )

    def _map_to_entity(self, data: dict[str, Any]) -> PharmacyInvoice:
        """
        Map ERP response to domain entity.

        Args:
            data: Raw ERP response data

        Returns:
            PharmacyInvoice entity
        """
        return PharmacyInvoice.from_dict(
            {
                "id": data.get("id", data.get("invoice_id", "")),
                "invoice_number": data.get("invoice_number", ""),
                "debt_id": data.get("debt_id", ""),
                "customer_id": data.get("customer_id", ""),
                "customer_name": data.get("customer_name", "Cliente"),
                "subtotal": data.get("subtotal", data.get("total_amount", 0)),
                "tax_amount": data.get("tax_amount", data.get("tax", 0)),
                "total_amount": data.get("total_amount", data.get("total", 0)),
                "items": data.get("items", []),
                "generated_at": data.get("generated_at", data.get("created_at")),
                "pdf_url": data.get("pdf_url"),
                "notes": data.get("notes"),
            }
        )
