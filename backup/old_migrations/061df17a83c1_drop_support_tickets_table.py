"""drop_support_tickets_table

Revision ID: 061df17a83c1
Revises: z7h2i34j567k
Create Date: 2026-01-08 22:23:52.129218

Removes legacy core.support_tickets table and its ENUMs.
Support is now handled by soporte.incidents table.

NOTE: The document_type_enum values (support_faq, support_guide, etc.)
added in f54b041d903d are KEPT as they're still used for knowledge documents.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "061df17a83c1"
down_revision: Union[str, Sequence[str], None] = "h4i5j67k890l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop support_tickets table and its ENUMs."""
    # 1. Drop indexes first
    op.drop_index(
        "idx_ticket_created_at", table_name="support_tickets", schema="core"
    )
    op.drop_index(
        "idx_ticket_priority", table_name="support_tickets", schema="core"
    )
    op.drop_index(
        "idx_ticket_type", table_name="support_tickets", schema="core"
    )
    op.drop_index(
        "idx_ticket_user_phone", table_name="support_tickets", schema="core"
    )
    op.drop_index(
        "idx_ticket_status", table_name="support_tickets", schema="core"
    )

    # 2. Drop the table
    op.drop_table("support_tickets", schema="core")

    # 3. Drop the ENUMs (in the public schema)
    op.execute("DROP TYPE IF EXISTS ticket_priority_enum")
    op.execute("DROP TYPE IF EXISTS ticket_status_enum")
    op.execute("DROP TYPE IF EXISTS ticket_type_enum")


def downgrade() -> None:
    """
    Rollback not implemented - this is a one-way migration.

    Data should have been migrated to soporte.incidents before this migration.
    If rollback is needed, restore from backup.
    """
    pass
