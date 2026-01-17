# ============================================================================
# SCOPE: MULTI-TENANT
# Description: YAML template loader for WhatsApp response formatter.
#              Handles loading of interactive message templates (buttons, lists).
# Tenant-Aware: Yes - templates contain tenant-specific placeholders.
# ============================================================================
"""
WhatsApp Formatter Template Loader - Load templates for interactive messages.

Responsibilities:
- Load whatsapp_formatter.yaml
- Parse button/list structures
- Cache loaded templates for reuse
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ButtonTemplate:
    """Template for a WhatsApp button."""

    id: str
    titulo: str | None = None  # Static title
    titulo_template: str | None = None  # Dynamic title with {variables}


@dataclass
class ListItemTemplate:
    """Template for a WhatsApp list item (static)."""

    id: str
    titulo: str
    descripcion: str


@dataclass
class WhatsAppFormatterTemplate:
    """A single WhatsApp formatter template."""

    key: str
    name: str
    response_type: str  # "text" | "buttons" | "list"
    body_template: str
    title: str | None = None
    buttons: list[ButtonTemplate] = field(default_factory=list)
    list_button_text: str | None = None
    list_item_add_person: ListItemTemplate | None = None
    awaiting_input: str | None = None
    is_complete: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadedWhatsAppTemplates:
    """Result of loading WhatsApp formatter templates."""

    templates: dict[str, WhatsAppFormatterTemplate]

    def get(self, key: str) -> WhatsAppFormatterTemplate | None:
        """Get template by short key."""
        return self.templates.get(key)


class WhatsAppFormatterTemplateLoader:
    """
    Lazy loader for WhatsApp formatter YAML templates.

    Single Responsibility: Loading and caching WhatsApp formatter templates.
    """

    TEMPLATE_FILE = "pharmacy/whatsapp_formatter.yaml"

    def __init__(self, templates_dir: Path | str | None = None) -> None:
        """
        Initialize template loader.

        Args:
            templates_dir: Path to prompts/templates directory.
                          Defaults to app/prompts/templates.
        """
        if templates_dir is None:
            self._templates_dir = Path(__file__).parents[4] / "prompts" / "templates"
        else:
            self._templates_dir = Path(templates_dir)

        self._loaded: LoadedWhatsAppTemplates | None = None

    @property
    def is_loaded(self) -> bool:
        """Check if templates have been loaded."""
        return self._loaded is not None

    async def load(self) -> LoadedWhatsAppTemplates:
        """
        Load all templates. Returns cached result if already loaded.

        Returns:
            LoadedWhatsAppTemplates with all template data
        """
        if self._loaded is not None:
            return self._loaded

        templates = await self._load_templates()
        self._loaded = LoadedWhatsAppTemplates(templates=templates)

        return self._loaded

    async def _load_templates(self) -> dict[str, WhatsAppFormatterTemplate]:
        """Load WhatsApp formatter templates from YAML."""
        path = self._templates_dir / self.TEMPLATE_FILE
        templates: dict[str, WhatsAppFormatterTemplate] = {}

        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                logger.warning("WhatsApp formatter YAML is not a dict: %s", type(data))
                return templates

            for prompt in data.get("prompts", []):
                template = self._parse_template(prompt)
                if template:
                    # Extract short key from full namespace
                    short_key = template.key.split(".")[-1]
                    templates[short_key] = template

            logger.info("Loaded %d WhatsApp formatter templates", len(templates))
            # Log main_menu template details for debugging
            if "main_menu" in templates:
                mm = templates["main_menu"]
                logger.info(
                    f"main_menu template: response_type={mm.response_type}, "
                    f"buttons_count={len(mm.buttons)}"
                )

        except FileNotFoundError:
            logger.error("WhatsApp formatter template file not found: %s", path)
        except yaml.YAMLError as e:
            logger.error("YAML parsing error in WhatsApp formatter templates: %s", e)
        except Exception as e:
            logger.exception("Failed to load WhatsApp formatter templates: %s", e)

        return templates

    def _parse_template(self, data: dict[str, Any]) -> WhatsAppFormatterTemplate | None:
        """Parse a single template from YAML data."""
        key = data.get("key", "")
        if not key:
            return None

        # Parse buttons
        buttons: list[ButtonTemplate] = []
        for btn_data in data.get("buttons", []):
            buttons.append(
                ButtonTemplate(
                    id=btn_data.get("id", ""),
                    titulo=btn_data.get("titulo"),
                    titulo_template=btn_data.get("titulo_template"),
                )
            )

        # Parse list item for add person
        list_item_add_person: ListItemTemplate | None = None
        if add_person_data := data.get("list_item_add_person"):
            list_item_add_person = ListItemTemplate(
                id=add_person_data.get("id", ""),
                titulo=add_person_data.get("titulo", ""),
                descripcion=add_person_data.get("descripcion", ""),
            )

        return WhatsAppFormatterTemplate(
            key=key,
            name=data.get("name", ""),
            response_type=data.get("response_type", "text"),
            body_template=data.get("body_template", ""),
            title=data.get("title"),
            buttons=buttons,
            list_button_text=data.get("list_button_text"),
            list_item_add_person=list_item_add_person,
            awaiting_input=data.get("awaiting_input"),
            is_complete=data.get("is_complete", False),
            metadata=data.get("metadata", {}),
        )


# Singleton instance
_loader: WhatsAppFormatterTemplateLoader | None = None


def get_whatsapp_template_loader() -> WhatsAppFormatterTemplateLoader:
    """Get or create the singleton template loader instance."""
    global _loader
    if _loader is None:
        _loader = WhatsAppFormatterTemplateLoader()
    return _loader


def invalidate_whatsapp_template_cache() -> None:
    """
    Invalidate the WhatsApp template cache.

    Forces templates to be reloaded on next access.
    Call this after modifying whatsapp_formatter.yaml.
    """
    global _loader
    if _loader is not None:
        _loader._loaded = None
        logger.info("WhatsApp template cache invalidated")


__all__ = [
    "ButtonTemplate",
    "ListItemTemplate",
    "LoadedWhatsAppTemplates",
    "WhatsAppFormatterTemplate",
    "WhatsAppFormatterTemplateLoader",
    "get_whatsapp_template_loader",
    "invalidate_whatsapp_template_cache",
]
