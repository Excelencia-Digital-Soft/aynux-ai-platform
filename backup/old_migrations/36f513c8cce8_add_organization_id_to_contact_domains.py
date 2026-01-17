"""add_organization_id_to_contact_domains

Revision ID: 36f513c8cce8
Revises: s0m5n34o789n
Create Date: 2025-12-29 15:32:13.167001

Adds organization_id column to contact_domains table for multi-tenant support.
This column allows mapping contacts to specific organizations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '36f513c8cce8'
down_revision: Union[str, Sequence[str], None] = 's0m5n34o789n'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add organization_id column to contact_domains for multi-tenant support."""
    # Add column if it doesn't exist (idempotent)
    op.execute("""
        ALTER TABLE core.contact_domains
        ADD COLUMN IF NOT EXISTS organization_id UUID
    """)

    # Create index for multi-tenant lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_contact_domains_org_id
        ON core.contact_domains(organization_id)
    """)


def downgrade() -> None:
    """Remove organization_id column from contact_domains."""
    op.execute("DROP INDEX IF EXISTS core.idx_contact_domains_org_id")
    op.execute("ALTER TABLE core.contact_domains DROP COLUMN IF EXISTS organization_id")
