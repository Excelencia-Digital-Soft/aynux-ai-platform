"""Create pharmacy intent patterns tables.

Revision ID: h4i5j67k890l
Revises: g3h4i56j789k
Create Date: 2026-01-08

Creates tables for configurable pharmacy intent patterns:
- pharmacy_intents: Main intent definitions (debt_query, confirm, reject, etc.)
- pharmacy_intent_lemmas: spaCy lemma patterns
- pharmacy_intent_phrases: Complete phrase patterns
- pharmacy_confirmation_patterns: Yes/no confirmation patterns
- pharmacy_keyword_patterns: Fallback keyword patterns

Multi-tenant: Each organization can customize their own patterns.
No fallback: Patterns must be in database for intent detection to work.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h4i5j67k890l"
down_revision: Union[str, Sequence[str], None] = "g3h4i56j789k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pharmacy intent patterns tables."""

    # ==========================================================================
    # 1. Clean up any leftover artifacts from failed migrations
    # ==========================================================================
    op.execute("DROP TABLE IF EXISTS core.pharmacy_keyword_patterns CASCADE")
    op.execute("DROP TABLE IF EXISTS core.pharmacy_confirmation_patterns CASCADE")
    op.execute("DROP TABLE IF EXISTS core.pharmacy_intent_phrases CASCADE")
    op.execute("DROP TABLE IF EXISTS core.pharmacy_intent_lemmas CASCADE")
    op.execute("DROP TABLE IF EXISTS core.pharmacy_intents CASCADE")

    # ==========================================================================
    # 2. Create pharmacy_intents table (main intent definitions)
    # ==========================================================================
    op.create_table(
        "pharmacy_intents",
        # Primary key
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique intent identifier",
        ),
        # Multi-tenant association
        sa.Column(
            "organization_id",
            UUID(),
            nullable=False,
            comment="Organization that owns this intent",
        ),
        # Domain scope
        sa.Column(
            "domain_key",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'pharmacy'"),
            comment="Domain: pharmacy (expandable)",
        ),
        # Intent identification
        sa.Column(
            "intent_key",
            sa.String(100),
            nullable=False,
            comment="Unique intent key (e.g., 'debt_query', 'confirm')",
        ),
        # Display information
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Human-readable intent name",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Intent description and usage notes",
        ),
        # Scoring configuration
        sa.Column(
            "weight",
            sa.Numeric(3, 2),
            nullable=False,
            server_default=sa.text("1.0"),
            comment="Scoring weight multiplier",
        ),
        sa.Column(
            "exact_match",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="If true, requires exact phrase match",
        ),
        # Status and ordering
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether intent is active",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("50"),
            comment="Evaluation order (100 = first)",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "domain_key",
            "intent_key",
            name="uq_pharmacy_intents_org_domain_key",
        ),
        schema="core",
    )

    # Create indexes for pharmacy_intents
    op.create_index(
        "idx_pharmacy_intents_org",
        "pharmacy_intents",
        ["organization_id"],
        schema="core",
    )
    op.create_index(
        "idx_pharmacy_intents_domain",
        "pharmacy_intents",
        ["domain_key"],
        schema="core",
    )
    op.create_index(
        "idx_pharmacy_intents_enabled",
        "pharmacy_intents",
        ["organization_id", "is_enabled"],
        schema="core",
    )
    op.create_index(
        "idx_pharmacy_intents_org_domain",
        "pharmacy_intents",
        ["organization_id", "domain_key"],
        schema="core",
    )

    # ==========================================================================
    # 3. Create pharmacy_intent_lemmas table (spaCy lemma patterns)
    # ==========================================================================
    op.create_table(
        "pharmacy_intent_lemmas",
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique lemma entry identifier",
        ),
        sa.Column(
            "intent_id",
            UUID(),
            nullable=False,
            comment="Parent intent",
        ),
        sa.Column(
            "lemma",
            sa.String(100),
            nullable=False,
            comment="Word root (e.g., 'deuda', 'pagar')",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["core.pharmacy_intents.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "intent_id",
            "lemma",
            name="uq_pharmacy_lemmas_intent_lemma",
        ),
        schema="core",
    )

    op.create_index(
        "idx_pharmacy_lemmas_intent",
        "pharmacy_intent_lemmas",
        ["intent_id"],
        schema="core",
    )

    # ==========================================================================
    # 4. Create pharmacy_intent_phrases table (complete phrase patterns)
    # ==========================================================================
    op.create_table(
        "pharmacy_intent_phrases",
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique phrase entry identifier",
        ),
        sa.Column(
            "intent_id",
            UUID(),
            nullable=False,
            comment="Parent intent",
        ),
        sa.Column(
            "phrase",
            sa.String(500),
            nullable=False,
            comment="Complete phrase to match",
        ),
        sa.Column(
            "match_type",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'contains'"),
            comment="Match strategy: exact, contains, prefix",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["core.pharmacy_intents.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "intent_id",
            "phrase",
            name="uq_pharmacy_phrases_intent_phrase",
        ),
        schema="core",
    )

    op.create_index(
        "idx_pharmacy_phrases_intent",
        "pharmacy_intent_phrases",
        ["intent_id"],
        schema="core",
    )

    # ==========================================================================
    # 5. Create pharmacy_confirmation_patterns table (yes/no patterns)
    # ==========================================================================
    op.create_table(
        "pharmacy_confirmation_patterns",
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique pattern entry identifier",
        ),
        sa.Column(
            "intent_id",
            UUID(),
            nullable=False,
            comment="Parent intent (confirm or reject)",
        ),
        sa.Column(
            "pattern",
            sa.String(100),
            nullable=False,
            comment="Pattern to match (e.g., 'si', 'confirmo')",
        ),
        sa.Column(
            "pattern_type",
            sa.String(20),
            nullable=False,
            comment="Match type: exact or contains",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["core.pharmacy_intents.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "intent_id",
            "pattern",
            "pattern_type",
            name="uq_pharmacy_confirmation_pattern",
        ),
        schema="core",
    )

    op.create_index(
        "idx_pharmacy_confirmation_intent",
        "pharmacy_confirmation_patterns",
        ["intent_id"],
        schema="core",
    )

    # ==========================================================================
    # 6. Create pharmacy_keyword_patterns table (fallback keywords)
    # ==========================================================================
    op.create_table(
        "pharmacy_keyword_patterns",
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique keyword entry identifier",
        ),
        sa.Column(
            "intent_id",
            UUID(),
            nullable=False,
            comment="Parent intent",
        ),
        sa.Column(
            "keyword",
            sa.String(200),
            nullable=False,
            comment="Keyword to match in message",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Keyword priority (higher = first)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["core.pharmacy_intents.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "intent_id",
            "keyword",
            name="uq_pharmacy_keywords_intent_keyword",
        ),
        schema="core",
    )

    op.create_index(
        "idx_pharmacy_keywords_intent",
        "pharmacy_keyword_patterns",
        ["intent_id"],
        schema="core",
    )

    # ==========================================================================
    # 7. Add table comments
    # ==========================================================================
    op.execute("""
        COMMENT ON TABLE core.pharmacy_intents IS
        'Intent definitions for pharmacy domain. Multi-tenant: each organization can customize patterns.'
    """)
    op.execute("""
        COMMENT ON TABLE core.pharmacy_intent_lemmas IS
        'spaCy lemma patterns for intent matching. Lemmas are word roots extracted by spaCy.'
    """)
    op.execute("""
        COMMENT ON TABLE core.pharmacy_intent_phrases IS
        'Complete phrase patterns for intent matching. Supports exact, contains, and prefix matching.'
    """)
    op.execute("""
        COMMENT ON TABLE core.pharmacy_confirmation_patterns IS
        'Yes/No confirmation patterns for confirm/reject intents. High priority in detection.'
    """)
    op.execute("""
        COMMENT ON TABLE core.pharmacy_keyword_patterns IS
        'Fallback keyword patterns when spaCy is unavailable. Simple substring matching.'
    """)


