"""Unify intent pattern tables (multi-tenant + multi-domain)

Revision ID: aa8i3j45k678l
Revises: z7h2i34j567k
Create Date: 2025-01-09

Refactors pharmacy intent pattern tables into a unified structure:
- domain_intents: Replaces pharmacy_intents with multi-domain support
- intent_patterns: Unified pattern storage (replaces lemmas, phrases, confirmation, keywords)

Migration path:
- pharmacy_intents -> domain_intents
- pharmacy_intent_lemmas -> intent_patterns (pattern_type='lemma')
- pharmacy_intent_phrases -> intent_patterns (pattern_type='phrase')
- pharmacy_confirmation_patterns -> intent_patterns (pattern_type='confirmation')
- pharmacy_keyword_patterns -> intent_patterns (pattern_type='keyword')

NOTE: Old tables are NOT dropped in this migration for safety.
      Run aa8i3j45k678m_drop_legacy_pharmacy_intent_tables.py after validation.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "aa8i3j45k678l"
down_revision = "j6k7l89m012n"  # Updated to current head
branch_labels = None
depends_on = None

SCHEMA = "core"


def upgrade() -> None:
    """Create unified domain_intents and intent_patterns tables, migrate data."""

    # =========================================================================
    # Step 1: Create domain_intents table
    # =========================================================================
    op.create_table(
        "domain_intents",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique intent identifier",
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            comment="Organization that owns this intent",
        ),
        sa.Column(
            "domain_key",
            sa.String(50),
            nullable=False,
            comment="Domain: pharmacy, excelencia, ecommerce, healthcare, etc.",
        ),
        sa.Column(
            "intent_key",
            sa.String(100),
            nullable=False,
            comment="Unique intent key within org+domain",
        ),
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
            comment="If True, requires exact phrase match",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether intent is active for detection",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("50"),
            comment="Evaluation order (100 = first, 0 = last)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=SCHEMA,
    )

    # Unique constraint: one intent_key per org+domain
    op.create_unique_constraint(
        "uq_domain_intents_org_domain_key",
        "domain_intents",
        ["organization_id", "domain_key", "intent_key"],
        schema=SCHEMA,
    )

    # Indexes for common queries
    op.create_index(
        "idx_domain_intents_org",
        "domain_intents",
        ["organization_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_domain_intents_domain",
        "domain_intents",
        ["domain_key"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_domain_intents_org_domain",
        "domain_intents",
        ["organization_id", "domain_key"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_domain_intents_enabled",
        "domain_intents",
        ["organization_id", "domain_key", "is_enabled"],
        schema=SCHEMA,
    )

    # =========================================================================
    # Step 2: Create intent_patterns table
    # =========================================================================
    op.create_table(
        "intent_patterns",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique pattern identifier",
        ),
        sa.Column(
            "intent_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.domain_intents.id", ondelete="CASCADE"),
            nullable=False,
            comment="Parent intent",
        ),
        sa.Column(
            "pattern_type",
            sa.String(20),
            nullable=False,
            comment="Pattern type: lemma, phrase, confirmation, keyword",
        ),
        sa.Column(
            "pattern_value",
            sa.String(500),
            nullable=False,
            comment="The pattern string to match",
        ),
        sa.Column(
            "match_type",
            sa.String(20),
            nullable=True,
            comment="Match strategy: exact, contains, prefix (NULL for lemmas/keywords)",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Pattern priority within type",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=SCHEMA,
    )

    # Unique constraint: no duplicate patterns per intent+type
    op.create_unique_constraint(
        "uq_intent_patterns_intent_type_value",
        "intent_patterns",
        ["intent_id", "pattern_type", "pattern_value"],
        schema=SCHEMA,
    )

    # Indexes
    op.create_index(
        "idx_intent_patterns_intent",
        "intent_patterns",
        ["intent_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_intent_patterns_type",
        "intent_patterns",
        ["intent_id", "pattern_type"],
        schema=SCHEMA,
    )

    # =========================================================================
    # Step 3: Migrate data from pharmacy_intents to domain_intents
    # =========================================================================
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.domain_intents (
            id, organization_id, domain_key, intent_key, name, description,
            weight, exact_match, is_enabled, priority, created_at, updated_at
        )
        SELECT
            id, organization_id, domain_key, intent_key, name, description,
            weight, exact_match, is_enabled, priority, created_at, updated_at
        FROM {SCHEMA}.pharmacy_intents
        """
    )

    # =========================================================================
    # Step 4: Migrate pharmacy_intent_lemmas -> intent_patterns (type='lemma')
    # =========================================================================
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.intent_patterns (
            intent_id, pattern_type, pattern_value, match_type, priority
        )
        SELECT
            intent_id,
            'lemma',
            lemma,
            NULL,
            0
        FROM {SCHEMA}.pharmacy_intent_lemmas
        """
    )

    # =========================================================================
    # Step 5: Migrate pharmacy_intent_phrases -> intent_patterns (type='phrase')
    # =========================================================================
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.intent_patterns (
            intent_id, pattern_type, pattern_value, match_type, priority
        )
        SELECT
            intent_id,
            'phrase',
            phrase,
            match_type,
            0
        FROM {SCHEMA}.pharmacy_intent_phrases
        """
    )

    # =========================================================================
    # Step 6: Migrate pharmacy_confirmation_patterns -> intent_patterns (type='confirmation')
    # =========================================================================
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.intent_patterns (
            intent_id, pattern_type, pattern_value, match_type, priority
        )
        SELECT
            intent_id,
            'confirmation',
            pattern,
            pattern_type,
            0
        FROM {SCHEMA}.pharmacy_confirmation_patterns
        """
    )

    # =========================================================================
    # Step 7: Migrate pharmacy_keyword_patterns -> intent_patterns (type='keyword')
    # =========================================================================
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.intent_patterns (
            intent_id, pattern_type, pattern_value, match_type, priority
        )
        SELECT
            intent_id,
            'keyword',
            keyword,
            NULL,
            priority
        FROM {SCHEMA}.pharmacy_keyword_patterns
        """
    )

    # Log migration stats
    op.execute(
        """
        DO $$
        DECLARE
            intent_count INTEGER;
            pattern_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO intent_count FROM core.domain_intents;
            SELECT COUNT(*) INTO pattern_count FROM core.intent_patterns;
            RAISE NOTICE 'Migration complete: % intents, % patterns migrated',
                intent_count, pattern_count;
        END $$;
        """
    )


def downgrade() -> None:
    """Remove unified tables (data is still in legacy tables)."""

    # Drop intent_patterns first (has FK to domain_intents)
    op.drop_index("idx_intent_patterns_type", table_name="intent_patterns", schema=SCHEMA)
    op.drop_index("idx_intent_patterns_intent", table_name="intent_patterns", schema=SCHEMA)
    op.drop_constraint(
        "uq_intent_patterns_intent_type_value",
        "intent_patterns",
        schema=SCHEMA,
        type_="unique",
    )
    op.drop_table("intent_patterns", schema=SCHEMA)

    # Drop domain_intents
    op.drop_index("idx_domain_intents_enabled", table_name="domain_intents", schema=SCHEMA)
    op.drop_index("idx_domain_intents_org_domain", table_name="domain_intents", schema=SCHEMA)
    op.drop_index("idx_domain_intents_domain", table_name="domain_intents", schema=SCHEMA)
    op.drop_index("idx_domain_intents_org", table_name="domain_intents", schema=SCHEMA)
    op.drop_constraint(
        "uq_domain_intents_org_domain_key",
        "domain_intents",
        schema=SCHEMA,
        type_="unique",
    )
    op.drop_table("domain_intents", schema=SCHEMA)
