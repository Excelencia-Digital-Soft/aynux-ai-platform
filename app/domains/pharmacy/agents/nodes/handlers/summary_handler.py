"""
Pharmacy Summary Handler

Handles summary requests for debt items analysis using LLM.
Uses LLM-driven ResponseGenerator for natural language responses.
"""

from __future__ import annotations

from typing import Any

from .base_handler import BasePharmacyHandler


class SummaryHandler(BasePharmacyHandler):
    """
    Handle summary/analysis requests for pharmacy domain.

    Generates intelligent summaries of customer debt items
    with categorization and insights.
    """

    async def handle(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle summary request.

        Args:
            message: User summary request
            state: Current state with debt_data

        Returns:
            State updates with summary response
        """
        state = state or {}
        customer_name = state.get("customer_name", "Cliente")
        debt_data = state.get("debt_data", {})

        if not debt_data or not debt_data.get("items"):
            result_content = await self._generate_response(
                intent="summary_no_data",
                state=state,
                user_message=message,
                current_task="Informa que no hay datos de productos para resumir.",
            )
            return self._format_state_update(
                message=result_content,
                intent_type="summary",
                workflow_step="summary_no_data",
                state=state,
            )

        try:
            summary = await self._generate_summary_with_llm(
                user_message=message,
                customer_name=customer_name,
                debt_data=debt_data,
            )
        except Exception as e:
            self.logger.warning(f"LLM summary failed, using fallback: {e}")
            summary = self._get_inline_summary(customer_name, debt_data)

        return self._format_state_update(
            message=summary,
            intent_type="summary",
            workflow_step="summary_provided",
            state=state,
        )

    async def _generate_summary_with_llm(
        self,
        user_message: str,
        customer_name: str,
        debt_data: dict[str, Any],
    ) -> str:
        """
        Generate summary of medications/products using LLM.

        Args:
            user_message: Original user request
            customer_name: Customer name
            debt_data: Debt data with items

        Returns:
            Generated summary text
        """
        items = debt_data.get("items", [])
        total_debt = debt_data.get("total_debt", 0)

        items_text = "\n".join(
            [f"- {item.get('description', 'Item')}: ${float(item.get('amount', 0)):,.2f}" for item in items]
        )

        response_state = {
            "user_message": user_message,
            "customer_name": customer_name,
            "total_debt": f"${float(total_debt):,.2f}",
            "item_count": str(len(items)),
            "items_list": items_text,
        }

        result_content = await self._generate_response(
            intent="summary_generate",
            state=response_state,
            user_message=user_message,
            current_task="Genera un resumen de los productos y deuda del cliente.",
        )

        if result_content:
            return result_content

        return self._get_inline_summary(customer_name, debt_data)

    def _get_inline_summary(
        self,
        customer_name: str,
        debt_data: dict[str, Any],
    ) -> str:
        """Get inline summary when LLM is unavailable."""
        items = debt_data.get("items", [])
        total_debt = debt_data.get("total_debt", 0)

        if not items:
            return f"Hola {customer_name}, no hay productos para resumir."

        medicamentos: list[tuple[str, float]] = []
        otros: list[tuple[str, float]] = []
        med_keywords = ["mg", "ml", "comp", "caps", "gts", "jbe", "sol", "cr.", "gel"]

        for item in items:
            desc = item.get("description", "").lower()
            amount = float(item.get("amount", 0))
            if any(med in desc for med in med_keywords):
                medicamentos.append((item.get("description", "Item"), amount))
            else:
                otros.append((item.get("description", "Item"), amount))

        summary_parts = [f"**Resumen de tu cuenta, {customer_name}**\n"]

        if medicamentos:
            total_med = sum(a for _, a in medicamentos)
            summary_parts.append(f"**Medicamentos** ({len(medicamentos)} items): ${total_med:,.2f}")

        if otros:
            total_otros = sum(a for _, a in otros)
            summary_parts.append(f"**Otros productos** ({len(otros)} items): ${total_otros:,.2f}")

        summary_parts.append(f"\n**Total pendiente:** ${float(total_debt):,.2f}")
        summary_parts.append("\nPara ver el detalle completo, escribe *deuda*.")

        return "\n".join(summary_parts)
