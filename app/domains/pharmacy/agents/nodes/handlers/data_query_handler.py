"""
Pharmacy Data Query Handler

Handles data analysis queries using LLM to answer customer questions
about their debt items. Auto-fetches debt data from Plex if needed.
Uses LLM-driven ResponseGenerator for natural language responses.
"""

from __future__ import annotations

import re
from typing import Any

from app.domains.pharmacy.agents.utils.db_helpers import get_current_task
from app.tasks import TaskRegistry

from .base_handler import BasePharmacyHandler


class DataQueryHandler(BasePharmacyHandler):
    """
    Handle data analysis queries for pharmacy domain.

    Answers questions like:
    - "¿Cuál es el medicamento que más debo?"
    - "¿Cuántos productos tengo pendientes?"
    - "¿Cuál es el producto más caro?"

    Auto-fetches debt data from Plex if not available in state.
    """

    async def handle(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle data analysis query.

        Args:
            message: User question about their data
            state: Current state (may or may not have debt_data)

        Returns:
            State updates with analysis response
        """
        state = state or {}
        customer_name = state.get("customer_name", "Cliente")
        plex_customer_id = state.get("plex_customer_id")
        debt_data = state.get("debt_data", {})

        state_updates: dict[str, Any] = {}

        if (not debt_data or not debt_data.get("items")) and plex_customer_id:
            self.logger.info(f"Auto-fetching debt for data_query, customer_id={plex_customer_id}")
            fetched_data = await self._fetch_debt_for_query(plex_customer_id)
            if fetched_data:
                debt_data = fetched_data
                state_updates["debt_data"] = debt_data
                state_updates["total_debt"] = debt_data.get("total_debt", 0)
                state_updates["has_debt"] = True

        if not debt_data or not debt_data.get("items"):
            response_content = await self._generate_response(
                intent="data_query_no_data",
                state=state,
                user_message=message,
                current_task=await get_current_task(TaskRegistry.PHARMACY_DATA_QUERY_NO_DATA),
            )
            return self._format_state_update(
                message=response_content,
                intent_type="data_query",
                workflow_step="data_query_no_data",
                state=state,
            )

        try:
            analysis = await self._analyze_data_with_llm(
                user_question=message,
                customer_name=customer_name,
                debt_data=debt_data,
            )
        except Exception as e:
            self.logger.warning(f"LLM data analysis failed, using fallback: {e}")
            analysis = await self._get_inline_data_analysis(message, customer_name, debt_data)

        return {
            **state_updates,
            **self._format_state_update(
                message=analysis,
                intent_type="data_query",
                workflow_step="data_query_answered",
                state=state,
            ),
        }

    async def _fetch_debt_for_query(
        self,
        plex_customer_id: int,
    ) -> dict[str, Any] | None:
        """
        Fetch debt data from Plex for data analysis queries.

        Args:
            plex_customer_id: The Plex customer ID

        Returns:
            Debt data dict with items, or None if fetch failed
        """
        try:
            from app.clients.plex_client import PlexClient

            plex_client = PlexClient()
            async with plex_client:
                balance_data = await plex_client.get_customer_balance(
                    customer_id=plex_customer_id,
                    detailed=True,
                )

            if not balance_data or balance_data.get("saldo", 0) <= 0:
                return None

            items = [
                {
                    "description": item_data.get("descripcion", "Item"),
                    "amount": float(item_data.get("importe", 0)),
                    "quantity": item_data.get("cantidad", 1),
                    "invoice_number": item_data.get("comprobante", ""),
                    "invoice_date": item_data.get("fecha", ""),
                }
                for item_data in balance_data.get("detalle", [])
            ]

            # Sort items by amount descending
            items.sort(key=lambda x: x["amount"], reverse=True)

            return {
                "items": items,
                "total_debt": float(balance_data.get("saldo", 0)),
            }

        except Exception as e:
            self.logger.error(f"Error fetching debt for data_query: {e}")
            return None

    async def _analyze_data_with_llm(
        self,
        user_question: str,
        customer_name: str,
        debt_data: dict[str, Any],
    ) -> str:
        """
        Analyze debt data using LLM to answer user questions.

        Args:
            user_question: User's question about their data
            customer_name: Customer name
            debt_data: Debt data with items

        Returns:
            Generated analysis response
        """
        from app.domains.pharmacy.domain.services.debt_grouping_service import (
            DebtGroupingService,
        )

        items = debt_data.get("items", [])
        total_debt = debt_data.get("total_debt", 0)

        # Group items by invoice for accurate analysis
        invoice_groups = DebtGroupingService.group_by_invoice(items)
        invoice_count = len(invoice_groups)

        # Build grouped items text
        grouped_lines = []
        for group in invoice_groups[:10]:  # Limit to top 10 invoices
            grouped_lines.append(
                f"\n**Factura {group.invoice_number}** "
                f"(Total: ${float(group.total_amount):,.2f}, Fecha: {group.invoice_date or 'N/A'})"
            )
            for item in group.items[:5]:  # Limit to 5 items per invoice
                if isinstance(item, dict):
                    desc = item.get("description", "Item")
                    amount = float(item.get("amount", 0))
                else:
                    desc = item.description
                    amount = float(item.amount)
                grouped_lines.append(f"  - {desc}: ${amount:,.2f}")
            if group.item_count > 5:
                grouped_lines.append(f"  ... y {group.item_count - 5} productos más")
        grouped_items_text = "\n".join(grouped_lines)

        # Use ResponseGenerator for LLM analysis
        response_state = {
            "customer_name": customer_name,
            "total_debt": f"${float(total_debt):,.2f}",
            "invoice_count": str(invoice_count),
            "user_message": user_question,
            "debt_details": grouped_items_text,
        }

        response_content = await self._generate_response(
            intent="data_query_analyze",
            state=response_state,
            user_message=user_question,
            current_task=await get_current_task(TaskRegistry.PHARMACY_DATA_QUERY_ANALYZE),
        )

        if response_content:
            return response_content

        return await self._get_inline_data_analysis(user_question, customer_name, debt_data)

    async def _get_inline_data_analysis(
        self,
        question: str,
        customer_name: str,
        debt_data: dict[str, Any],
    ) -> str:
        """
        Fallback data analysis when LLM is unavailable.

        Uses contextual logic:
        - "medicamento/producto/remedio" → individual item with highest value
        - "factura/comprobante/deuda" → invoice with highest total
        - Just "debo" without context → invoice with highest total (default)
        """
        from app.domains.pharmacy.domain.services.debt_grouping_service import (
            DebtGroupingService,
        )

        items = debt_data.get("items", [])
        total_debt = debt_data.get("total_debt", 0)
        question_lower = question.lower()

        # Priority: Detect price/cost queries for specific products
        asks_for_price = any(
            word in question_lower for word in ["precio", "costo", "cuanto cuesta", "cuánto cuesta", "vale", "valor de"]
        )

        if asks_for_price:
            # Extract product name from question
            product_name = self._extract_product_name(question_lower)

            if product_name:
                # Search for product in debt items
                matching_item = self._find_product_in_debt(product_name, items)

                if matching_item:
                    # Found in debt - show price from their account
                    desc = matching_item.get("description", "Producto")
                    amount = float(matching_item.get("amount", 0))
                    invoice_num = matching_item.get("invoice_number", "")
                    invoice_date = matching_item.get("invoice_date", "")

                    invoice_info = ""
                    if invoice_num:
                        invoice_info = f"\n📄 Factura: {invoice_num}"
                        if invoice_date:
                            invoice_info += f" | Fecha: {invoice_date}"

                    return await self._render_fallback_template(
                        template_key="product_found",
                        variables={
                            "customer_name": customer_name,
                            "product_desc": desc,
                            "amount": f"{amount:,.2f}",
                            "invoice_info": invoice_info,
                        },
                    )
                else:
                    # Not found - explain limitations clearly
                    return await self._render_fallback_template(
                        template_key="product_not_found",
                        variables={
                            "customer_name": customer_name,
                        },
                    )

        # Get grouped data
        invoice_groups = DebtGroupingService.group_by_invoice(items)
        highest_invoice = DebtGroupingService.get_highest_debt_invoice(items)
        highest_item = DebtGroupingService.get_highest_individual_item(items)

        # Detect context from question
        asks_for_item = any(word in question_lower for word in ["medicamento", "producto", "remedio", "más caro"])
        asks_for_invoice = any(word in question_lower for word in ["factura", "comprobante", "deuda total"])

        # Handle "mayor deuda" type questions with intelligent context
        if any(word in question_lower for word in ["más debo", "mayor", "mayor valor", "debo", "caro"]):
            # Context: Asking for individual product
            if asks_for_item and not asks_for_invoice and highest_item:
                if isinstance(highest_item, dict):
                    max_desc = highest_item.get("description", "Item")
                    max_amount = float(highest_item.get("amount", 0))
                    invoice_num = highest_item.get("invoice_number", "")
                    invoice_date = highest_item.get("invoice_date", "")
                else:
                    max_desc = highest_item.description
                    max_amount = float(highest_item.amount)
                    invoice_num = highest_item.invoice_number or ""
                    invoice_date = highest_item.invoice_date or ""

                invoice_info = ""
                if invoice_num or invoice_date:
                    invoice_info = f"\n📄 Factura: {invoice_num or 'N/A'} | Fecha: {invoice_date or 'N/A'}"

                return await self._render_fallback_template(
                    template_key="highest_item",
                    variables={
                        "customer_name": customer_name,
                        "item_desc": max_desc,
                        "amount": f"{max_amount:,.2f}",
                        "total_debt": f"{float(total_debt):,.2f}",
                        "invoice_info": invoice_info,
                    },
                )

            # Context: Asking for invoice/grouped debt (default for ambiguous queries)
            if highest_invoice:
                products_lines = []
                for item in highest_invoice.items[:5]:
                    if isinstance(item, dict):
                        desc = item.get("description", "Item")
                        amount = float(item.get("amount", 0))
                    else:
                        desc = item.description
                        amount = float(item.amount)
                    products_lines.append(f"  - {desc}: ${amount:,.2f}")

                if highest_invoice.item_count > 5:
                    products_lines.append(f"  ... y {highest_invoice.item_count - 5} productos más")

                products_text = "\n".join(products_lines)

                date_info = ""
                if highest_invoice.invoice_date:
                    date_info = f"\n📅 Fecha: {highest_invoice.invoice_date}"

                return await self._render_fallback_template(
                    template_key="highest_invoice",
                    variables={
                        "customer_name": customer_name,
                        "invoice_number": highest_invoice.invoice_number,
                        "invoice_total": f"{float(highest_invoice.total_amount):,.2f}",
                        "date_info": date_info,
                        "products_text": products_text,
                        "total_debt": f"{float(total_debt):,.2f}",
                        "invoice_count": str(len(invoice_groups)),
                    },
                )

        # Question about quantity
        if any(word in question_lower for word in ["cuántos", "cuantos", "cantidad"]):
            invoice_summary = ""
            if invoice_groups:
                invoice_summary = f"\n📄 Distribuidos en **{len(invoice_groups)} facturas**"

            return (
                f"**{customer_name}**, tienes **{len(items)} productos** "
                f"pendientes de pago.{invoice_summary}\n\n"
                f"📊 Total: ${float(total_debt):,.2f}"
            )

        # Default summary with both individual and grouped info
        highest_item_text = "N/A"
        if highest_item:
            if isinstance(highest_item, dict):
                highest_item_text = (
                    f"{highest_item.get('description', 'Item')} (${float(highest_item.get('amount', 0)):,.2f})"
                )
            else:
                highest_item_text = f"{highest_item.description} (${float(highest_item.amount):,.2f})"

        highest_invoice_text = ""
        if highest_invoice:
            highest_invoice_text = (
                f"\n📄 **Mayor factura:** {highest_invoice.invoice_number} "
                f"(${float(highest_invoice.total_amount):,.2f})"
            )

        return await self._render_fallback_template(
            template_key="summary",
            variables={
                "customer_name": customer_name,
                "item_count": str(len(items)),
                "total_debt": f"{float(total_debt):,.2f}",
                "highest_item_text": highest_item_text,
                "highest_invoice_text": highest_invoice_text,
            },
        )

    def _extract_product_name(self, question: str) -> str | None:
        """
        Extract product name from price query.

        Patterns:
        - "precio del paracetamol" → "paracetamol"
        - "cuánto cuesta el ibuprofeno" → "ibuprofeno"
        - "valor de la aspirina" → "aspirina"

        Args:
            question: User question (lowercase)

        Returns:
            Extracted product name or None
        """
        patterns = [
            r"precio\s+(?:del?|de\s+la?)\s+(.+?)(?:\?|$)",
            r"cuanto\s+cuesta\s+(?:el|la|un|una)?\s*(.+?)(?:\?|$)",
            r"cuánto\s+cuesta\s+(?:el|la|un|una)?\s*(.+?)(?:\?|$)",
            r"valor\s+(?:del?|de\s+la?)\s+(.+?)(?:\?|$)",
            r"costo\s+(?:del?|de\s+la?)\s+(.+?)(?:\?|$)",
            r"que\s+(?:precio|costo)\s+tiene\s+(?:el|la)?\s*(.+?)(?:\?|$)",
            r"qué\s+(?:precio|costo)\s+tiene\s+(?:el|la)?\s*(.+?)(?:\?|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _find_product_in_debt(
        self,
        product_name: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """
        Find a product in debt items by name similarity.

        Uses simple substring matching to find products.

        Args:
            product_name: Product name to search for
            items: List of debt items

        Returns:
            Matching item dict or None
        """
        if not product_name:
            return None

        product_lower = product_name.lower().strip()

        for item in items:
            desc = item.get("description", "").lower()
            # Substring matching in both directions
            if product_lower in desc or desc in product_lower:
                return item

        return None
