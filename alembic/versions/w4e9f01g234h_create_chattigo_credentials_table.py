"""create_chattigo_credentials_table

Revision ID: w4e9f01g234h
Revises: v3d8e90f123g
Create Date: 2024-12-30

Creates chattigo_credentials table for multi-DID Chattigo ISV support:
- Each DID (WhatsApp Business number) has its own credentials
- Username/password encrypted with pgcrypto
- Configurable URLs and token refresh settings
- Optional link to bypass_rules for routing

Tokens are managed at runtime by ChattigoTokenCache, not stored in DB.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "w4e9f01g234h"
down_revision: str | None = "v3d8e90f123g"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CORE_SCHEMA = "core"


def upgrade() -> None:
    """Create chattigo_credentials table."""

    op.create_table(
        "chattigo_credentials",
        # Primary key
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # DID identification
        sa.Column(
            "did",
            sa.String(20),
            nullable=False,
            unique=True,
            comment="WhatsApp Business phone number (DID), e.g., '5492644710400'",
        ),
        sa.Column(
            "name",
            sa.String(100),
            nullable=False,
            comment="Human-readable name for this DID (e.g., 'Turmedica')",
        ),
        # Credentials (encrypted with pgcrypto)
        sa.Column(
            "username_encrypted",
            sa.Text(),
            nullable=False,
            comment="Encrypted Chattigo ISV username (pgcrypto)",
        ),
        sa.Column(
            "password_encrypted",
            sa.Text(),
            nullable=False,
            comment="Encrypted Chattigo ISV password (pgcrypto)",
        ),
        # URLs (configurable)
        sa.Column(
            "login_url",
            sa.String(255),
            nullable=False,
            server_default="https://channels.chattigo.com/bsp-cloud-chattigo-isv/login",
            comment="Chattigo ISV login endpoint",
        ),
        sa.Column(
            "message_url",
            sa.String(255),
            nullable=False,
            server_default="https://channels.chattigo.com/bsp-cloud-chattigo-isv/webhooks/inbound",
            comment="Chattigo ISV message/webhook endpoint",
        ),
        # Configuration
        sa.Column(
            "bot_name",
            sa.String(50),
            nullable=False,
            server_default="Aynux",
            comment="Bot display name for outbound messages",
        ),
        sa.Column(
            "token_refresh_hours",
            sa.Integer(),
            nullable=False,
            server_default="7",
            comment="Hours between token refresh (tokens expire at 8h)",
        ),
        # Status
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Whether this DID credential is active",
        ),
        # Foreign keys
        sa.Column(
            "organization_id",
            sa.UUID(),
            nullable=False,
            comment="Organization this credential belongs to",
        ),
        sa.Column(
            "bypass_rule_id",
            sa.UUID(),
            nullable=True,
            comment="Optional bypass rule linked to this DID",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            [f"{CORE_SCHEMA}.organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["bypass_rule_id"],
            [f"{CORE_SCHEMA}.bypass_rules.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("did", name="uq_chattigo_credentials_did"),
        schema=CORE_SCHEMA,
    )

    # Create indexes
    op.create_index(
        "idx_chattigo_credentials_did",
        "chattigo_credentials",
        ["did"],
        unique=True,
        schema=CORE_SCHEMA,
    )
    op.create_index(
        "idx_chattigo_credentials_org_id",
        "chattigo_credentials",
        ["organization_id"],
        unique=False,
        schema=CORE_SCHEMA,
    )
    op.create_index(
        "idx_chattigo_credentials_enabled",
        "chattigo_credentials",
        ["enabled"],
        unique=False,
        schema=CORE_SCHEMA,
    )
    op.create_index(
        "idx_chattigo_credentials_bypass_rule",
        "chattigo_credentials",
        ["bypass_rule_id"],
        unique=False,
        schema=CORE_SCHEMA,
    )


def downgrade() -> None:
    """Drop chattigo_credentials table."""
    op.drop_index(
        "idx_chattigo_credentials_bypass_rule",
        table_name="chattigo_credentials",
        schema=CORE_SCHEMA,
    )
    op.drop_index(
        "idx_chattigo_credentials_enabled",
        table_name="chattigo_credentials",
        schema=CORE_SCHEMA,
    )
    op.drop_index(
        "idx_chattigo_credentials_org_id",
        table_name="chattigo_credentials",
        schema=CORE_SCHEMA,
    )
    op.drop_index(
        "idx_chattigo_credentials_did",
        table_name="chattigo_credentials",
        schema=CORE_SCHEMA,
    )
    op.drop_table("chattigo_credentials", schema=CORE_SCHEMA)
