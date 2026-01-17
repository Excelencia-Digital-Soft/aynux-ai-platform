# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Payment confirmation pattern loading and matching.
#              Extracted from payment_processor_node.py for SRP compliance.
# Tenant-Aware: Yes - loads patterns from database per organization.
# ============================================================================
"""
Payment confirmation pattern loading and matching.

Single Responsibility: Load and match YES/NO confirmation patterns.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """
    Normalize text for pattern matching.

    Removes accents and converts to lowercase for consistent matching.
    E.g., "Sí" → "si", "café" → "cafe"
    """
    # NFD decomposes characters: é → e + ´
    normalized = unicodedata.normalize("NFD", text.lower())
    # Remove combining diacritical marks (accents)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class ConfirmationResult:
    """
    Result of confirmation pattern matching.

    Attributes:
        result: Match result - "yes", "no", or "unclear"
        matched_pattern: The pattern that matched (if any)
    """

    result: Literal["yes", "no", "unclear"]
    matched_pattern: str | None = None


class ConfirmationPatternLoader:
    """
    Loads YES/NO confirmation patterns from database.

    Single Responsibility: Load confirmation patterns from cache/database.

    Patterns are loaded from domain_intent_cache using the 3-layer cache
    (Memory → Redis → Database) for optimal performance.
    """

    # Fallback patterns for resilience
    FALLBACK_YES: frozenset[str] = frozenset({"si", "sí", "yes", "s", "confirmo", "dale", "ok"})
    FALLBACK_NO: frozenset[str] = frozenset({"no", "n", "cancelar", "cancela", "volver"})

    @classmethod
    async def load(
        cls,
        db: "AsyncSession",
        organization_id: "UUID",
    ) -> tuple[set[str], set[str]]:
        """
        Load YES/NO confirmation patterns from database.

        Args:
            db: Database session
            organization_id: Organization UUID for multi-tenant support

        Returns:
            Tuple of (yes_patterns, no_patterns) sets
        """
        from app.core.cache.domain_intent_cache import domain_intent_cache

        try:
            patterns = await domain_intent_cache.get_confirmation_patterns(
                db, organization_id, "pharmacy"
            )

            confirm = patterns.get("confirm", {})
            reject = patterns.get("reject", {})

            yes_patterns = set(confirm.get("exact", [])) | set(confirm.get("contains", []))
            no_patterns = set(reject.get("exact", [])) | set(reject.get("contains", []))

            # Fallback to common patterns if database is empty
            if not yes_patterns:
                logger.warning("No YES patterns in database for 'confirm' intent, using fallback")
                yes_patterns = set(cls.FALLBACK_YES)

            if not no_patterns:
                logger.warning("No NO patterns in database for 'reject' intent, using fallback")
                no_patterns = set(cls.FALLBACK_NO)

            return yes_patterns, no_patterns

        except Exception as e:
            logger.error(f"Error loading confirmation patterns: {e}", exc_info=True)
            return set(cls.FALLBACK_YES), set(cls.FALLBACK_NO)


class ConfirmationMatcher:
    """
    Matches user messages against confirmation patterns.

    Single Responsibility: Pattern matching for YES/NO confirmations.
    """

    @staticmethod
    def match(
        message: str,
        yes_patterns: set[str],
        no_patterns: set[str],
    ) -> ConfirmationResult:
        """
        Match user message against YES/NO patterns.

        Handles messages like:
        - "Sí, pagar" → yes (first word "sí" normalized to "si")
        - "ok!" → yes (exact match after cleanup)
        - "no gracias" → no (first word "no")

        Uses accent normalization for consistent matching:
        - "sí" matches "si" pattern
        - "Sí, pagar" first word "sí" → normalized "si" matches "si" pattern

        Args:
            message: User message (may have accents)
            yes_patterns: Set of YES patterns
            no_patterns: Set of NO patterns

        Returns:
            ConfirmationResult with match result
        """
        message_lower = message.strip().lower()
        message_normalized = _normalize_text(message)

        # Normalize patterns for comparison
        yes_normalized = {_normalize_text(p) for p in yes_patterns}
        no_normalized = {_normalize_text(p) for p in no_patterns}

        # Extract first word and remove punctuation
        first_word = message_lower.split()[0].rstrip(",.!?;:") if message_lower.strip() else ""
        first_word_normalized = _normalize_text(first_word)

        logger.debug(
            f"[CONFIRMATION_MATCHER] message='{message}', first_word='{first_word}', "
            f"normalized='{first_word_normalized}', yes_patterns={yes_normalized}"
        )

        # Check for YES - exact match OR first word matches (with normalization)
        if message_normalized in yes_normalized:
            return ConfirmationResult(result="yes", matched_pattern=message_lower)
        if first_word_normalized in yes_normalized:
            return ConfirmationResult(result="yes", matched_pattern=first_word)

        # Check for NO - exact match OR first word matches (with normalization)
        if message_normalized in no_normalized:
            return ConfirmationResult(result="no", matched_pattern=message_lower)
        if first_word_normalized in no_normalized:
            return ConfirmationResult(result="no", matched_pattern=first_word)

        # Unclear response
        logger.warning(
            f"[CONFIRMATION_MATCHER] No match found for '{message}' "
            f"(normalized: '{first_word_normalized}'). Available YES: {yes_normalized}"
        )
        return ConfirmationResult(result="unclear")
