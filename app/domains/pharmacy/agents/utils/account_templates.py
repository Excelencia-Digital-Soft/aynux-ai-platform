# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Template loading for account switcher node.
#              Provides access to account-related message templates from YAML.
# Tenant-Aware: Yes - templates support tenant-specific variable substitution.
# ============================================================================
"""
Account Templates - Template loading for account_switcher_node.py

Provides cached access to account-related templates from fallback.yaml,
avoiding hardcoded message strings in node implementations.

Usage:
    from app.domains.pharmacy.agents.utils.account_templates import AccountTemplates

    # Get a template
    template = await AccountTemplates.get("pharmacy.fallback.no_registered_accounts")

    # Render with variables
    message = AccountTemplates.render(template, customer_name="Juan")
"""

from __future__ import annotations

import logging

from app.domains.pharmacy.agents.utils.response.template_loader import PharmacyTemplateLoader

logger = logging.getLogger(__name__)


# Template keys used by account_switcher_node.py
class AccountTemplateKeys:
    """Constants for account-related template keys."""

    NO_REGISTERED_ACCOUNTS = "pharmacy.fallback.no_registered_accounts"
    QUERYING_OWN_DEBT = "pharmacy.fallback.querying_own_debt"
    OWN_OR_OTHER_PROMPT = "pharmacy.fallback.own_or_other_prompt"
    ADD_PERSON_DNI_REQUEST = "pharmacy.fallback.add_person_dni_request"
    ACCOUNT_SELECTION_UNCLEAR = "pharmacy.fallback.account_selection_unclear"
    ACCOUNT_SELECTION_CONFIRMED = "pharmacy.fallback.account_selection_confirmed"
    ACCOUNT_LIST_HEADER = "pharmacy.fallback.account_list_header"
    ACCOUNT_LIST_FOOTER = "pharmacy.fallback.account_list_footer"
    ACCOUNT_LIST_ADD_OPTION = "pharmacy.fallback.account_list_add_option"


class AccountTemplates:
    """
    Loads and renders account-related templates from YAML.

    Uses PharmacyTemplateLoader for lazy loading and caching.
    Templates are cached at class level for efficiency.
    """

    _cache: dict[str, str] = {}
    _loader: PharmacyTemplateLoader | None = None

    @classmethod
    async def _ensure_loaded(cls) -> None:
        """Ensure templates are loaded into cache."""
        if cls._cache:
            return

        if cls._loader is None:
            cls._loader = PharmacyTemplateLoader()

        templates = await cls._loader.load()

        # Extract fallback templates into cache
        for key, template in templates.fallback_templates.items():
            cls._cache[key] = template

        logger.debug(f"Loaded {len(cls._cache)} fallback templates into AccountTemplates cache")

    @classmethod
    async def get(cls, key: str) -> str:
        """
        Get template by key.

        Args:
            key: Template key (e.g., "pharmacy.fallback.no_registered_accounts")

        Returns:
            Template string, or empty string if not found
        """
        await cls._ensure_loaded()

        template = cls._cache.get(key, "")
        if not template:
            logger.warning(f"Template not found: {key}")
        return template

    @classmethod
    def render(cls, template: str, **kwargs) -> str:
        """
        Render template with variable substitution.

        Args:
            template: Template string with {variable} placeholders
            **kwargs: Variables to substitute

        Returns:
            Rendered template string
        """
        if not template:
            return ""

        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
            return template

    @classmethod
    async def get_rendered(cls, key: str, **kwargs) -> str:
        """
        Get and render template in one call.

        Args:
            key: Template key
            **kwargs: Variables to substitute

        Returns:
            Rendered template string
        """
        template = await cls.get(key)
        return cls.render(template, **kwargs)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the template cache."""
        cls._cache.clear()
        cls._loader = None


__all__ = ["AccountTemplates", "AccountTemplateKeys"]