def downgrade() -> None:
    """Remove pharmacy intent patterns tables."""

    # Drop indexes and tables in reverse order (child tables first)
    op.drop_index(
        "idx_pharmacy_keywords_intent",
        table_name="pharmacy_keyword_patterns",
        schema="core",
    )
    op.drop_table("pharmacy_keyword_patterns", schema="core")

    op.drop_index(
        "idx_pharmacy_confirmation_intent",
        table_name="pharmacy_confirmation_patterns",
        schema="core",
    )
    op.drop_table("pharmacy_confirmation_patterns", schema="core")

    op.drop_index(
        "idx_pharmacy_phrases_intent",
        table_name="pharmacy_intent_phrases",
        schema="core",
    )
    op.drop_table("pharmacy_intent_phrases", schema="core")

    op.drop_index(
        "idx_pharmacy_lemmas_intent",
        table_name="pharmacy_intent_lemmas",
        schema="core",
    )
    op.drop_table("pharmacy_intent_lemmas", schema="core")

    op.drop_index(
        "idx_pharmacy_intents_org_domain",
        table_name="pharmacy_intents",
        schema="core",
    )
    op.drop_index(
        "idx_pharmacy_intents_enabled",
        table_name="pharmacy_intents",
        schema="core",
    )
    op.drop_index(
        "idx_pharmacy_intents_domain",
        table_name="pharmacy_intents",
        schema="core",
    )
    op.drop_index(
        "idx_pharmacy_intents_org",
        table_name="pharmacy_intents",
        schema="core",
    )
    op.drop_table("pharmacy_intents", schema="core")
