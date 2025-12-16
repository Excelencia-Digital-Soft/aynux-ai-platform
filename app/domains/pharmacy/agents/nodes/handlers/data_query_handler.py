"""
Pharmacy Data Query Handler

Handles data analysis queries using LLM to answer customer questions
about their debt items. Auto-fetches debt data from Plex if needed.
"""

from __future__ import annotations

from typing import Any

from app.integrations.llm import ModelComplexity, get_llm_for_task

from .base_handler import BasePharmacyHandler

# LLM configuration
DATA_QUERY_LLM_TEMPERATURE = 0.3


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
            return self._format_state_update(
                message=(
                    f"Hola {customer_name}, no tengo información de tu cuenta "
                    "para responder esa pregunta.\n\n"
                    "Por favor escribe *deuda* para consultar tu saldo pendiente."
                ),
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
            analysis = self._get_inline_data_analysis(message, customer_name, debt_data)

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
                    "comprobante": item_data.get("comprobante", ""),
                    "fecha": item_data.get("fecha", ""),
                }
                for item_data in balance_data.get("detalle", [])
            ]

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
        items = debt_data.get("items", [])
        total_debt = debt_data.get("total_debt", 0)

        # Build items text with invoice details if available
        items_lines = []
        for item in items:
            desc = item.get("description", "Item")
            amount = float(item.get("amount", 0))
            comprobante = item.get("comprobante", "")
            fecha = item.get("fecha", "")
            line = f"- {desc}: ${amount:,.2f}"
            if comprobante or fecha:
                line += f" (Fact: {comprobante or 'N/A'}, Fecha: {fecha or 'N/A'})"
            items_lines.append(line)
        items_text = "\n".join(items_lines)

        prompt = f"""Eres un asistente de farmacia analizando los datos de deuda de un cliente.

**Datos de deuda del cliente {customer_name}:**
Total pendiente: ${float(total_debt):,.2f}
Cantidad de productos: {len(items)}

**Detalle de productos pendientes:**
{items_text}

**Pregunta del cliente:** {user_question}

**Instrucciones:**
1. Analiza los datos disponibles y responde la pregunta del cliente
2. Si la pregunta es sobre "qué medicamento debo más", busca el item con mayor importe
3. Si la pregunta es sobre "cuántos productos", cuenta los items
4. Si la pregunta requiere información histórica que NO tenemos (ej: compras pasadas),
   explica amablemente que solo tienes información de la deuda actual
5. Sé conciso y directo en tu respuesta
6. Usa formato amigable con emojis si es apropiado

Responde SOLO basándote en los datos proporcionados:"""

        llm = get_llm_for_task(
            complexity=ModelComplexity.COMPLEX,
            temperature=DATA_QUERY_LLM_TEMPERATURE,
        )
        response = await llm.ainvoke(prompt)

        content = self._extract_response_content(response)
        if content:
            return content

        return self._get_inline_data_analysis(user_question, customer_name, debt_data)

    def _get_inline_data_analysis(
        self,
        question: str,
        customer_name: str,
        debt_data: dict[str, Any],
    ) -> str:
        """Fallback data analysis when LLM is unavailable."""
        items = debt_data.get("items", [])
        total_debt = debt_data.get("total_debt", 0)
        question_lower = question.lower()

        max_desc = "N/A"
        max_amount = 0.0
        max_comprobante = ""
        max_fecha = ""
        if items:
            max_item = max(items, key=lambda x: float(x.get("amount", 0)))
            max_desc = max_item.get("description", "Item")
            max_amount = float(max_item.get("amount", 0))
            max_comprobante = max_item.get("comprobante", "")
            max_fecha = max_item.get("fecha", "")

        # Build invoice info string if available
        invoice_info = ""
        if max_comprobante or max_fecha:
            invoice_info = f"\n📄 Factura: {max_comprobante or 'N/A'} | Fecha: {max_fecha or 'N/A'}"

        if any(word in question_lower for word in ["más debo", "mayor", "más caro", "mayor valor"]):
            return (
                f"**{customer_name}**, según tu deuda actual:\n\n"
                f"💊 El producto con mayor importe pendiente es:\n"
                f"**{max_desc}** - ${max_amount:,.2f}{invoice_info}\n\n"
                f"📊 Total de tu deuda: ${float(total_debt):,.2f}"
            )

        if any(word in question_lower for word in ["cuántos", "cuantos", "cantidad"]):
            return (
                f"**{customer_name}**, tienes **{len(items)} productos** "
                f"pendientes de pago.\n\n"
                f"📊 Total: ${float(total_debt):,.2f}"
            )

        return (
            f"**{customer_name}**, aquí está la información de tu cuenta:\n\n"
            f"📦 **Productos pendientes:** {len(items)}\n"
            f"💰 **Total:** ${float(total_debt):,.2f}\n"
            f"📊 **Mayor importe:** {max_desc} (${max_amount:,.2f}){invoice_info}\n\n"
            "¿Necesitas más detalles? Escribe *deuda* para ver el listado completo."
        )
