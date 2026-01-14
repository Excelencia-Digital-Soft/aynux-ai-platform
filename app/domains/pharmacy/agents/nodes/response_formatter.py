"""
Response Formatter - WhatsApp message formatting with buttons and lists.

This node formats responses for WhatsApp delivery, supporting:
- Text messages
- Interactive Reply Buttons (max 3 buttons)
- Interactive Lists (up to 10 items)

The formatter sets state fields that are read by the WhatsApp sender service
to determine the appropriate message type and structure.

REFACTORED: Now uses YAML templates from whatsapp_formatter.yaml instead of
hardcoded strings. All text content loaded via WhatsAppFormatterTemplateLoader.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from app.domains.pharmacy.agents.utils.response.template_renderer import (
    PharmacyTemplateRenderer,
)
from app.domains.pharmacy.agents.utils.whatsapp_template_loader import (
    LoadedWhatsAppTemplates,
    WhatsAppFormatterTemplateLoader,
    get_whatsapp_template_loader,
)

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Formats responses for WhatsApp delivery with button/list support.

    This class generates the appropriate response structure based on
    the current state and context. The formatted response is stored
    in state fields that the WhatsApp sender service reads.

    REFACTORED: Uses YAML templates for all text content.

    Response Types:
    - text: Simple text message
    - buttons: Up to 3 reply buttons
    - list: Interactive list with up to 10 items
    """

    def __init__(
        self,
        template_loader: WhatsAppFormatterTemplateLoader | None = None,
        template_renderer: PharmacyTemplateRenderer | None = None,
    ) -> None:
        """
        Initialize response formatter with template loader.

        Args:
            template_loader: Optional custom template loader
            template_renderer: Optional custom template renderer
        """
        self._loader = template_loader or get_whatsapp_template_loader()
        self._renderer = template_renderer or PharmacyTemplateRenderer()
        self._templates: LoadedWhatsAppTemplates | None = None

    async def _ensure_templates_loaded(self) -> LoadedWhatsAppTemplates:
        """Ensure templates are loaded (lazy loading)."""
        if self._templates is None:
            self._templates = await self._loader.load()
        return self._templates

    def _build_variables(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Build variables dictionary from state.

        Args:
            state: Current conversation state

        Returns:
            Variables dictionary for template rendering
        """
        total_debt = state.get("total_debt") or 0
        payment_amount = state.get("payment_amount") or 0
        customer_name = state.get("customer_name") or ""

        # Build debt details from debt_items if available
        debt_details = ""
        debt_items = state.get("debt_items") or []
        if debt_items:
            # Group by invoice and format (max 5 invoices)
            invoices: dict[str, float] = {}
            for item in debt_items:
                if isinstance(item, dict):
                    inv_num = item.get("invoice_number") or "Sin comprobante"
                    amount = float(item.get("amount") or 0)
                else:
                    inv_num = getattr(item, "invoice_number", "Sin comprobante")
                    amount = float(getattr(item, "amount", 0))
                invoices[inv_num] = invoices.get(inv_num, 0) + amount

            lines = []
            for inv_num, inv_total in list(invoices.items())[:5]:
                lines.append(f"📄 {inv_num}: ${inv_total:,.2f}")
            if len(invoices) > 5:
                lines.append(f"... y {len(invoices) - 5} comprobantes más")
            debt_details = "\n".join(lines)

        return {
            "pharmacy_name": state.get("pharmacy_name") or "Farmacia",
            "customer_name": customer_name or "tu cuenta",
            "customer_name_greeting": f" {customer_name}" if customer_name else "",
            "total_debt": f"${total_debt:,.2f}",
            "payment_amount": f"${payment_amount:,.2f}",
            "remaining_balance": f"${(total_debt - payment_amount):,.2f}",
            "mp_payment_link": state.get("mp_payment_link") or "",
            "debt_details": debt_details,
        }

    def _render_buttons(
        self,
        template_key: str,
        variables: dict[str, Any],
        templates: LoadedWhatsAppTemplates,
    ) -> list[dict[str, str]] | None:
        """
        Render buttons from template.

        Args:
            template_key: Template short key
            variables: Variables for rendering
            templates: Loaded templates

        Returns:
            List of button dicts or None
        """
        template = templates.get(template_key)
        if not template or not template.buttons:
            return None

        buttons = []
        for btn in template.buttons:
            titulo = btn.titulo
            if btn.titulo_template:
                titulo = self._renderer.render(btn.titulo_template, variables)
            buttons.append({"id": btn.id, "titulo": titulo or ""})

        return buttons

    async def format_debt_response(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format debt display with action buttons.

        Shows total debt and provides buttons for:
        - Pay full amount
        - Pay partial amount
        - Switch to different account

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("debt_response")

        if not template:
            logger.error("Template 'debt_response' not found")
            return self._fallback_response("Error loading template")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)
        buttons = self._render_buttons("debt_response", variables, templates)

        return {
            "response_type": "buttons",
            "response_buttons": buttons,
            "response_list_items": None,
            "_formatted_body": body,
            "_formatted_title": template.title,
        }

    async def format_payment_confirmation(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format payment confirmation with Yes/No buttons.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        is_partial = state.get("is_partial_payment", False)

        template_key = "payment_confirmation_partial" if is_partial else "payment_confirmation_full"
        template = templates.get(template_key)

        if not template:
            logger.error("Template '%s' not found", template_key)
            return self._fallback_response("Error loading template")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)
        buttons = self._render_buttons(template_key, variables, templates)

        return {
            "response_type": "buttons",
            "response_buttons": buttons,
            "response_list_items": None,
            "_formatted_body": body,
            "_formatted_title": template.title,
        }

    async def format_payment_link(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format payment link message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("payment_link")

        if not template:
            logger.error("Template 'payment_link' not found")
            return self._fallback_response("Error loading template")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
        }

    async def format_account_selection(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format account selection list.

        Uses WhatsApp Interactive List for multiple accounts.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("account_selection")

        if not template:
            logger.error("Template 'account_selection' not found")
            return self._fallback_response("Error loading template")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)

        # Build list items dynamically from accounts (max 10)
        accounts = state.get("registered_accounts") or []
        list_items: list[dict[str, str]] = []

        for acc in accounts[:10]:
            debt = acc.get("debt", 0)
            list_items.append(
                {
                    "id": f"account_{acc.get('id', '')}",
                    "titulo": str(acc.get("name", ""))[:24],  # Max 24 chars for title
                    "descripcion": f"Deuda: ${debt:,.2f}",
                }
            )

        # Add option to add new person from template
        if len(accounts) < 10 and template.list_item_add_person:
            add_person = template.list_item_add_person
            list_items.append(
                {
                    "id": add_person.id,
                    "titulo": add_person.titulo,
                    "descripcion": add_person.descripcion,
                }
            )

        return {
            "response_type": "list",
            "response_buttons": None,
            "response_list_items": list_items,
            "_formatted_body": body,
            "_formatted_title": template.title,
            "_list_button_text": template.list_button_text,
        }

    async def format_own_or_other(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format own/other debt selection.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("own_or_other")

        if not template:
            logger.error("Template 'own_or_other' not found")
            return self._fallback_response("Error loading template")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)
        buttons = self._render_buttons("own_or_other", variables, templates)

        return {
            "response_type": "buttons",
            "response_buttons": buttons,
            "response_list_items": None,
            "_formatted_body": body,
            "_formatted_title": template.title,
        }

    async def format_main_menu(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format main menu message with WhatsApp interactive buttons.

        Per pharmacy_flujo_mejorado_v2.md, main menu should use 3 buttons:
        - Consultar deuda
        - Pagar deuda
        - Ver otra cuenta

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("main_menu")

        if not template:
            logger.error("Template 'main_menu' not found")
            return self._fallback_response("Error loading template")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)

        # Render buttons if template has them
        buttons = self._render_buttons("main_menu", variables, templates)
        response_type = template.response_type or "text"

        return {
            "response_type": response_type,
            "response_buttons": buttons,
            "response_list_items": None,
            "_formatted_body": body,
            "_formatted_title": template.title if hasattr(template, "title") else None,
            "awaiting_input": template.awaiting_input,
        }

    async def format_pay_debt_menu(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format PAY_DEBT_MENU response (Flujo 2: Pagar deuda directo).

        Shows debt summary with 2 payment buttons.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("pay_debt_menu")

        if not template:
            logger.error("Template 'pay_debt_menu' not found")
            return self._fallback_response("Error loading template")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)
        buttons = self._render_buttons("pay_debt_menu", variables, templates)

        return {
            "response_type": template.response_type or "buttons",
            "response_buttons": buttons,
            "response_list_items": None,
            "_formatted_body": body,
            "_formatted_title": template.title,
            "awaiting_input": template.awaiting_input,
        }

    async def format_invoice_detail(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format INVOICE_DETAIL response.

        Shows single invoice detail (no medications - privacy rule).

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("invoice_detail")

        if not template:
            logger.error("Template 'invoice_detail' not found")
            return self._fallback_response("Error loading template")

        # Build variables including invoice-specific data
        variables = self._build_variables(state)
        variables["invoice_number"] = state.get("selected_invoice_number") or "N/A"
        variables["invoice_date"] = state.get("selected_invoice_date") or "N/A"
        invoice_amount = state.get("selected_invoice_amount") or 0
        variables["invoice_amount"] = f"${invoice_amount:,.2f}"

        body = self._renderer.render(template.body_template, variables)
        buttons = self._render_buttons("invoice_detail", variables, templates)

        return {
            "response_type": template.response_type or "buttons",
            "response_buttons": buttons,
            "response_list_items": None,
            "_formatted_body": body,
            "_formatted_title": template.title,
            "awaiting_input": template.awaiting_input,
        }

    async def format_no_debt(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format no debt message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("no_debt")

        if not template:
            logger.error("Template 'no_debt' not found")
            return self._fallback_response("Error loading template")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
        }

    async def format_error(
        self,
        error_type: str,
        state: "PharmacyStateV2",
    ) -> dict[str, Any]:
        """
        Format error message.

        Args:
            error_type: Type of error (plex_unavailable, payment_error, generic)
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()

        # Map error type to template key
        template_key = f"error_{error_type}"
        template = templates.get(template_key)

        # Fall back to generic error if specific not found
        if not template:
            template = templates.get("error_generic")

        if not template:
            logger.error("No error template found for '%s'", error_type)
            return self._fallback_response("Error inesperado")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
            "error_count": (state.get("error_count") or 0) + 1,
        }

    async def format_farewell(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format farewell message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("farewell")

        if not template:
            logger.error("Template 'farewell' not found")
            return self._fallback_response("Hasta luego")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
            "is_complete": template.is_complete,
        }

    async def format_request_dni(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format DNI request message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("request_dni")

        if not template:
            logger.error("Template 'request_dni' not found")
            return self._fallback_response("Por favor ingresá tu DNI")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
            "awaiting_input": template.awaiting_input,
        }

    async def format_request_name(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format name request message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get("request_name")

        if not template:
            logger.error("Template 'request_name' not found")
            return self._fallback_response("Por favor ingresá tu nombre")

        variables = self._build_variables(state)
        body = self._renderer.render(template.body_template, variables)

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
            "awaiting_input": template.awaiting_input,
        }

    def _fallback_response(self, message: str) -> dict[str, Any]:
        """
        Create a fallback response when template loading fails.

        Args:
            message: Fallback message text

        Returns:
            Basic text response structure
        """
        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": message,
        }


