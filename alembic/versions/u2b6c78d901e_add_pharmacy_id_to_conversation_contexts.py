"""add_pharmacy_id_to_conversation_contexts

Revision ID: u2b6c78d901e
Revises: t1a5b67c890d
Create Date: 2025-12-29

Adds pharmacy_id column to conversation_contexts table to enable
filtering conversations by specific pharmacy (not just organization).
This is needed because an organization can have multiple pharmacies.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "u2b6c78d901e"
down_revision: Union[str, Sequence[str], None] = "t1a5b67c890d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pharmacy_id column to conversation_contexts."""
    op.add_column(
        "conversation_contexts",
        sa.Column(
            "pharmacy_id",
            sa.UUID(as_uuid=True),
            nullable=True,
            comment="Pharmacy that owns this conversation (for multi-pharmacy orgs)",
        ),
        schema="core",
    )
    op.create_index(
        "ix_conversation_contexts_pharmacy_id",
        "conversation_contexts",
        ["pharmacy_id"],
        schema="core",
    )


def downgrade() -> None:
    """Remove pharmacy_id column from conversation_contexts."""
    op.drop_index(
        "ix_conversation_contexts_pharmacy_id",
        table_name="conversation_contexts",
        schema="core",
    )
    op.drop_column("conversation_contexts", "pharmacy_id", schema="core")
