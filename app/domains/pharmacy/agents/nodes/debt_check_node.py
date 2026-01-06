"""
Debt Check Node

Pharmacy domain node for checking customer debt via Plex ERP.
Uses PromptManager for externalized response templates.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.domain.entities.pharmacy_debt import DebtItem, PharmacyDebt
from app.domains.pharmacy.domain.value_objects.debt_status import DebtStatus
from app.integrations.llm import ModelComplexity, VllmLLM, get_llm_for_task
from app.prompts.manager import PromptManager

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)

# Maximum number of items to display in debt response
MAX_ITEMS_DISPLAY = 10

# LLM configuration for debt response generation
DEBT_LLM_TEMPERATURE = 0.5
DEBT_LLM_MAX_TOKENS = 500


class DebtCheckNode(BaseAgent):
    """
    Pharmacy node specialized in debt checking (Consulta Deuda).

    Uses PlexClient to query customer balance via the Plex ERP API.
    Requires that the customer has already been identified (plex_customer_id in state).
    Uses PromptManager for externalized response templates.
    """

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        config: dict[str, Any] | None = None,
        prompt_manager: PromptManager | None = None,
    ):
        """
        Initialize debt check node.

        Args:
            plex_client: PlexClient instance for API calls
            config: Node configuration
            prompt_manager: PromptManager instance for response templates
        """
        super().__init__("debt_check_node", config or {})
        self._plex_client = plex_client
        self._prompt_manager = prompt_manager

    @property
    def prompt_manager(self) -> PromptManager:
        """Get or create PromptManager instance."""
        if self._prompt_manager is None:
            self._prompt_manager = PromptManager()
        return self._prompt_manager

    def _get_plex_client(self) -> PlexClient:
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient
            self._plex_client = PlexClient()
        return self._plex_client

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process debt check queries.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            # Get Plex customer ID from state
            plex_customer_id = state_dict.get("plex_customer_id")

            if not plex_customer_id:
                logger.warning("No plex_customer_id in state for debt check")
                return await self._handle_no_customer()

            # Get customer name for personalized response
            customer_name = (
                state_dict.get("customer_name")
                or state_dict.get("plex_customer", {}).get("nombre", "Cliente")
            )

            logger.info(f"Checking debt for Plex customer: {plex_customer_id}")

            plex_client = self._get_plex_client()

            async with plex_client:
                balance_data = await plex_client.get_customer_balance(
                    customer_id=plex_customer_id,
                    detailed=True,
                )

            if not balance_data:
                return await self._handle_no_debt(customer_name)

            # Check if there's actual debt
            total_debt = balance_data.get("saldo", 0)
            if total_debt <= 0:
                return await self._handle_no_debt(customer_name)

            # Transform Plex response to domain entity
            debt = self._map_plex_balance_to_debt(
                balance_data,
                plex_customer_id,
                customer_name,
            )

            # Check if this was auto-triggered from "quiero pagar" intent
            auto_proceed_to_invoice = state_dict.get("auto_proceed_to_invoice", False)
            extracted_entities = state_dict.get("extracted_entities", {})
            payment_amount = extracted_entities.get("amount")

            # Format response based on context
            if auto_proceed_to_invoice:
                response_text = await self._format_payment_ready_response(
                    debt, payment_amount
                )
            else:
                response_text = await self._format_debt_response(debt)

            result = {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "debt_id": str(balance_data.get("id", plex_customer_id)),
                "debt_data": debt.to_dict(),
                "debt_status": debt.status.value,
                "total_debt": float(debt.total_debt),
                "has_debt": True,
                "workflow_step": "debt_checked",
                "awaiting_confirmation": True,  # Wait for user to confirm
                "is_complete": False,
            }

            # If auto-proceeding to invoice, set payment amount from intent
            if auto_proceed_to_invoice and payment_amount:
                result["payment_amount"] = min(payment_amount, float(debt.total_debt))
                result["is_partial_payment"] = payment_amount < float(debt.total_debt)

            return result

        except Exception as e:
            logger.error(f"Error in debt check node: {e!s}", exc_info=True)
            return await self._handle_error(str(e), state_dict)

    def _map_plex_balance_to_debt(
        self,
        balance_data: dict[str, Any],
        customer_id: int,
        customer_name: str,
    ) -> PharmacyDebt:
        """
        Map Plex balance response to PharmacyDebt entity.

        Args:
            balance_data: Raw response from Plex /saldo_cliente
            customer_id: Plex customer ID
            customer_name: Customer display name

        Returns:
            PharmacyDebt domain entity
        """
        # Extract items from Plex response
        items: list[DebtItem] = []
        detalle = balance_data.get("detalle", [])

        for item_data in detalle:
            items.append(
                DebtItem(
                    description=item_data.get("descripcion", "Item"),
                    amount=Decimal(str(item_data.get("importe", 0))),
                    quantity=item_data.get("cantidad", 1),
                    unit_price=(
                        Decimal(str(item_data["precio_unitario"]))
                        if item_data.get("precio_unitario")
                        else None
                    ),
                    product_code=item_data.get("codigo"),
                    invoice_number=item_data.get("comprobante"),
                    invoice_date=item_data.get("fecha"),
                )
            )

        # Sort items by amount descending to ensure highest values are first
        items.sort(key=lambda x: x.amount, reverse=True)

        # Build debt entity
        return PharmacyDebt.from_dict({
            "id": str(balance_data.get("id", customer_id)),
            "customer_id": str(customer_id),
            "customer_name": customer_name,
            "total_debt": balance_data.get("saldo", 0),
            "status": DebtStatus.PENDING.value,
            "due_date": balance_data.get("fecha_vencimiento"),
            "items": [item.to_dict() for item in items],
            "created_at": balance_data.get("fecha"),
            "notes": balance_data.get("observaciones"),
        })

    async def _format_debt_response(self, debt: PharmacyDebt) -> str:
        """Format debt information as user-friendly response using LLM."""
        items_text = self._format_items(debt.items)

        try:
            # Try LLM-powered response first
            response = await self._generate_debt_response_with_llm(debt, items_text)
            if response:
                return response
        except Exception as e:
            logger.warning(f"LLM debt response failed, using fallback: {e}")

        # Fallback to static template
        return self._get_fallback_debt_response(debt, items_text)

    async def _generate_debt_response_with_llm(
        self,
        debt: PharmacyDebt,
        items_text: str,
    ) -> str | None:
        """
        Generate natural debt response using LLM.

        Args:
            debt: PharmacyDebt entity with debt information
            items_text: Formatted items text

        Returns:
            Generated response text or None if failed
        """
        try:
            # Build prompt from template
            prompt = await self.prompt_manager.get_prompt(
                "pharmacy.response.debt_query_llm",
                variables={
                    "customer_name": debt.customer_name,
                    "total_debt": f"${float(debt.total_debt):,.2f}",
                    "item_count": len(debt.items),
                    "items_summary": items_text,
                },
            )

            # Get LLM instance
            llm = get_llm_for_task(
                complexity=ModelComplexity.SIMPLE,
                temperature=DEBT_LLM_TEMPERATURE,
            )

            # Generate response
            response = await llm.ainvoke(prompt)

            # Extract content
            if hasattr(response, "content"):
                content = response.content
                if isinstance(content, str):
                    # Clean deepseek thinking tags if present
                    cleaned = VllmLLM.clean_reasoning_response(content)
                    return cleaned.strip()
                elif isinstance(content, list):
                    return " ".join(str(item) for item in content).strip()

            return None

        except ValueError as e:
            logger.warning(f"Debt LLM template not found: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating debt response with LLM: {e}")
            return None

    def _get_fallback_debt_response(self, debt: PharmacyDebt, items_text: str) -> str:
        """Get static fallback debt response."""
        due_date_text = (
            debt.due_date.strftime("%d/%m/%Y") if debt.due_date else "No especificada"
        )

        return f"""**Consulta de Deuda**

