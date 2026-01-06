# ============================================================================
# Migration: Rename message_url to base_url in chattigo_credentials
# Description: Updates column name to reflect new WhatsApp Cloud API format
#              where DID is added as path parameter: /v15.0/{did}/messages
# ============================================================================
"""rename message_url to base_url

Revision ID: b9j4k56m789n
Revises: a8i3j45k678l
Create Date: 2026-01-06

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9j4k56m789n"
down_revision: str | None = "a8i3j45k678l"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename message_url column to base_url and update existing values."""
    # Rename column
    op.alter_column(
        "chattigo_credentials",
        "message_url",
        new_column_name="base_url",
        schema="core",
    )

    # Update existing URLs: remove /webhooks/inbound suffix
    # Old format: https://channels.chattigo.com/bsp-cloud-chattigo-isv/webhooks/inbound
    # New format: https://channels.chattigo.com/bsp-cloud-chattigo-isv
    op.execute("""
        UPDATE core.chattigo_credentials
        SET base_url = 'https://channels.chattigo.com/bsp-cloud-chattigo-isv'
        WHERE base_url LIKE '%/webhooks/inbound'
    """)

    # Update column default
    op.execute("""
        ALTER TABLE core.chattigo_credentials
        ALTER COLUMN base_url SET DEFAULT 'https://channels.chattigo.com/bsp-cloud-chattigo-isv'
    """)


def downgrade() -> None:
    """Rename base_url column back to message_url and restore old values."""
    # Rename column back
    op.alter_column(
        "chattigo_credentials",
        "base_url",
        new_column_name="message_url",
        schema="core",
    )

    # Restore old URL format by appending /webhooks/inbound
    op.execute("""
        UPDATE core.chattigo_credentials
        SET message_url = message_url || '/webhooks/inbound'
        WHERE message_url NOT LIKE '%/webhooks/inbound'
    """)
