"""
Debt Format Templates Loader

Loads and provides access to debt formatting templates from YAML configuration.
Templates are loaded once at startup and cached for performance.

NOTE: All templates MUST be defined in the YAML file.
      No hardcoded fallbacks - missing templates raise errors.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import yaml

logger = logging.getLogger(__name__)

# Path to the templates file
TEMPLATES_PATH = Path(__file__).parent.parent.parent.parent.parent / "prompts/templates/pharmacy/debt_format.yaml"


class TemplateNotFoundError(Exception):
    """Raised when a required template is not found in configuration."""

    def __init__(self, template_key: str, section: str | None = None) -> None:
        self.template_key = template_key
        self.section = section
        location = f"{section}.{template_key}" if section else template_key
        super().__init__(f"Template '{location}' not found in debt_format.yaml")


def _load_templates() -> dict[str, Any]:
    """
    Load templates from YAML file.

    Raises:
        FileNotFoundError: If YAML file doesn't exist
        yaml.YAMLError: If YAML file is invalid
    """
    if not TEMPLATES_PATH.exists():
        raise FileNotFoundError(f"Debt format templates not found at {TEMPLATES_PATH}")

    with open(TEMPLATES_PATH, encoding="utf-8") as f:
        loaded = yaml.safe_load(f)

    if not loaded:
        raise ValueError(f"Debt format templates file is empty: {TEMPLATES_PATH}")

    if not isinstance(loaded, dict):
        raise ValueError(f"Debt format templates file must be a dictionary: {TEMPLATES_PATH}")

    logger.debug(f"Loaded debt format templates from {TEMPLATES_PATH}")
    return cast(dict[str, Any], loaded)


class DebtFormatTemplates:
    """
    Provides access to debt formatting templates.

    Loads templates from YAML file once and provides typed access.
    Raises TemplateNotFoundError if required templates are missing.
    """

    def __init__(self, templates: dict[str, Any]) -> None:
        self._templates = templates

    def reload(self) -> None:
        """Force reload templates from file."""
        self._templates = _load_templates()

    def _get_required(self, section: str, key: str) -> str:
        """Get a required template value, raising error if missing."""
        section_data = self._templates.get(section)
        if not section_data:
            raise TemplateNotFoundError(key, section)

        value = section_data.get(key)
        if value is None:
            raise TemplateNotFoundError(key, section)

        return str(value)

    # Utility strings
    @property
    def no_details(self) -> str:
        return self._get_required("utility", "no_details")

    @property
    def no_invoice(self) -> str:
        return self._get_required("utility", "no_invoice")

    @property
    def more_products(self) -> str:
        return self._get_required("utility", "more_products")

    @property
    def more_invoices(self) -> str:
        return self._get_required("utility", "more_invoices")

    @property
    def more_items(self) -> str:
        return self._get_required("utility", "more_items")

    @property
    def products_summary(self) -> str:
        return self._get_required("utility", "products_summary")

    # Payment options
    def get_payment_option(self, option: str) -> str:
        """Get payment option template by key (full, half, minimum, custom)."""
        return self._get_required("payment_options", option)

    # Action menu
    def get_action_menu_item(self, item: str) -> str:
        """Get action menu item template by key."""
        return self._get_required("action_menu", item)

    # PAY_DEBT_MENU menu items
    def get_pay_debt_menu_item(self, item: str) -> str:
        """Get pay debt menu item template by key (pay_full, pay_partial, back_to_menu)."""
        return self._get_required("pay_debt_menu", item)

    # INVOICE_DETAIL menu items
    def get_invoice_detail_menu_item(self, item: str) -> str:
        """Get invoice detail menu item template by key."""
        return self._get_required("invoice_detail_menu", item)

    # Full response templates
    @property
    def smart_debt_response(self) -> str:
        value = self._templates.get("smart_debt_response")
        if value is None:
            raise TemplateNotFoundError("smart_debt_response")
        return str(value)

    @property
    def pay_debt_menu_response(self) -> str:
        """Template for PAY_DEBT_MENU flow (Flujo 2: Pagar deuda directo)."""
        value = self._templates.get("pay_debt_menu_response")
        if value is None:
            raise TemplateNotFoundError("pay_debt_menu_response")
        return str(value)

    @property
    def invoice_detail_response(self) -> str:
        """Template for INVOICE_DETAIL flow (Ver detalle de factura)."""
        value = self._templates.get("invoice_detail_response")
        if value is None:
            raise TemplateNotFoundError("invoice_detail_response")
        return str(value)

    @property
    def payment_confirm_partial(self) -> str:
        return self._get_required("payment_confirm", "partial")

    @property
    def payment_confirm_full(self) -> str:
        return self._get_required("payment_confirm", "full")


# Singleton instance
_templates_instance: DebtFormatTemplates | None = None


def get_debt_format_templates() -> DebtFormatTemplates:
    """Get singleton templates instance."""
    global _templates_instance
    if _templates_instance is None:
        _templates_instance = DebtFormatTemplates(_load_templates())
    return _templates_instance


__all__ = ["DebtFormatTemplates", "get_debt_format_templates", "TemplateNotFoundError"]
