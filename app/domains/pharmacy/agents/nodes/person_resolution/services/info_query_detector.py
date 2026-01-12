"""
InfoQueryDetector - Database-driven info query detection.

Detects info queries (pharmacy info, hours, address, etc.) using patterns
loaded from database. No hardcoded patterns allowed.

Usage:
    detector = InfoQueryDetector()
    is_info = await detector.is_info_query(message, db, organization_id)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.cache.domain_intent_cache import domain_intent_cache

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class InfoQueryDetector:
    """
    Database-driven detector for info queries.

    Info queries are messages asking for pharmacy information that
    don't require user identification (hours, address, phone, etc.).

    Loads patterns from database via domain_intent_cache.
    """

    DOMAIN_KEY = "pharmacy"
    INTENT_KEY = "info_query"

    def __init__(self) -> None:
        """Initialize detector."""
        self._patterns_cache: dict[UUID, list[dict[str, Any]]] = {}

    async def is_info_query(
        self,
        message: str,
        db: "AsyncSession | None" = None,
        organization_id: UUID | None = None,
    ) -> bool:
        """
        Check if message is an info query.

        Args:
            message: User message to check
            db: Optional database session (cache creates own if None)
            organization_id: Tenant UUID

        Returns:
            True if message is an info query
        """
        if not message or not organization_id:
            return False

        text_lower = message.lower().strip()

        # Get patterns from cache/database
        patterns = await self._get_patterns(db, organization_id)

        if not patterns:
            logger.warning(
                f"No info_query patterns found for org {organization_id}. "
                "Please add info_query intent to domain_intents table."
            )
            return False

        # Check patterns
        for phrase_data in patterns:
            phrase = phrase_data.get("phrase", "")
            match_type = phrase_data.get("match_type", "contains")

            if not phrase:
                continue

            if match_type == "exact":
                if text_lower == phrase:
                    logger.debug(f"Info query detected (exact): '{phrase}'")
                    return True
            elif match_type == "prefix":
                if text_lower.startswith(phrase):
                    logger.debug(f"Info query detected (prefix): '{phrase}'")
                    return True
            else:  # contains
                if phrase in text_lower:
                    logger.debug(f"Info query detected (contains): '{phrase}'")
                    return True

        return False

    async def _get_patterns(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """
        Get info_query patterns from cache/database.

        Args:
            db: Optional database session
            organization_id: Tenant UUID

        Returns:
            List of phrase patterns {phrase, match_type}
        """
        # Get all patterns from cache
        all_patterns = await domain_intent_cache.get_patterns(
            db, organization_id, self.DOMAIN_KEY
        )

        # Extract info_query phrases
        info_query = all_patterns.get("intents", {}).get(self.INTENT_KEY, {})
        return info_query.get("phrases", [])


# Singleton instance for convenience
info_query_detector = InfoQueryDetector()


__all__ = ["InfoQueryDetector", "info_query_detector"]
