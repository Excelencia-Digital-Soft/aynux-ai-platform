"""add_embedding_updated_at_column

Adds embedding_updated_at column to agent_knowledge table for tracking
when embeddings were last generated, enabling staleness detection.

Revision ID: n5h0j89k234i
Revises: m4g9i78j123h
Create Date: 2024-12-26 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n5h0j89k234i"
down_revision: Union[str, Sequence[str], None] = "m4g9i78j123h"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add embedding_updated_at column and backfill existing data."""
    # Add embedding_updated_at column
    op.add_column(
        "agent_knowledge",
        sa.Column(
            "embedding_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when embedding was last generated/updated",
        ),
        schema="core",
    )

    # Backfill: Set embedding_updated_at = updated_at for existing documents with embeddings
    # This marks existing embeddings as "fresh" initially
    op.execute(
        """
        UPDATE core.agent_knowledge
        SET embedding_updated_at = updated_at
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    """Remove embedding_updated_at column."""
    op.drop_column("agent_knowledge", "embedding_updated_at", schema="core")
