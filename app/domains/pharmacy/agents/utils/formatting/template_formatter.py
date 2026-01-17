# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Generic template-based response formatting.
#              Replaces 12 duplicate format_* methods with single generic method.
# Tenant-Aware: Yes - state contains organization-specific data.
# ============================================================================
"""
Template-based response formatting with generic pattern.

This module provides a single generic format() method that replaces
the 12 duplicate format_* methods in the original response_formatter.py.

Single Responsibility: Load template → Build variables → Render → Return response.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.utils.formatting.constants import (
    FormattingLimits,
    ResponseType,
)
from app.domains.pharmacy.agents.utils.formatting.state_transformer import (
    StateTransformer,
)
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


class TemplateBasedFormatter:
    """
    Generic template-based response formatter.

    Single Responsibility: Load template → Build variables → Render → Return response.

    This class eliminates duplication by providing a single format() method
    that handles all template types using a consistent pattern.
    """

    def __init__(
        self,
        template_loader: WhatsAppFormatterTemplateLoader | None = None,
        template_renderer: PharmacyTemplateRenderer | None = None,
        state_transformer: StateTransformer | None = None,
    ) -> None:
        """
        Initialize formatter with dependencies.

        Args:
            template_loader: Optional custom template loader
            template_renderer: Optional custom template renderer
            state_transformer: Optional custom state transformer
        """
        self._loader = template_loader or get_whatsapp_template_loader()
        self._renderer = template_renderer or PharmacyTemplateRenderer()
        self._transformer = state_transformer or StateTransformer()
        self._templates: LoadedWhatsAppTemplates | None = None

    async def _ensure_templates_loaded(self) -> LoadedWhatsAppTemplates:
        """Ensure templates are loaded (lazy loading)."""
        if self._templates is None:
            self._templates = await self._loader.load()
        return self._templates

    async def format(
        self,
        template_key: str,
        state: "PharmacyStateV2",
        extra_variables: dict[str, Any] | None = None,
        response_type_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Generic format method for any template.

        This single method replaces all 12 format_* methods by using a consistent
        pattern: load template → check → build variables → render → return.

        Args:
            template_key: Template key (e.g., "debt_response", "main_menu")
            state: Current conversation state
            extra_variables: Additional variables to merge
            response_type_override: Override template's response_type

        Returns:
            State updates with formatted response
        """
        templates = await self._ensure_templates_loaded()
        template = templates.get(template_key)

        if not template:
            logger.error(f"Template '{template_key}' not found")
            return self._fallback_response(f"Error loading template: {template_key}")

        # Build variables from state
        if template_key == "invoice_detail":
            variables = self._transformer.build_invoice_variables(state)
        else:
            variables = self._transformer.build_variables(state)

        if extra_variables:
            variables.update(extra_variables)

        # Render body
        body = self._renderer.render(template.body_template, variables)

        # Determine response type
        response_type = response_type_override or template.response_type or ResponseType.TEXT

        # Build response based on type
        result: dict[str, Any] = {
            "response_type": response_type,
            "_formatted_body": body,
        }

        if response_type == ResponseType.BUTTONS:
            result["response_buttons"] = self._render_buttons(template_key, variables, templates)
            result["response_list_items"] = None
            if template.title:
                result["_formatted_title"] = template.title
        elif response_type == ResponseType.LIST:
            result["response_buttons"] = None
            result["response_list_items"] = self._build_list_items(state, template)
            if template.title:
                result["_formatted_title"] = template.title
            if template.list_button_text:
                result["_list_button_text"] = template.list_button_text
        else:  # text
            result["response_buttons"] = None
            result["response_list_items"] = None

        # Add template-specific state updates
        if template.awaiting_input:
            result["awaiting_input"] = template.awaiting_input

        # ALWAYS set is_complete to ensure checkpoint value is overridden
        # Only farewell and validation_failed templates set is_complete=True
        result["is_complete"] = bool(template.is_complete)

        return result

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
            logger.warning(
                f"[_render_buttons] No buttons for template_key={template_key}, "
                f"template_exists={template is not None}, "
                f"buttons_count={len(template.buttons) if template else 0}"
            )
            return None

        buttons = []
        for btn in template.buttons:
            titulo = btn.titulo
            if btn.titulo_template:
                titulo = self._renderer.render(btn.titulo_template, variables)
            buttons.append({"id": btn.id, "titulo": titulo or ""})

        return buttons

    def _build_list_items(
        self,
        state: "PharmacyStateV2",
        template: Any,
    ) -> list[dict[str, str]]:
        """
        Build list items from state and template.

        Used for account_selection and similar list-based responses.

        Args:
            state: Current conversation state
            template: Template with list configuration

        Returns:
            List of item dicts with id, titulo, descripcion
        """
        accounts = state.get("registered_accounts") or []
        list_items: list[dict[str, str]] = []

        max_items = FormattingLimits.MAX_LIST_ITEMS
        max_title_chars = FormattingLimits.MAX_TITLE_CHARS

        for acc in accounts[:max_items]:
            debt = acc.get("debt", 0)
            list_items.append(
                {
                    "id": f"account_{acc.get('id', '')}",
                    "titulo": str(acc.get("name", ""))[:max_title_chars],
                    "descripcion": f"Deuda: ${debt:,.2f}",
                }
            )

        # Add option to add new person from template
        if len(accounts) < max_items and template.list_item_add_person:
            add_person = template.list_item_add_person
            list_items.append(
                {
                    "id": add_person.id,
                    "titulo": add_person.titulo,
                    "descripcion": add_person.descripcion,
                }
            )

        return list_items

    def _fallback_response(self, message: str) -> dict[str, Any]:
        """
        Create a fallback response when template loading fails.

        Args:
            message: Fallback message text

        Returns:
            Basic text response structure
        """
        return {
            "response_type": ResponseType.TEXT,
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": message,
        }

    def invalidate_cache(self) -> None:
        """Clear cached templates. Call after modifying templates."""
        self._templates = None
