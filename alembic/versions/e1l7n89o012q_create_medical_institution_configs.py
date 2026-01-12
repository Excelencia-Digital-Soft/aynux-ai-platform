"""create_medical_institution_configs

Revision ID: e1l7n89o012q
Revises: d0k6m78n901p
Create Date: 2025-01-07

Adds medical institution configuration table for multi-tenant support:
- Per-organization medical institution config (SOAP URL, reminders, branding)
- JSONB config for dynamic/flexible settings per institution
- WhatsApp phone number ID for bypass routing
- Supports multiple institutions per organization (patologia_digestiva, mercedario, etc.)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1l7n89o012q"
down_revision: Union[str, Sequence[str], None] = "d0k6m78n901p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# System organization UUID (used for generic mode)
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    """Create medical_institution_configs table and seed initial data."""

    # Create medical_institution_configs table
    op.create_table(
        "medical_institution_configs",
        # Primary key
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Foreign key to organization
        sa.Column(
            "organization_id",
            sa.UUID(),
            nullable=False,
            comment="Organization this config belongs to",
        ),
        # Institution identification
        sa.Column(
            "institution_key",
            sa.String(100),
            nullable=False,
            comment="Unique key for the institution (e.g., 'patologia_digestiva', 'mercedario')",
        ),
        sa.Column(
            "institution_name",
            sa.String(255),
            nullable=False,
            comment="Human-readable institution name",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether this institution configuration is active",
        ),
        # SOAP/REST Configuration
        sa.Column(
            "soap_url",
            sa.String(500),
            nullable=True,
            comment="SOAP/REST service URL for the medical system",
        ),
        sa.Column(
            "soap_timeout",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
            comment="Request timeout in seconds",
        ),
        sa.Column(
            "api_type",
            sa.String(20),
            nullable=False,
            server_default="'soap'",
            comment="Type of API: 'soap' (HCWeb) or 'rest' (Mercedario)",
        ),
        # Reminder Configuration
        sa.Column(
            "reminder_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether appointment reminders are enabled",
        ),
        sa.Column(
            "reminder_timezone",
            sa.String(100),
            nullable=False,
            server_default="'America/Argentina/San_Juan'",
            comment="Timezone for reminder scheduling",
        ),
        sa.Column(
            "reminder_morning_hour",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("9"),
            comment="Hour for morning reminder (0-23)",
        ),
        sa.Column(
            "reminder_evening_hour",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("20"),
            comment="Hour for evening reminder (0-23)",
        ),
        # Institution Branding
        sa.Column(
            "institution_address",
            sa.String(500),
            nullable=True,
            comment="Institution address for display",
        ),
        sa.Column(
            "institution_phone",
            sa.String(50),
            nullable=True,
            comment="Institution contact phone",
        ),
        sa.Column(
            "institution_email",
            sa.String(255),
            nullable=True,
            comment="Institution contact email",
        ),
        sa.Column(
            "institution_logo_path",
            sa.String(500),
            nullable=True,
            comment="Path to institution logo image",
        ),
        sa.Column(
            "institution_website",
            sa.String(500),
            nullable=True,
            comment="Institution website URL",
        ),
        # WhatsApp Integration
        sa.Column(
            "whatsapp_phone_number_id",
            sa.String(100),
            nullable=True,
            comment="WhatsApp Business phone number ID for bypass routing",
        ),
        # Dynamic Configuration (JSONB)
        sa.Column(
            "config",
            JSONB,
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
            comment="Additional configuration as JSONB (specialties, providers, custom settings)",
        ),
        # Description/Notes
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Description or notes about this institution",
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
            ["core.organizations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "institution_key",
            name="uq_org_institution_key",
        ),
        schema="core",
    )

    # Create indexes
    op.create_index(
        "idx_medical_institution_configs_org",
        "medical_institution_configs",
        ["organization_id"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_medical_institution_configs_key",
        "medical_institution_configs",
        ["institution_key"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_medical_institution_configs_enabled",
        "medical_institution_configs",
        ["enabled"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_medical_institution_configs_wa",
        "medical_institution_configs",
        ["whatsapp_phone_number_id"],
        unique=False,
        schema="core",
        postgresql_where=sa.text("whatsapp_phone_number_id IS NOT NULL"),
    )

    # Ensure system organization exists (required for FK)
    op.execute(f"""
        INSERT INTO core.organizations (
            id, slug, name, display_name, mode, llm_model,
            llm_temperature, llm_max_tokens, features,
            max_users, max_documents, max_agents, status,
            created_at, updated_at
        ) VALUES (
            '{SYSTEM_ORG_ID}',
            'system',
            'System',
            'System (Generic Mode)',
            'generic',
            'llama3.2:1b',
            0.7,
            2048,
            '{{"rag_enabled": true, "generic_mode": true}}'::jsonb,
            1000,
            10000,
            100,
            'active',
            NOW(),
            NOW()
        ) ON CONFLICT (id) DO NOTHING;
    """)

    # Seed Patología Digestiva config for system org
    op.execute(f"""
        INSERT INTO core.medical_institution_configs (
            organization_id,
            institution_key,
            institution_name,
            enabled,
            soap_url,
            soap_timeout,
            api_type,
            reminder_enabled,
            reminder_timezone,
            reminder_morning_hour,
            reminder_evening_hour,
            description,
            config,
            created_at,
            updated_at
        ) VALUES (
            '{SYSTEM_ORG_ID}',
            'patologia_digestiva',
            'Patología Digestiva',
            true,
            '',
            30,
            'soap',
            true,
            'America/Argentina/San_Juan',
            9,
            20,
            'Institución de gastroenterología - Turnos médicos vía SOAP HCWeb',
            '{{"specialties": ["gastroenterologia", "hepatologia", "endoscopia"], "requires_dni": true, "max_appointments_per_day": 20}}'::jsonb,
            NOW(),
            NOW()
        ) ON CONFLICT (organization_id, institution_key) DO UPDATE SET
            institution_name = EXCLUDED.institution_name,
            description = EXCLUDED.description,
            config = EXCLUDED.config;
    """)


def downgrade() -> None:
    """Remove medical_institution_configs table and test data."""
    # Remove seeded data first
    op.execute(f"""
        DELETE FROM core.medical_institution_configs
        WHERE organization_id = '{SYSTEM_ORG_ID}';
    """)

    # Drop indexes
    op.drop_index(
        "idx_medical_institution_configs_wa",
        table_name="medical_institution_configs",
        schema="core",
    )
    op.drop_index(
        "idx_medical_institution_configs_enabled",
        table_name="medical_institution_configs",
        schema="core",
    )
    op.drop_index(
        "idx_medical_institution_configs_key",
        table_name="medical_institution_configs",
        schema="core",
    )
    op.drop_index(
        "idx_medical_institution_configs_org",
        table_name="medical_institution_configs",
        schema="core",
    )

    # Drop table
    op.drop_table("medical_institution_configs", schema="core")
