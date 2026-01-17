"""create_tenant_credentials_table

Revision ID: j1d6f45g890e
Revises: i0c5e34f789d
Create Date: 2025-12-22

Creates tenant_credentials table for encrypted credential storage:
- WhatsApp Business API credentials (access_token, verify_token)
- DUX ERP API credentials (api_key)
- Plex ERP API credentials (password)

All sensitive fields are stored encrypted using pgcrypto pgp_sym_encrypt.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j1d6f45g890e"
down_revision: Union[str, Sequence[str], None] = "i0c5e34f789d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tenant_credentials table."""

    op.create_table(
        "tenant_credentials",
        # Primary key
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Foreign key to organization (unique for 1:1 relationship)
        sa.Column(
            "organization_id",
            sa.UUID(),
            nullable=False,
            comment="Organization these credentials belong to (1:1 relationship)",
        ),
        # =====================================================================
        # WhatsApp Business API Credentials
        # =====================================================================
        sa.Column(
            "whatsapp_access_token_encrypted",
            sa.Text(),
            nullable=True,
            comment="Encrypted WhatsApp Graph API access token (pgcrypto)",
        ),
        sa.Column(
            "whatsapp_phone_number_id",
            sa.String(50),
            nullable=True,
            comment="WhatsApp Business phone number ID (not sensitive)",
        ),
        sa.Column(
            "whatsapp_verify_token_encrypted",
            sa.Text(),
            nullable=True,
            comment="Encrypted webhook verification token (pgcrypto)",
        ),
        # =====================================================================
        # DUX ERP API Credentials
        # =====================================================================
        sa.Column(
            "dux_api_key_encrypted",
            sa.Text(),
            nullable=True,
            comment="Encrypted DUX ERP API key (pgcrypto)",
        ),
        sa.Column(
            "dux_api_base_url",
            sa.String(255),
            nullable=True,
            comment="DUX API base URL (not sensitive)",
        ),
        # =====================================================================
        # Plex ERP API Credentials
        # =====================================================================
        sa.Column(
            "plex_api_url",
            sa.String(255),
            nullable=True,
            comment="Plex ERP API URL (not sensitive)",
        ),
        sa.Column(
            "plex_api_user",
            sa.String(100),
            nullable=True,
            comment="Plex ERP username (not sensitive)",
        ),
        sa.Column(
            "plex_api_pass_encrypted",
            sa.Text(),
            nullable=True,
            comment="Encrypted Plex ERP password (pgcrypto)",
        ),
        # =====================================================================
        # Timestamps
        # =====================================================================
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("organization_id", name="uq_tenant_credentials_org"),
        schema="core",
    )

    # Create index for organization lookup
    op.create_index(
        "idx_tenant_credentials_org_id",
        "tenant_credentials",
        ["organization_id"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    """Drop tenant_credentials table."""
    op.drop_index(
        "idx_tenant_credentials_org_id",
        table_name="tenant_credentials",
        schema="core",
    )
    op.drop_table("tenant_credentials", schema="core")
