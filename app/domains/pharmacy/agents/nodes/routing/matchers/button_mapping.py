# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Button/list mapping matcher for routing.
#              Matches WhatsApp interactive button/list selections.
# Tenant-Aware: Yes - uses configs loaded per organization.
# Domain-Aware: Yes - supports pharmacy via domain_key.
# ============================================================================
"""
Button Mapping Matcher - Matches button/list selections from database config.

Handles WhatsApp interactive message responses (button clicks, list selections).
Also handles known list item text-to-ID mappings from database metadata.

Usage:
    matcher = ButtonMappingMatcher()
    result = await matcher.matches(ctx)
    if result:
        # Handle button selection match
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchResult

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchContext

logger = logging.getLogger(__name__)


class ButtonMappingMatcher:
    """
    Matches button/list selections from database configuration.

    Single Responsibility: Check if message matches a button/list selection.

    Priority: 50 (after global keywords)

    Button mappings:
    - Match exact button IDs from WhatsApp interactive messages
    - Handle text-to-ID mappings via metadata.text_aliases
    """

    priority = 50

    async def matches(self, ctx: "MatchContext") -> MatchResult | None:
        """
        Check if message matches a button/list selection.

        Args:
            ctx: Match context with message, state, and configs

        Returns:
            MatchResult if matched, None otherwise
        """
        configs = ctx.config_loader.get_configs_by_type("button_mapping")
        if not configs:
            return None

        # Clean message for matching
        message_clean = ctx.message.strip()
        message_lower = ctx.message_lower

        # Build text-to-ID mapping from config metadata
        text_to_id = self._build_text_mapping(configs)

        # Check if message is a known list item text and convert to ID
        if message_lower in text_to_id:
            original = message_lower
            message_clean = text_to_id[message_lower]
            logger.info(f"[MATCHER] Mapped list item text '{original}' to ID '{message_clean}'")

        # Find matching config
        for config in configs:
            if config.trigger_value == message_clean:
                logger.info(f"[MATCHER] Button mapping matched: {config.trigger_value}")
                return MatchResult(
                    config=config,
                    match_type="button_mapping",
                    handler_key="button_selection",
                )

        return None

    def _build_text_mapping(self, configs: list) -> dict[str, str]:
        """
        Build text-to-ID mapping from config metadata.

        Looks for metadata.text_aliases or metadata.text_alias in configs.
        This replaces the hardcoded list_item_text_mapping dict.

        Args:
            configs: List of RoutingConfigDTO

        Returns:
            Dict mapping lowercase text to button ID
        """
        mapping: dict[str, str] = {}

        for config in configs:
            if not config.metadata:
                continue

            # Handle text_aliases (list of texts that map to this ID)
            aliases = config.metadata.get("text_aliases", [])
            for alias in aliases:
                if isinstance(alias, str):
                    mapping[alias.lower()] = config.trigger_value

            # Handle single text_alias
            single_alias = config.metadata.get("text_alias")
            if isinstance(single_alias, str):
                mapping[single_alias.lower()] = config.trigger_value

        return mapping


class KnownListItemMatcher:
    """
    Fallback matcher for known list item patterns.

    Handles list items that may not have database configuration.
    This replaces _handle_known_list_items from the original router.

    Priority: 45 (after button mapping, before menu options)
    """

    priority = 45

    async def matches(self, ctx: "MatchContext") -> MatchResult | None:
        """
        Check if message matches known list item patterns.

        Args:
            ctx: Match context with message, state, and configs

        Returns:
            MatchResult if matched, None otherwise
        """
        # Clean trailing punctuation (WhatsApp may add "..." to list items)
        message_cleaned = ctx.message_lower.rstrip(".").strip()

        # Known patterns for adding a new person
        add_person_patterns = {"agregar persona", "btn_add_new_person"}

        if message_cleaned in add_person_patterns:
            logger.info(f"[MATCHER] Known list item detected: '{ctx.message_lower}' -> add_new_person")
            return MatchResult(
                config=None,
                match_type="known_list_item",
                handler_key="known_list_item",
                metadata={
                    "intent": "add_new_person",
                    "awaiting_input": "account_number",
                    "next_node": "auth_plex",
                },
            )

        return None


__all__ = ["ButtonMappingMatcher", "KnownListItemMatcher"]
