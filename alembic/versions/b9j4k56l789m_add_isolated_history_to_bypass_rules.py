"""Add isolated_history column to bypass_rules

Revision ID: b9j4k56l789m
Revises: c9l5n67o890p
Create Date: 2026-01-06

Adds isolated_history field to bypass_rules table that enables separate
conversation history for agents routed via bypass rules. When enabled,
creates isolated conversation context using rule_id suffix.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b9j4k56l789m"
down_revision = "c9l5n67o890p"
branch_labels = None
depends_on = None

SCHEMA = "core"
TABLE = "bypass_rules"


def upgrade() -> None:
    """Add isolated_history column to bypass_rules."""
    op.add_column(
        TABLE,
        sa.Column(
            "isolated_history",
            sa.Boolean(),
            nullable=True,  # Nullable to not affect existing records
            default=None,
            comment="When true, creates isolated conversation history for this rule's flow",
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Remove isolated_history column from bypass_rules."""
    op.drop_column(TABLE, "isolated_history", schema=SCHEMA)