Hola {debt.customer_name},

Tu deuda pendiente es de **${debt.total_debt:,.2f}**

**Detalle:**
{items_text}

Fecha de vencimiento: {due_date_text}

Para confirmar esta deuda y proceder con el pago, responde *SI*.
Para cancelar, responde *NO*."""

    async def _format_payment_ready_response(
        self,
        debt: PharmacyDebt,
        payment_amount: float | None = None,
    ) -> str:
        """
        Format response when user wants to pay directly.

        This is called when the user said "quiero pagar" and we auto-fetched debt.

        Args:
            debt: PharmacyDebt entity
            payment_amount: Optional payment amount if user specified one

        Returns:
            Formatted response asking for payment confirmation
        """
        items_text = self._format_items(debt.items[:5])  # Show fewer items for payment flow
        total_debt = float(debt.total_debt)

        if payment_amount and payment_amount < total_debt:
            # Partial payment
            remaining = total_debt - payment_amount
            return f"""💰 **Pago Parcial**

Hola {debt.customer_name}, tu deuda total es **${total_debt:,.2f}**.

Quieres pagar: **${payment_amount:,.2f}**
Saldo restante: **${remaining:,.2f}**

**Algunos productos en tu cuenta:**
{items_text}

Para confirmar este pago parcial, responde *SI*.
Para cancelar, responde *NO*."""
        else:
            # Full payment
            return f"""💰 **Confirmar Pago**

