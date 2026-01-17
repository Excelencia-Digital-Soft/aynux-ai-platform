"""Drop legacy pharmacy intent tables

Revision ID: cc0k5l67m890n
Revises: df60b7014e72
Create Date: 2025-01-09

Removes the 5 legacy pharmacy-specific intent tables that have been
replaced by the unified domain_intents table with JSONB columns:
- pharmacy_intents (main table)
- pharmacy_intent_lemmas
- pharmacy_intent_phrases
- pharmacy_confirmation_patterns
- pharmacy_keyword_patterns

The domain_intents table now stores all patterns as JSONB columns,
eliminating the need for separate pattern tables and JOINs.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "cc0k5l67m890n"
down_revision = "df60b7014e72"
branch_labels = None
depends_on = None

SCHEMA = "core"


def upgrade() -> None:
    """Drop legacy pharmacy intent tables."""

    # Drop child tables first (foreign key dependencies)
    op.drop_table("pharmacy_keyword_patterns", schema=SCHEMA)
    op.drop_table("pharmacy_confirmation_patterns", schema=SCHEMA)
    op.drop_table("pharmacy_intent_phrases", schema=SCHEMA)
    op.drop_table("pharmacy_intent_lemmas", schema=SCHEMA)

    # Drop parent table last
    op.drop_table("pharmacy_intents", schema=SCHEMA)

    # Log completion
    op.execute("""
        DO $$
        BEGIN
            RAISE NOTICE 'Legacy pharmacy intent tables dropped successfully';
        END $$;
    """)


def downgrade() -> None:
    """Recreate legacy pharmacy intent tables (for rollback only)."""

    # Recreate pharmacy_intents (parent table) first
    op.create_table(
        "pharmacy_intents",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("intent_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weight", sa.Numeric(3, 2), nullable=False, server_default=sa.text("1.0")),
        sa.Column("exact_match", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("50")),
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

    op.create_index(
        "idx_pharmacy_intents_org",
        "pharmacy_intents",
        ["organization_id"],
        schema=SCHEMA,
    )

    op.create_unique_constraint(
        "uq_pharmacy_intents_org_key",
        "pharmacy_intents",
        ["organization_id", "intent_key"],
        schema=SCHEMA,
    )

    # Recreate pharmacy_intent_lemmas
    op.create_table(
        "pharmacy_intent_lemmas",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "intent_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.pharmacy_intents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lemma", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "idx_pharmacy_intent_lemmas_intent",
        "pharmacy_intent_lemmas",
        ["intent_id"],
        schema=SCHEMA,
    )

    # Recreate pharmacy_intent_phrases
    op.create_table(
        "pharmacy_intent_phrases",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "intent_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.pharmacy_intents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phrase", sa.String(500), nullable=False),
        sa.Column("match_type", sa.String(20), nullable=False, server_default=sa.text("'contains'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "idx_pharmacy_intent_phrases_intent",
        "pharmacy_intent_phrases",
        ["intent_id"],
        schema=SCHEMA,
    )

    # Recreate pharmacy_confirmation_patterns
    op.create_table(
        "pharmacy_confirmation_patterns",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "intent_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.pharmacy_intents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pattern", sa.String(100), nullable=False),
        sa.Column("pattern_type", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "idx_pharmacy_confirmation_patterns_intent",
        "pharmacy_confirmation_patterns",
        ["intent_id"],
        schema=SCHEMA,
    )

    # Recreate pharmacy_keyword_patterns
    op.create_table(
        "pharmacy_keyword_patterns",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "intent_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.pharmacy_intents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(100), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "idx_pharmacy_keyword_patterns_intent",
        "pharmacy_keyword_patterns",
        ["intent_id"],
        schema=SCHEMA,
    )
