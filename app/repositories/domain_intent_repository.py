# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Repository for unified domain intent patterns with JSONB storage.
#              All patterns stored in domain_intents table as JSONB columns.
# Tenant-Aware: Yes - each organization has isolated patterns per domain.
# ============================================================================
"""
Domain Intent Repository - Data persistence layer for unified intent patterns.

Single-table design with JSONB columns for patterns:
- DomainIntent.lemmas: JSONB array of strings
- DomainIntent.phrases: JSONB array of {phrase, match_type}
- DomainIntent.confirmation_patterns: JSONB array of {pattern, pattern_type}
- DomainIntent.keywords: JSONB array of strings

Follows Single Responsibility Principle - only handles data persistence.

Usage:
    repository = DomainIntentRepository(db)
    patterns = await repository.get_all_patterns_structured(org_id, "pharmacy")
    intent = await repository.create_intent(org_id, "pharmacy", data)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.domain_intents import DomainIntent

logger = logging.getLogger(__name__)


class DomainIntentRepository:
    """
    Async repository for unified domain intent pattern persistence.

    Single Responsibility: Data access layer for domain_intents with JSONB patterns.
    Multi-tenant: All operations require organization_id.
    Multi-domain: All operations require domain_key.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with async database session.

        Args:
            db: SQLAlchemy async session
        """
        self._db = db

    # =========================================================================
    # Optimized Pattern Loading (for cache)
    # =========================================================================

    async def get_all_patterns_structured(
        self,
        organization_id: UUID,
        domain_key: str,
    ) -> dict[str, Any]:
        """
        Get all patterns in the structure expected by IntentAnalyzer.

        Single query - no JOINs needed since patterns are JSONB columns.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope (e.g., "pharmacy", "excelencia")

        Returns:
            Dict with:
            - intents: {intent_key: {lemmas, phrases, weight, exact_match}}
            - confirmation_patterns: {intent_key: {exact: set, contains: set}}
            - keyword_patterns: {intent_key: [keywords]}
            - greeting_patterns: {exact: set, prefixes: list}
            - valid_intents: set of all intent keys
        """
        # Load all enabled intents (patterns are JSONB columns, no JOINs)
        stmt = (
            select(DomainIntent)
            .where(DomainIntent.organization_id == organization_id)
            .where(DomainIntent.domain_key == domain_key)
            .where(DomainIntent.is_enabled == True)  # noqa: E712
            .order_by(DomainIntent.priority.desc())
        )

        result = await self._db.execute(stmt)
        intents = list(result.scalars().all())

        # Build structured response
        patterns: dict[str, Any] = {
            "intents": {},
            "confirmation_patterns": {},
            "keyword_patterns": {},
            "greeting_patterns": {"exact": set(), "prefixes": []},
            "valid_intents": set(),
        }

        for intent in intents:
            intent_key = intent.intent_key
            patterns["valid_intents"].add(intent_key)

            # Get patterns directly from JSONB columns
            lemmas = intent.lemmas or []
            phrases = intent.phrases or []
            confirmation = intent.confirmation_patterns or []
            keywords = intent.keywords or []

            # Build intent pattern structure
            patterns["intents"][intent_key] = {
                "lemmas": lemmas,
                "phrases": phrases,
                "weight": float(intent.weight) if intent.weight else 1.0,
                "exact_match": intent.exact_match,
            }

            # Confirmation patterns (for confirm/reject)
            if confirmation:
                exact: set[str] = set()
                contains: set[str] = set()
                for cp in confirmation:
                    if cp.get("pattern_type") == "exact":
                        exact.add(cp["pattern"])
                    else:
                        contains.add(cp["pattern"])
                patterns["confirmation_patterns"][intent_key] = {
                    "exact": exact,
                    "contains": contains,
                }

            # Keyword patterns
            if keywords:
                patterns["keyword_patterns"][intent_key] = keywords

            # Special handling for greeting intent
            if intent_key == "greeting":
                for phrase_data in phrases:
                    phrase = phrase_data.get("phrase", "")
                    match_type = phrase_data.get("match_type")
                    if match_type == "exact":
                        patterns["greeting_patterns"]["exact"].add(phrase)
                    elif match_type == "prefix":
                        patterns["greeting_patterns"]["prefixes"].append(phrase)

        logger.debug(
            f"Loaded {len(patterns['valid_intents'])} intents for org {organization_id} "
            f"domain {domain_key}"
        )
        return patterns

    # =========================================================================
    # Intent CRUD Operations
    # =========================================================================

    async def find_all_intents(
        self,
        organization_id: UUID,
        domain_key: str,
        enabled_only: bool = False,
    ) -> list[DomainIntent]:
        """Find all intents for an organization and domain.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope
            enabled_only: Only return enabled intents

        Returns:
            List of DomainIntent with embedded JSONB patterns
        """
        stmt = (
            select(DomainIntent)
            .where(DomainIntent.organization_id == organization_id)
            .where(DomainIntent.domain_key == domain_key)
        )

        if enabled_only:
            stmt = stmt.where(DomainIntent.is_enabled == True)  # noqa: E712

        stmt = stmt.order_by(DomainIntent.priority.desc(), DomainIntent.name)

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_intent_by_id(self, intent_id: UUID) -> DomainIntent | None:
        """Get intent by UUID.

        Args:
            intent_id: Intent UUID

        Returns:
            DomainIntent or None if not found
        """
        stmt = select(DomainIntent).where(DomainIntent.id == intent_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_intent_by_key(
        self,
        organization_id: UUID,
        domain_key: str,
        intent_key: str,
    ) -> DomainIntent | None:
        """Get intent by unique key within organization and domain.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope
            intent_key: Intent key (e.g., "debt_query")

        Returns:
            DomainIntent or None if not found
        """
        stmt = (
            select(DomainIntent)
            .where(DomainIntent.organization_id == organization_id)
            .where(DomainIntent.domain_key == domain_key)
            .where(DomainIntent.intent_key == intent_key)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_intent(
        self,
        organization_id: UUID,
        domain_key: str,
        data: dict[str, Any],
    ) -> DomainIntent:
        """Create a new intent with optional patterns.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope
            data: Intent data including optional JSONB patterns

        Returns:
            Created DomainIntent with generated ID
        """
        # Process phrases to ensure correct format
        phrases = []
        for phrase_data in data.get("phrases", []):
            if isinstance(phrase_data, str):
                phrases.append({"phrase": phrase_data, "match_type": "contains"})
            else:
                phrases.append({
                    "phrase": phrase_data.get("phrase", phrase_data.get("value", "")),
                    "match_type": phrase_data.get("match_type", "contains"),
                })

        # Process confirmation patterns
        confirmation_patterns = []
        for cp in data.get("confirmation_patterns", []):
            confirmation_patterns.append({
                "pattern": cp.get("pattern", cp.get("value", "")),
                "pattern_type": cp.get("pattern_type", "exact"),
            })

        intent = DomainIntent(
            organization_id=organization_id,
            domain_key=domain_key,
            intent_key=data["intent_key"],
            name=data["name"],
            description=data.get("description"),
            weight=data.get("weight", 1.0),
            exact_match=data.get("exact_match", False),
            is_enabled=data.get("is_enabled", True),
            priority=data.get("priority", 50),
            # JSONB pattern columns
            lemmas=data.get("lemmas", []),
            phrases=phrases,
            confirmation_patterns=confirmation_patterns,
            keywords=data.get("keywords", []),
        )

        self._db.add(intent)
        await self._db.commit()
        await self._db.refresh(intent)
        return intent

    async def update_intent(
        self,
        intent_id: UUID,
        data: dict[str, Any],
    ) -> DomainIntent | None:
        """Update an existing intent (base fields only, use pattern methods for patterns).

        Args:
            intent_id: Intent UUID
            data: Fields to update

        Returns:
            Updated DomainIntent or None if not found
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return None

        # Update allowed fields
        for field in ["name", "description", "weight", "exact_match", "is_enabled", "priority"]:
            if field in data:
                setattr(intent, field, data[field])

        intent.updated_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(intent)
        return intent

    async def delete_intent(self, intent_id: UUID) -> bool:
        """Delete an intent.

        Args:
            intent_id: Intent UUID

        Returns:
            True if deleted, False if not found
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return False

        await self._db.delete(intent)
        await self._db.commit()
        return True

    # =========================================================================
    # Pattern Management Operations (using model's JSONB methods)
    # =========================================================================

    async def add_lemmas(self, intent_id: UUID, lemmas: list[str]) -> int:
        """Add lemmas to an intent.

        Args:
            intent_id: Intent UUID
            lemmas: List of lemma strings

        Returns:
            Number of lemmas added
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return 0

        added = intent.add_lemmas(lemmas)
        if added > 0:
            intent.updated_at = datetime.now(UTC)
            await self._db.commit()

        return added

    async def remove_lemmas(self, intent_id: UUID, lemmas: list[str]) -> int:
        """Remove lemmas from an intent.

        Args:
            intent_id: Intent UUID
            lemmas: List of lemmas to remove

        Returns:
            Number of lemmas removed
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return 0

        removed = intent.remove_lemmas(lemmas)
        if removed > 0:
            intent.updated_at = datetime.now(UTC)
            await self._db.commit()

        return removed

    async def add_keywords(self, intent_id: UUID, keywords: list[str]) -> int:
        """Add keywords to an intent.

        Args:
            intent_id: Intent UUID
            keywords: List of keyword strings

        Returns:
            Number of keywords added
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return 0

        added = intent.add_keywords(keywords)
        if added > 0:
            intent.updated_at = datetime.now(UTC)
            await self._db.commit()

        return added

    async def remove_keywords(self, intent_id: UUID, keywords: list[str]) -> int:
        """Remove keywords from an intent.

        Args:
            intent_id: Intent UUID
            keywords: List of keywords to remove

        Returns:
            Number of keywords removed
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return 0

        removed = intent.remove_keywords(keywords)
        if removed > 0:
            intent.updated_at = datetime.now(UTC)
            await self._db.commit()

        return removed

    async def add_phrases(self, intent_id: UUID, phrases: list[dict[str, str]]) -> int:
        """Add phrases to an intent.

        Args:
            intent_id: Intent UUID
            phrases: List of {phrase, match_type} dicts

        Returns:
            Number of phrases added
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return 0

        added = intent.add_phrases(phrases)
        if added > 0:
            intent.updated_at = datetime.now(UTC)
            await self._db.commit()

        return added

    async def remove_phrases(self, intent_id: UUID, phrases: list[str]) -> int:
        """Remove phrases from an intent by phrase text.

        Args:
            intent_id: Intent UUID
            phrases: List of phrase texts to remove

        Returns:
            Number of phrases removed
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return 0

        removed = intent.remove_phrases(phrases)
        if removed > 0:
            intent.updated_at = datetime.now(UTC)
            await self._db.commit()

        return removed

    async def add_confirmation_patterns(
        self, intent_id: UUID, patterns: list[dict[str, str]]
    ) -> int:
        """Add confirmation patterns to an intent.

        Args:
            intent_id: Intent UUID
            patterns: List of {pattern, pattern_type} dicts

        Returns:
            Number of patterns added
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return 0

        added = intent.add_confirmation_patterns(patterns)
        if added > 0:
            intent.updated_at = datetime.now(UTC)
            await self._db.commit()

        return added

    async def remove_confirmation_patterns(
        self, intent_id: UUID, patterns: list[str]
    ) -> int:
        """Remove confirmation patterns by pattern text.

        Args:
            intent_id: Intent UUID
            patterns: List of pattern texts to remove

        Returns:
            Number of patterns removed
        """
        intent = await self.get_intent_by_id(intent_id)
        if not intent:
            return 0

        removed = intent.remove_confirmation_patterns(patterns)
        if removed > 0:
            intent.updated_at = datetime.now(UTC)
            await self._db.commit()

        return removed

    # =========================================================================
    # Utility Operations
    # =========================================================================

    async def intent_exists(
        self,
        organization_id: UUID,
        domain_key: str,
        intent_key: str,
    ) -> bool:
        """Check if intent exists for organization and domain.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope
            intent_key: Intent key

        Returns:
            True if exists
        """
        intent = await self.get_intent_by_key(organization_id, domain_key, intent_key)
        return intent is not None

    async def count_intents(
        self,
        organization_id: UUID,
        domain_key: str,
    ) -> int:
        """Count intents for an organization and domain.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope

        Returns:
            Number of intents
        """
        stmt = (
            select(func.count())
            .select_from(DomainIntent)
            .where(DomainIntent.organization_id == organization_id)
            .where(DomainIntent.domain_key == domain_key)
        )
        result = await self._db.execute(stmt)
        return result.scalar() or 0

    async def get_available_domains(self, organization_id: UUID) -> list[str]:
        """Get list of domains with intents for an organization.

        Args:
            organization_id: Tenant UUID

        Returns:
            List of domain keys
        """
        stmt = (
            select(DomainIntent.domain_key)
            .where(DomainIntent.organization_id == organization_id)
            .distinct()
            .order_by(DomainIntent.domain_key)
        )
        result = await self._db.execute(stmt)
        return [row[0] for row in result.all()]