Hola {debt.customer_name}, tu deuda pendiente es **${total_debt:,.2f}**.

**Algunos productos en tu cuenta:**
{items_text}

Para confirmar y generar el recibo de pago, responde *SI*.
Para cancelar, responde *NO*.

💡 *Tip: También puedes pagar un monto parcial escribiendo "pagar X" (ej: "pagar 5000").*"""

    def _format_items(self, items: list[DebtItem]) -> str:
        """Format debt items with display limit."""
        if not items:
            return "- Sin detalle disponible"

        # Limit items shown to avoid huge messages
        display_items = items[:MAX_ITEMS_DISPLAY]
        formatted = "\n".join(
            [f"- {item.description}: ${float(item.amount):,.2f}" for item in display_items]
        )

        # Add summary if there are more items
        if len(items) > MAX_ITEMS_DISPLAY:
            remaining = len(items) - MAX_ITEMS_DISPLAY
            formatted += f"\n\n... y {remaining} productos más en tu cuenta."

        return formatted

    async def _handle_no_customer(self) -> dict[str, Any]:
        """Handle missing customer identification."""
        try:
            content = await self.prompt_manager.get_prompt("pharmacy.response.no_customer")
        except ValueError:
            content = (
                "No pude identificar tu cuenta. "
                "Por favor escribe tu número de DNI para buscarte."
            )

        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_agent": self.name,
            "awaiting_document_input": True,
            "has_debt": False,
        }

    async def _handle_no_debt(self, customer_name: str) -> dict[str, Any]:
        """Handle no debt found."""
        try:
            content = await self.prompt_manager.get_prompt(
                "pharmacy.response.no_debt",
                variables={"customer_name": customer_name},
            )
        except ValueError:
            content = (
                f"Hola {customer_name}, no tienes deudas pendientes. "
                "¿Hay algo más en que pueda ayudarte?"
            )

        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_agent": self.name,
            "has_debt": False,
            "is_complete": True,
        }

    async def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Debt check error: {error}")

        try:
            content = await self.prompt_manager.get_prompt("pharmacy.response.error")
        except ValueError:
            content = (
                "Disculpa, tuve un problema consultando tu deuda. "
                "Por favor intenta de nuevo en unos momentos."
            )

        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }
