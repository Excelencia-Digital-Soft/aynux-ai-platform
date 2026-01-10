# ============================================================================
# SCOPE: MULTI-TENANT
# Description: YAML template loader for pharmacy domain responses.
#              Handles lazy loading and caching of template files.
# Tenant-Aware: Yes - templates may contain tenant-specific placeholders.
# ============================================================================
"""
Pharmacy Template Loader - YAML template loading and caching.

Responsibilities:
- Load system context YAML
- Load critical templates YAML
- Load fallback templates YAML
- Cache loaded templates for reuse
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class LoadedTemplates:
    """Result of loading all template files."""

    system_context: str
    critical_templates: dict[str, str]
    fallback_templates: dict[str, str]


class PharmacyTemplateLoader:
    """
    Lazy loader for pharmacy YAML templates.

    Single Responsibility: Loading and caching YAML template files.
    """

    SYSTEM_CONTEXT_FILE = "pharmacy/system_context.yaml"
    CRITICAL_TEMPLATES_FILE = "pharmacy/critical_templates.yaml"
    FALLBACK_TEMPLATES_FILE = "pharmacy/fallback_templates.yaml"

    def __init__(self, templates_dir: Path | str | None = None) -> None:
        """
        Initialize template loader.

        Args:
            templates_dir: Path to prompts/templates directory.
                          Defaults to app/prompts/templates.
        """
        if templates_dir is None:
            self._templates_dir = (
                Path(__file__).parents[5] / "prompts" / "templates"
            )
        else:
            self._templates_dir = Path(templates_dir)

        self._loaded: LoadedTemplates | None = None

    @property
    def is_loaded(self) -> bool:
        """Check if templates have been loaded."""
        return self._loaded is not None

    async def load(self) -> LoadedTemplates:
        """
        Load all templates. Returns cached result if already loaded.

        Returns:
            LoadedTemplates with all template data
        """
        if self._loaded is not None:
            return self._loaded

        system_context = await self._load_system_context()
        critical = await self._load_critical_templates()
        fallback = await self._load_fallback_templates()

        self._loaded = LoadedTemplates(
            system_context=system_context,
            critical_templates=critical,
            fallback_templates=fallback,
        )

        return self._loaded

    async def _load_system_context(self) -> str:
        """Load system context YAML."""
        path = self._templates_dir / self.SYSTEM_CONTEXT_FILE
        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            data = yaml.safe_load(content)
            logger.debug("Loaded system context from %s", path)
            if not isinstance(data, dict):
                logger.warning("System context YAML is not a dict: %s", type(data))
                return ""
            return data.get("system_prompt", "")
        except Exception as e:
            logger.error("Failed to load system context: %s", e)
            return ""

    async def _load_critical_templates(self) -> dict[str, str]:
        """Load critical templates YAML."""
        path = self._templates_dir / self.CRITICAL_TEMPLATES_FILE
        return await self._load_template_file(path, "critical")

    async def _load_fallback_templates(self) -> dict[str, str]:
        """Load fallback templates YAML."""
        path = self._templates_dir / self.FALLBACK_TEMPLATES_FILE
        return await self._load_template_file(path, "fallback")

    async def _load_template_file(
        self, path: Path, template_type: str
    ) -> dict[str, str]:
        """
        Load a template YAML file.

        Args:
            path: Path to YAML file
            template_type: Type name for logging

        Returns:
            Dictionary mapping short keys to templates
        """
        templates: dict[str, str] = {}
        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                logger.warning("%s templates YAML is not a dict: %s", template_type, type(data))
                return templates

            for prompt in data.get("prompts", []):
                key = prompt.get("key", "")
                template = prompt.get("template", "")
                if key and template:
                    # Extract short key from full namespace
                    short_key = key.split(".")[-1]
                    templates[short_key] = template

            logger.debug("Loaded %d %s templates", len(templates), template_type)
        except Exception as e:
            logger.error("Failed to load %s templates: %s", template_type, e)

        return templates


__all__ = ["LoadedTemplates", "PharmacyTemplateLoader"]
