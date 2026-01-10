# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Unified intent patterns in a single table with JSONB columns
#              (pharmacy, excelencia, ecommerce, healthcare, etc.)
# Tenant-Aware: Yes - each organization has isolated patterns per domain.
# ============================================================================
"""
Domain Intent Patterns - Single-table model for multi-domain intent detection.

This module provides a unified structure for intent management where all patterns
(lemmas, phrases, confirmation_patterns, keywords) are stored as JSONB columns
in a single table, eliminating the need for JOINs.

Structure:
- domain_intents: Single table containing intent metadata + all patterns as JSONB

Pattern Storage:
- lemmas: JSONB array of strings ["deuda", "pagar", ...]
- phrases: JSONB array of {phrase, match_type} objects
- confirmation_patterns: JSONB array of {pattern, pattern_type} objects
- keywords: JSONB array of strings ["urgente", ...]

Migration History:
- pharmacy_intents + 4 pattern tables → domain_intents + intent_patterns (v1)
- domain_intents + intent_patterns → domain_intents with JSONB (v2, current)
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA

if TYPE_CHECKING:
    from .tenancy.organization import Organization


class DomainIntent(Base, TimestampMixin):
    """
    Intent definition for any domain with embedded patterns.

    Each intent represents a user intention (e.g., debt_query, confirm, reject)
    with all associated patterns stored as JSONB columns for efficient retrieval.

    Attributes:
        id: Unique identifier
        organization_id: Tenant that owns this intent
        domain_key: Domain scope (pharmacy, excelencia, ecommerce, etc.)
        intent_key: Unique intent identifier within org+domain (e.g., "debt_query")
        name: Human-readable name
        description: Intent description
        weight: Scoring weight (1.0 default, higher = more priority)
        exact_match: If True, requires exact phrase match
        is_enabled: Whether intent is active
        priority: Evaluation order (higher = first)
        lemmas: JSONB array of lemma strings for spaCy matching
        phrases: JSONB array of {phrase, match_type} objects
        confirmation_patterns: JSONB array of {pattern, pattern_type} objects
        keywords: JSONB array of keyword strings

    Example domains:
        - pharmacy: Debt queries, confirmations, greetings
        - excelencia: Module queries, invoice requests
        - ecommerce: Product queries, cart operations
        - healthcare: Appointment booking, patient queries
    """

    __tablename__ = "domain_intents"

    # Primary identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique intent identifier",
    )

    # Multi-tenant association
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this intent",
    )

    # Domain scope - supports multiple domains
    domain_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Domain: pharmacy, excelencia, ecommerce, healthcare, etc.",
    )

    # Intent identification
    intent_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Unique intent key within org+domain (e.g., 'debt_query', 'confirm')",
    )

    # Display information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable intent name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Intent description and usage notes",
    )

    # Scoring configuration
    weight: Mapped[float] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        default=1.0,
        comment="Scoring weight multiplier (1.0 default, higher = more priority)",
    )

    exact_match: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="If True, requires exact phrase match (used for confirm/reject)",
    )

    # Status and ordering
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether intent is active for detection",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        comment="Evaluation order (100 = first, 0 = last)",
    )

    # =========================================================================
    # Pattern Storage - JSONB columns for all pattern types
    # =========================================================================

    lemmas: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Array of lemma strings for spaCy matching",
    )

    phrases: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Array of {phrase, match_type} objects",
    )

    confirmation_patterns: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Array of {pattern, pattern_type} objects",
    )

    keywords: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Array of keyword strings",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="domain_intents",
    )

    # Table configuration
    __table_args__ = (
        # Unique constraint: one intent_key per org+domain
        UniqueConstraint(
            "organization_id",
            "domain_key",
            "intent_key",
            name="uq_domain_intents_org_domain_key",
        ),
        # Indexes for common queries
        Index("idx_domain_intents_org", "organization_id"),
        Index("idx_domain_intents_domain", "domain_key"),
        Index("idx_domain_intents_org_domain", "organization_id", "domain_key"),
        Index(
            "idx_domain_intents_enabled", "organization_id", "domain_key", "is_enabled"
        ),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<DomainIntent(domain='{self.domain_key}', intent='{self.intent_key}', org={self.organization_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "domain_key": self.domain_key,
            "intent_key": self.intent_key,
            "name": self.name,
            "description": self.description,
            "weight": float(self.weight) if self.weight else 1.0,
            "exact_match": self.exact_match,
            "is_enabled": self.is_enabled,
            "priority": self.priority,
            "lemmas": self.lemmas or [],
            "phrases": self.phrases or [],
            "confirmation_patterns": self.confirmation_patterns or [],
            "keywords": self.keywords or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    # =========================================================================
    # Pattern Manipulation Methods
    # =========================================================================

    def add_lemmas(self, new_lemmas: list[str]) -> int:
        """Add lemmas to the intent. Returns count of added lemmas."""
        current = set(self.lemmas or [])
        to_add = [l.lower().strip() for l in new_lemmas if l.lower().strip() not in current]
        if to_add:
            self.lemmas = list(current | set(to_add))
        return len(to_add)

    def remove_lemmas(self, lemmas_to_remove: list[str]) -> int:
        """Remove lemmas from the intent. Returns count of removed lemmas."""
        current = set(self.lemmas or [])
        to_remove = {l.lower().strip() for l in lemmas_to_remove}
        removed = current & to_remove
        if removed:
            self.lemmas = list(current - removed)
        return len(removed)

    def add_keywords(self, new_keywords: list[str]) -> int:
        """Add keywords to the intent. Returns count of added keywords."""
        current = set(self.keywords or [])
        to_add = [k.lower().strip() for k in new_keywords if k.lower().strip() not in current]
        if to_add:
            self.keywords = list(current | set(to_add))
        return len(to_add)

    def remove_keywords(self, keywords_to_remove: list[str]) -> int:
        """Remove keywords from the intent. Returns count of removed keywords."""
        current = set(self.keywords or [])
        to_remove = {k.lower().strip() for k in keywords_to_remove}
        removed = current & to_remove
        if removed:
            self.keywords = list(current - removed)
        return len(removed)

    def add_phrases(self, new_phrases: list[dict]) -> int:
        """
        Add phrases to the intent. Each phrase is {phrase: str, match_type: str}.
        Returns count of added phrases.
        """
        current_phrases = {p["phrase"].lower() for p in (self.phrases or [])}
        to_add = []
        for p in new_phrases:
            phrase = p.get("phrase", "").lower().strip()
            if phrase and phrase not in current_phrases:
                to_add.append({
                    "phrase": phrase,
                    "match_type": p.get("match_type", "contains"),
                })
                current_phrases.add(phrase)
        if to_add:
            self.phrases = (self.phrases or []) + to_add
        return len(to_add)

    def remove_phrases(self, phrases_to_remove: list[str]) -> int:
        """Remove phrases by their phrase text. Returns count of removed phrases."""
        to_remove = {p.lower().strip() for p in phrases_to_remove}
        original_count = len(self.phrases or [])
        self.phrases = [
            p for p in (self.phrases or [])
            if p.get("phrase", "").lower() not in to_remove
        ]
        return original_count - len(self.phrases)

    def add_confirmation_patterns(self, new_patterns: list[dict]) -> int:
        """
        Add confirmation patterns. Each is {pattern: str, pattern_type: str}.
        Returns count of added patterns.
        """
        current_patterns = {p["pattern"].lower() for p in (self.confirmation_patterns or [])}
        to_add = []
        for p in new_patterns:
            pattern = p.get("pattern", "").lower().strip()
            if pattern and pattern not in current_patterns:
                to_add.append({
                    "pattern": pattern,
                    "pattern_type": p.get("pattern_type", "exact"),
                })
                current_patterns.add(pattern)
        if to_add:
            self.confirmation_patterns = (self.confirmation_patterns or []) + to_add
        return len(to_add)

    def remove_confirmation_patterns(self, patterns_to_remove: list[str]) -> int:
        """Remove confirmation patterns by pattern text. Returns count removed."""
        to_remove = {p.lower().strip() for p in patterns_to_remove}
        original_count = len(self.confirmation_patterns or [])
        self.confirmation_patterns = [
            p for p in (self.confirmation_patterns or [])
            if p.get("pattern", "").lower() not in to_remove
        ]
        return original_count - len(self.confirmation_patterns)


# Backward compatibility alias (deprecated)
PharmacyIntent = DomainIntent
