"""Add JSONB columns to domain_intents.

Revision ID: gg6h7i8j9k0l
Revises: aac255afc73b
Create Date: 2026-01-12

Adds JSONB pattern columns to domain_intents table.
This completes the v1→v2 schema migration where patterns
are stored directly in domain_intents instead of a separate
intent_patterns table.

Note: intent_patterns table is empty, no data migration needed.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "gg6h7i8j9k0l"
down_revision: Union[str, Sequence[str], None] = "aac255afc73b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "core"


def upgrade() -> None:
    """Add JSONB pattern columns to domain_intents table."""
    # Add JSONB columns for pattern storage
    op.add_column(
        "domain_intents",
        sa.Column(
            "lemmas",
            JSONB,
            server_default="[]",
            nullable=False,
            comment="Array of lemma strings for spaCy matching",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "domain_intents",
        sa.Column(
            "phrases",
            JSONB,
            server_default="[]",
            nullable=False,
            comment="Array of {phrase, match_type} objects",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "domain_intents",
        sa.Column(
            "confirmation_patterns",
            JSONB,
            server_default="[]",
            nullable=False,
            comment="Array of {pattern, pattern_type} objects",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "domain_intents",
        sa.Column(
            "keywords",
            JSONB,
            server_default="[]",
            nullable=False,
            comment="Array of keyword strings",
        ),
        schema=SCHEMA,
    )

    # Drop the unused intent_patterns table (was created by aa8i3j45k678l but never used)
    op.execute("DROP TABLE IF EXISTS core.intent_patterns")


def downgrade() -> None:
    """Remove JSONB columns from domain_intents."""
    op.drop_column("domain_intents", "keywords", schema=SCHEMA)
    op.drop_column("domain_intents", "confirmation_patterns", schema=SCHEMA)
    op.drop_column("domain_intents", "phrases", schema=SCHEMA)
    op.drop_column("domain_intents", "lemmas", schema=SCHEMA)