# Singleton instance
_response_formatter: ResponseFormatter | None = None


def get_response_formatter() -> ResponseFormatter:
    """Get or create the singleton response formatter instance."""
    global _response_formatter
    if _response_formatter is None:
        _response_formatter = ResponseFormatter()
    return _response_formatter


def invalidate_response_formatter_cache() -> None:
    """
    Invalidate the response formatter singleton and template cache.

    Forces templates to be reloaded on next access.
    Call this after modifying whatsapp_formatter.yaml.
    """
    global _response_formatter
    # Invalidate WhatsApp template loader cache
    from app.domains.pharmacy.agents.utils.whatsapp_template_loader import (
        invalidate_whatsapp_template_cache,
    )

    invalidate_whatsapp_template_cache()
    # Reset formatter singleton (will recreate with fresh templates)
    _response_formatter = None
    logger.info("Response formatter cache invalidated")


# LangGraph node function
async def response_formatter_node(
    state: "PharmacyStateV2",
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """
    LangGraph node function for response formatting.

    This node is called after processing to format the response
    for WhatsApp delivery. It determines the appropriate format
    based on the current state and intent.

    Args:
        state: Current conversation state
        config: Optional configuration

    Returns:
        State updates with response formatting and AIMessage
    """
    formatter = get_response_formatter()

    intent = state.get("intent")
    has_debt = state.get("has_debt", False)
    is_complete = state.get("is_complete", False)

    # Determine the appropriate format based on state
    result: dict[str, Any]

    if is_complete:
        result = await formatter.format_farewell(state)
    elif intent == "check_debt" or intent == "debt_query":
        if has_debt:
            result = await formatter.format_debt_response(state)
        else:
            result = await formatter.format_no_debt(state)
    elif intent == "pay_debt_menu":
        # PAY_DEBT_MENU flow (Flujo 2: Pagar deuda directo)
        if has_debt:
            result = await formatter.format_pay_debt_menu(state)
        else:
            result = await formatter.format_no_debt(state)
    elif intent == "view_invoice_detail":
        # INVOICE_DETAIL flow
        result = await formatter.format_invoice_detail(state)
    elif intent in ("pay_full", "pay_partial", "payment_link"):
        if state.get("mp_payment_link"):
            result = await formatter.format_payment_link(state)
        elif state.get("awaiting_payment_confirmation"):
            result = await formatter.format_payment_confirmation(state)
        else:
            result = await formatter.format_debt_response(state)
    elif intent == "switch_account":
        if state.get("awaiting_account_selection"):
            result = await formatter.format_account_selection(state)
        else:
            result = await formatter.format_own_or_other(state)
    elif intent == "show_menu":
        result = await formatter.format_main_menu(state)
    elif intent == "farewell":
        result = await formatter.format_farewell(state)
    else:
        # Default: show main menu
        result = await formatter.format_main_menu(state)

    # Add AIMessage with formatted body for extract_bot_response() to find
    body = result.get("_formatted_body", "")
    if body:
        result["messages"] = [AIMessage(content=body)]

    return result
