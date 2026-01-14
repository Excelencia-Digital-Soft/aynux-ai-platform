# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Keyword matcher service for pharmacy domain.
#              Matches user input against database-stored keywords/lemmas.
# Tenant-Aware: Yes - loads patterns per organization_id from DB cache.
# ============================================================================
"""
Keyword Matcher Service - Database-driven keyword matching for pharmacy nodes.

Provides utilities to match user messages against intent keywords stored in
the database, avoiding hardcoded keyword sets in node implementations.

Usage:
    from app.domains.pharmacy.agents.utils.keyword_matcher import KeywordMatcher

    # Check if message matches an intent's keywords
    if await KeywordMatcher.matches_intent(db, org_id, message, "account_add_new"):
        # User wants to add a new person

    # Get all matching keywords from a message
    matched = await KeywordMatcher.get_matched_keywords(db, org_id, message, "account_add_new")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.cache.domain_intent_cache import domain_intent_cache

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class KeywordMatcher:
    """
    Matches user input against database-stored keywords/lemmas.

    Uses the domain_intent_cache to load patterns from the database
    with multi-layer caching (Memory → Redis → DB).

    All methods are static for easy usage without instantiation.
    """

    @staticmethod
    async def matches_intent(
        db: "AsyncSession | None",
        organization_id: UUID,
        message: str,
        intent_key: str,
        domain_key: str = "pharmacy",
    ) -> bool:
        """
        Check if message matches any keyword/lemma for the given intent.

        Args:
            db: Database session (can be None, cache may have data)
            organization_id: Organization UUID for multi-tenant isolation
            message: User message to check
            intent_key: Intent identifier (e.g., "account_add_new")
            domain_key: Domain scope (default: "pharmacy")

        Returns:
            True if any keyword/lemma from the intent is found in the message

        Example:
            >>> if await KeywordMatcher.matches_intent(db, org_id, "quiero agregar", "account_add_new"):
            ...     # User wants to add new person
        """
        if not message:
            return False

        try:
            patterns = await domain_intent_cache.get_patterns(db, organization_id, domain_key)
            intent_data = patterns.get("intents", {}).get(intent_key)

            if not intent_data:
                logger.debug(f"Intent '{intent_key}' not found in patterns for org {organization_id}")
                return False

            # Get lemmas and keywords from intent
            lemmas = intent_data.get("lemmas", [])
            keywords = intent_data.get("keywords", [])
            all_keywords = set(lemmas) | set(keywords)

            if not all_keywords:
                return False

            message_lower = message.lower().strip()
            return any(kw in message_lower for kw in all_keywords)

        except Exception as e:
            logger.warning(f"Error checking intent match for '{intent_key}': {e}")
            return False

    @staticmethod
    async def get_matched_keywords(
        db: "AsyncSession | None",
        organization_id: UUID,
        message: str,
        intent_key: str,
        domain_key: str = "pharmacy",
    ) -> list[str]:
        """
        Get all keywords/lemmas from the intent that match the message.

        Args:
            db: Database session
            organization_id: Organization UUID
            message: User message to check
            intent_key: Intent identifier
            domain_key: Domain scope (default: "pharmacy")

        Returns:
            List of matched keywords found in the message
        """
        if not message:
            return []

        try:
            patterns = await domain_intent_cache.get_patterns(db, organization_id, domain_key)
            intent_data = patterns.get("intents", {}).get(intent_key)

            if not intent_data:
                return []

            lemmas = intent_data.get("lemmas", [])
            keywords = intent_data.get("keywords", [])
            all_keywords = set(lemmas) | set(keywords)

            message_lower = message.lower().strip()
            return [kw for kw in all_keywords if kw in message_lower]

        except Exception as e:
            logger.warning(f"Error getting matched keywords for '{intent_key}': {e}")
            return []

    @staticmethod
    async def matches_any_of(
        db: "AsyncSession | None",
        organization_id: UUID,
        message: str,
        intent_keys: list[str],
        domain_key: str = "pharmacy",
    ) -> str | None:
        """
        Check if message matches any of the given intents.

        Args:
            db: Database session
            organization_id: Organization UUID
            message: User message to check
            intent_keys: List of intent identifiers to check
            domain_key: Domain scope (default: "pharmacy")

        Returns:
            First matching intent_key, or None if no match
        """
        for intent_key in intent_keys:
            if await KeywordMatcher.matches_intent(db, organization_id, message, intent_key, domain_key):
                return intent_key
        return None


__all__ = ["KeywordMatcher"]
