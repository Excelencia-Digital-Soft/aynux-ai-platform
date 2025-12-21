"""add_pharmacy_merchant_configs

Revision ID: h9b4d23e678c
Revises: g8a3c12f567b
Create Date: 2025-12-19

Adds pharmacy merchant configuration table for multi-tenant support:
- Per-organization pharmacy info for PDF receipts
- Per-organization Mercado Pago credentials
- Seeds test organization for Streamlit testing
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h9b4d23e678c"
down_revision: Union[str, Sequence[str], None] = "g8a3c12f567b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Well-known test organization UUID (different from system org 0...0)
TEST_PHARMACY_ORG_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Create pharmacy_merchant_configs table and seed test data."""

    # Create pharmacy_merchant_configs table
    op.create_table(
        "pharmacy_merchant_configs",
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
            comment="Organization this config belongs to (1:1 relationship)",
        ),
        # Pharmacy receipt info
        sa.Column(
            "pharmacy_name",
            sa.String(255),
            nullable=False,
            server_default="Farmacia",
            comment="Pharmacy name displayed on PDF receipts",
        ),
        sa.Column(
            "pharmacy_address",
            sa.String(500),
            nullable=True,
            comment="Pharmacy address displayed on PDF receipts",
        ),
        sa.Column(
            "pharmacy_phone",
            sa.String(50),
            nullable=True,
            comment="Pharmacy phone displayed on PDF receipts",
        ),
        sa.Column(
            "pharmacy_logo_path",
            sa.String(500),
            nullable=True,
            comment="Path to pharmacy logo image for PDF receipts",
        ),
        # Mercado Pago credentials
        sa.Column(
            "mp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether Mercado Pago integration is enabled",
        ),
        sa.Column(
            "mp_access_token",
            sa.String(500),
            nullable=True,
            comment="Mercado Pago Access Token (APP_USR-xxx)",
        ),
        sa.Column(
            "mp_public_key",
            sa.String(255),
            nullable=True,
            comment="Mercado Pago Public Key",
        ),
        sa.Column(
            "mp_webhook_secret",
            sa.String(255),
            nullable=True,
            comment="Secret for validating MP webhook signatures",
        ),
        sa.Column(
            "mp_sandbox",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Use Mercado Pago sandbox mode for testing",
        ),
        sa.Column(
            "mp_timeout",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
            comment="Timeout for Mercado Pago API requests in seconds",
        ),
        # URLs
        sa.Column(
            "mp_notification_url",
            sa.String(500),
            nullable=True,
            comment="Public URL for Mercado Pago webhook notifications",
        ),
        sa.Column(
            "receipt_public_url_base",
            sa.String(500),
            nullable=True,
            comment="Base URL for public PDF receipt access",
        ),
        # WhatsApp mapping for fast lookup
        sa.Column(
            "whatsapp_phone_number",
            sa.String(20),
            nullable=True,
            comment="WhatsApp phone number for quick webhook org resolution",
        ),
        # Timestamps
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
        sa.UniqueConstraint("organization_id", name="uq_pharmacy_merchant_configs_org"),
        schema="core",
    )

    # Create indexes
    op.create_index(
        "idx_pharmacy_merchant_configs_org",
        "pharmacy_merchant_configs",
        ["organization_id"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_pharmacy_merchant_configs_whatsapp",
        "pharmacy_merchant_configs",
        ["whatsapp_phone_number"],
        unique=False,
        schema="core",
        postgresql_where=sa.text("whatsapp_phone_number IS NOT NULL"),
    )

    # Seed test organization for Streamlit testing
    # This org has a well-known UUID that Streamlit will use
    op.execute(f"""
        INSERT INTO core.organizations (
            id, slug, name, display_name, mode, llm_model,
            llm_temperature, llm_max_tokens, features,
            max_users, max_documents, max_agents, status,
            created_at, updated_at
        ) VALUES (
            '{TEST_PHARMACY_ORG_ID}',
            'test-pharmacy',
            'Test Pharmacy',
            'Farmacia de Prueba (Streamlit)',
            'multi_tenant',
            'llama3.2:1b',
            0.7,
            2048,
            '{{"rag_enabled": false, "test_mode": true}}'::jsonb,
            100,
            1000,
            20,
            'active',
            NOW(),
            NOW()
        ) ON CONFLICT (id) DO NOTHING;
    """)

    # Seed test pharmacy config
    op.execute(f"""
        INSERT INTO core.pharmacy_merchant_configs (
            organization_id,
            pharmacy_name,
            pharmacy_address,
            pharmacy_phone,
            mp_enabled,
            mp_sandbox,
            mp_timeout,
            whatsapp_phone_number,
            created_at,
            updated_at
        ) VALUES (
            '{TEST_PHARMACY_ORG_ID}',
            'Farmacia de Prueba',
            'Calle Test 123, Ciudad Test',
            '+54 9 264 555-0000',
            false,
            true,
            30,
            'TEST_PHARMACY_000',
            NOW(),
            NOW()
        ) ON CONFLICT (organization_id) DO NOTHING;
    """)


def downgrade() -> None:
    """Remove pharmacy_merchant_configs table and test data."""
    # Remove test data first
    op.execute(f"""
        DELETE FROM core.pharmacy_merchant_configs
        WHERE organization_id = '{TEST_PHARMACY_ORG_ID}';
    """)
    op.execute(f"""
        DELETE FROM core.organizations
        WHERE id = '{TEST_PHARMACY_ORG_ID}';
    """)

    # Drop indexes
    op.drop_index(
        "idx_pharmacy_merchant_configs_whatsapp",
        table_name="pharmacy_merchant_configs",
        schema="core",
    )
    op.drop_index(
        "idx_pharmacy_merchant_configs_org",
        table_name="pharmacy_merchant_configs",
        schema="core",
    )

    # Drop table
    op.drop_table("pharmacy_merchant_configs", schema="core")
