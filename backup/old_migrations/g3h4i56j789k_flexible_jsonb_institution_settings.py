"""Flexible JSONB settings for tenant_institution_configs.

Revision ID: g3h4i56j789k
Revises: f2m8o90p123r
Create Date: 2026-01-07 21:00:00.000000

This migration converts the fixed columns in tenant_institution_configs
to a flexible JSONB structure:

Before:
    - soap_url, soap_timeout, api_type (fixed columns)
    - reminder_enabled, reminder_timezone, etc. (fixed columns)
    - institution_address, institution_phone, etc. (fixed columns)
    - whatsapp_phone_number_id (fixed column)
    - config (JSONB for arbitrary settings)

After:
    - settings (JSONB containing all dynamic configuration)
    - encrypted_secrets (BYTEA for sensitive values)
    - institution_type (VARCHAR for filtering)

The migration:
1. Adds new columns (institution_type, settings, encrypted_secrets)
2. Migrates existing data to JSONB structure
3. Drops old fixed columns
4. Creates new indexes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "g3h4i56j789k"
down_revision = "f2m8o90p123r"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add new columns
    op.add_column(
        "tenant_institution_configs",
        sa.Column("institution_type", sa.String(50), nullable=True),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("settings", JSONB, nullable=True),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("encrypted_secrets", sa.LargeBinary, nullable=True),
        schema="core",
    )

    # Step 2: Migrate data from fixed columns to JSONB settings
    op.execute(
        """
        UPDATE core.tenant_institution_configs
        SET
            institution_type = 'medical',
            settings = jsonb_build_object(
                'connection', jsonb_build_object(
                    'type', COALESCE(api_type, 'soap'),
                    'base_url', COALESCE(soap_url, ''),
                    'timeout_seconds', COALESCE(soap_timeout, 30),
                    'retry_count', 3,
                    'verify_ssl', true
                ),
                'auth', jsonb_build_object(
                    'type', 'none'
                ),
                'scheduler', jsonb_build_object(
                    'enabled', COALESCE(reminder_enabled, true),
                    'timezone', COALESCE(reminder_timezone, 'America/Argentina/San_Juan'),
                    'morning_hour', COALESCE(reminder_morning_hour, 9),
                    'evening_hour', COALESCE(reminder_evening_hour, 20),
                    'reminder_days_before', 1
                ),
                'branding', jsonb_build_object(
                    'address', institution_address,
                    'phone', institution_phone,
                    'email', institution_email,
                    'website', institution_website,
                    'logo_path', institution_logo_path
                ),
                'whatsapp', jsonb_build_object(
                    'phone_number_id', whatsapp_phone_number_id
                ),
                'custom', COALESCE(config, '{}'::jsonb)
            )
        WHERE settings IS NULL
        """
    )

    # Step 3: Set defaults and make columns non-nullable
    op.execute(
        """
        UPDATE core.tenant_institution_configs
        SET
            institution_type = COALESCE(institution_type, 'generic'),
            settings = COALESCE(settings, '{}'::jsonb)
        """
    )

    op.alter_column(
        "tenant_institution_configs",
        "institution_type",
        nullable=False,
        server_default=sa.text("'generic'"),
        schema="core",
    )
    op.alter_column(
        "tenant_institution_configs",
        "settings",
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        schema="core",
    )

    # Step 4: Drop old columns
    op.drop_column("tenant_institution_configs", "soap_url", schema="core")
    op.drop_column("tenant_institution_configs", "soap_timeout", schema="core")
    op.drop_column("tenant_institution_configs", "api_type", schema="core")
    op.drop_column("tenant_institution_configs", "reminder_enabled", schema="core")
    op.drop_column("tenant_institution_configs", "reminder_timezone", schema="core")
    op.drop_column("tenant_institution_configs", "reminder_morning_hour", schema="core")
    op.drop_column("tenant_institution_configs", "reminder_evening_hour", schema="core")
    op.drop_column("tenant_institution_configs", "institution_address", schema="core")
    op.drop_column("tenant_institution_configs", "institution_phone", schema="core")
    op.drop_column("tenant_institution_configs", "institution_email", schema="core")
    op.drop_column("tenant_institution_configs", "institution_logo_path", schema="core")
    op.drop_column("tenant_institution_configs", "institution_website", schema="core")
    op.drop_column("tenant_institution_configs", "whatsapp_phone_number_id", schema="core")
    op.drop_column("tenant_institution_configs", "config", schema="core")

    # Step 5: Drop old indexes (if they exist)
    op.execute("DROP INDEX IF EXISTS core.idx_tenant_institution_configs_wa")
    op.execute("DROP INDEX IF EXISTS core.idx_tenant_institution_configs_enabled")

    # Step 6: Create new indexes
    op.create_index(
        "idx_tenant_institution_configs_type",
        "tenant_institution_configs",
        ["institution_type"],
        schema="core",
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tenant_institution_configs_settings_gin
        ON core.tenant_institution_configs USING GIN (settings)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tenant_institution_configs_wa_phone
        ON core.tenant_institution_configs ((settings->'whatsapp'->>'phone_number_id'))
        """
    )


def downgrade() -> None:
    # Step 1: Add back old columns
    op.add_column(
        "tenant_institution_configs",
        sa.Column("soap_url", sa.String(500), nullable=True),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("soap_timeout", sa.Integer, nullable=False, server_default="30"),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("api_type", sa.String(20), nullable=False, server_default="'soap'"),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("reminder_enabled", sa.Boolean, nullable=False, server_default="true"),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column(
            "reminder_timezone",
            sa.String(100),
            nullable=False,
            server_default="'America/Argentina/San_Juan'",
        ),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("reminder_morning_hour", sa.Integer, nullable=False, server_default="9"),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("reminder_evening_hour", sa.Integer, nullable=False, server_default="20"),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("institution_address", sa.String(500), nullable=True),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("institution_phone", sa.String(50), nullable=True),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("institution_email", sa.String(255), nullable=True),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("institution_logo_path", sa.String(500), nullable=True),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("institution_website", sa.String(500), nullable=True),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("whatsapp_phone_number_id", sa.String(100), nullable=True),
        schema="core",
    )
    op.add_column(
        "tenant_institution_configs",
        sa.Column("config", JSONB, nullable=True, server_default="'{}'::jsonb"),
        schema="core",
    )

    # Step 2: Migrate data back from JSONB to fixed columns
    op.execute(
        """
        UPDATE core.tenant_institution_configs
        SET
            soap_url = settings->'connection'->>'base_url',
            soap_timeout = COALESCE((settings->'connection'->>'timeout_seconds')::integer, 30),
            api_type = COALESCE(settings->'connection'->>'type', 'soap'),
            reminder_enabled = COALESCE((settings->'scheduler'->>'enabled')::boolean, true),
            reminder_timezone = COALESCE(settings->'scheduler'->>'timezone', 'America/Argentina/San_Juan'),
            reminder_morning_hour = COALESCE((settings->'scheduler'->>'morning_hour')::integer, 9),
            reminder_evening_hour = COALESCE((settings->'scheduler'->>'evening_hour')::integer, 20),
            institution_address = settings->'branding'->>'address',
            institution_phone = settings->'branding'->>'phone',
            institution_email = settings->'branding'->>'email',
            institution_logo_path = settings->'branding'->>'logo_path',
            institution_website = settings->'branding'->>'website',
            whatsapp_phone_number_id = settings->'whatsapp'->>'phone_number_id',
            config = COALESCE(settings->'custom', '{}'::jsonb)
        """
    )

    # Step 3: Drop new indexes
    op.execute("DROP INDEX IF EXISTS core.idx_tenant_institution_configs_settings_gin")
    op.execute("DROP INDEX IF EXISTS core.idx_tenant_institution_configs_wa_phone")
    op.execute("DROP INDEX IF EXISTS core.idx_tenant_institution_configs_type")

    # Step 4: Drop new columns
    op.drop_column("tenant_institution_configs", "settings", schema="core")
    op.drop_column("tenant_institution_configs", "institution_type", schema="core")
    op.drop_column("tenant_institution_configs", "encrypted_secrets", schema="core")

    # Step 5: Recreate old indexes
    op.create_index(
        "idx_tenant_institution_configs_wa",
        "tenant_institution_configs",
        ["whatsapp_phone_number_id"],
        schema="core",
    )
    op.create_index(
        "idx_tenant_institution_configs_enabled",
        "tenant_institution_configs",
        ["enabled"],
        schema="core",
    )
