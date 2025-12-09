"""
Invoice Generation Node

Pharmacy domain node for generating invoices from confirmed debt.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.application.use_cases.generate_invoice import (
    GenerateInvoiceRequest,
    GenerateInvoiceUseCase,
)

if TYPE_CHECKING:
    from app.clients.pharmacy_erp_client import PharmacyERPClient

logger = logging.getLogger(__name__)


class InvoiceGenerationNode(BaseAgent):
    """Pharmacy node specialized in invoice generation."""

    def __init__(
        self,
        erp_client: PharmacyERPClient | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize invoice generation node.

        Args:
            erp_client: Pharmacy ERP client instance
            config: Node configuration
        """
        super().__init__("invoice_generation_node", config or {})
        self._erp_client = erp_client
        self._use_case: GenerateInvoiceUseCase | None = None

    def _get_use_case(self) -> GenerateInvoiceUseCase:
        """Get or create the use case with lazy initialization."""
        if self._use_case is None:
            if self._erp_client is None:
                from app.clients.pharmacy_erp_client import PharmacyERPClient

                self._erp_client = PharmacyERPClient()
            self._use_case = GenerateInvoiceUseCase(self._erp_client)
        return self._use_case

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process invoice generation.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            debt_id = state_dict.get("debt_id")
            customer_id = state_dict.get("customer_id") or state_dict.get("user_id")
            debt_status = state_dict.get("debt_status")

            if not debt_id:
                return self._handle_no_debt_id()

            if not customer_id:
                return self._handle_no_customer()

            # Check if debt is confirmed
            if debt_status != "confirmed":
                return self._handle_not_confirmed()

            # Execute use case (ensures _erp_client is initialized)
            use_case = self._get_use_case()

            # Need to use context manager for httpx client
            # _get_use_case() guarantees _erp_client is not None
            erp_client = self._erp_client
            if erp_client is None:
                return self._handle_error("ERP client not configured", state_dict)

            async with erp_client:
                request = GenerateInvoiceRequest(
                    debt_id=debt_id,
                    customer_id=customer_id,
                )
                response = await use_case.execute(request)

            if not response.success or not response.invoice_number:
                return self._handle_generation_failed(
                    response.error or "Invoice generation failed",
                    state_dict,
                )

            # Invoice generated successfully
            response_text = self._format_invoice_response(
                response.invoice_number,
                response.pdf_url,
                state_dict.get("total_debt", 0),
            )

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "invoice_number": response.invoice_number,
                "pdf_url": response.pdf_url,
                "debt_status": "invoiced",
                "workflow_step": "invoiced",
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in invoice generation node: {e!s}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    def _format_invoice_response(
        self,
        invoice_number: str,
        pdf_url: str | None,
        total: float,
    ) -> str:
        """Format invoice response message."""
        base_message = (
            f"Tu factura ha sido generada exitosamente.\n\n"
            f"**Numero de Factura:** {invoice_number}\n"
            f"**Total:** ${total:,.2f}"
        )

        if pdf_url:
            base_message += f"\n\n**Descargar PDF:** {pdf_url}"

        base_message += "\n\nGracias por tu preferencia!"

        return base_message

    def _handle_no_debt_id(self) -> dict[str, Any]:
        """Handle missing debt ID."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No hay una deuda seleccionada para facturar. "
                        "Por favor primero consulta y confirma tu deuda."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
        }

    def _handle_no_customer(self) -> dict[str, Any]:
        """Handle missing customer ID."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No pude identificar tu cuenta. "
                        "Por favor contacta a soporte."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
        }

    def _handle_not_confirmed(self) -> dict[str, Any]:
        """Handle debt not confirmed."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "La deuda debe estar confirmada antes de generar la factura. "
                        "Por favor confirma tu deuda primero respondiendo *SI*."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": False,
        }

    def _handle_generation_failed(
        self,
        error: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle invoice generation failure."""
        logger.warning(f"Invoice generation failed: {error}")
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No se pudo generar la factura. "
                        "Por favor intenta de nuevo o contacta a soporte."
                    ),
                }
            ],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }

    def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Invoice generation node error: {error}")
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, tuve un problema generando la factura. "
                        "Por favor intenta de nuevo."
                    ),
                }
            ],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }
