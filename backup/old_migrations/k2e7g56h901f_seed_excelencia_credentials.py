"""seed_excelencia_credentials

Revision ID: k2e7g56h901f
Revises: j1d6f45g890e
Create Date: 2025-12-22

Creates the 'excelencia' organization and seeds initial credentials
from environment variables.

IMPORTANT: This migration requires the following environment variables:
- CREDENTIAL_ENCRYPTION_KEY: pgcrypto encryption key
- DUX_API_KEY: DUX ERP API key
- DUX_API_BASE_URL: DUX API base URL
- PLEX_API_BASE_URL: Plex ERP API URL
- PLEX_API_USER: Plex ERP username
- PLEX_API_PASS: Plex ERP password

NOTE: WhatsApp/Chattigo credentials are stored in database with encryption.
Configure via Admin API: POST /api/v1/admin/chattigo-credentials

Run with: PGPASSWORD=aynux_dev uv run alembic upgrade head
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k2e7g56h901f"
down_revision: Union[str, Sequence[str], None] = "j1d6f45g890e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Well-known organization UUIDs
EXCELENCIA_ORG_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    """Create excelencia organization and seed credentials from env vars."""

    # Get encryption key
    encryption_key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    if not encryption_key:
        print("WARNING: CREDENTIAL_ENCRYPTION_KEY not set. Skipping credential seeding.")
        print("Run this migration after setting the encryption key to seed credentials.")
        _create_excelencia_org_only()
        return

    # Get credentials from environment
    # NOTE: WhatsApp/Chattigo credentials are stored in database via Admin API

    dux_api_key = os.environ.get("DUX_API_KEY", "")
    dux_base_url = os.environ.get("DUX_API_BASE_URL", "")

    plex_url = os.environ.get("PLEX_API_BASE_URL", "")
    plex_user = os.environ.get("PLEX_API_USER", "")
    plex_pass = os.environ.get("PLEX_API_PASS", "")

    # Check if we have any credentials to seed
    has_dux = dux_api_key and dux_base_url
    has_plex = plex_url and plex_user and plex_pass

    if not any([has_dux, has_plex]):
        print("WARNING: No credentials found in environment variables.")
        print("Credentials can be added later via Admin API.")
        _create_excelencia_org_only()
        return

    # Create excelencia organization if not exists
    op.execute(f"""
        INSERT INTO core.organizations (
            id, slug, name, display_name, mode, llm_model,
            llm_temperature, llm_max_tokens, features,
            max_users, max_documents, max_agents, status,
            created_at, updated_at
        ) VALUES (
            '{EXCELENCIA_ORG_ID}',
            'excelencia',
            'Excelencia Digital',
            'Excelencia Digital Soft',
            'multi_tenant',
            'llama3.2:1b',
            0.7,
            2048,
            '{{"rag_enabled": true, "primary_org": true}}'::jsonb,
            100,
            10000,
            50,
            'active',
            NOW(),
            NOW()
        ) ON CONFLICT (id) DO NOTHING;
    """)

    # Also try to insert by slug in case ID exists but slug doesn't
    op.execute(f"""
        INSERT INTO core.organizations (
            id, slug, name, display_name, mode, llm_model,
            llm_temperature, llm_max_tokens, features,
            max_users, max_documents, max_agents, status,
            created_at, updated_at
        ) VALUES (
            '{EXCELENCIA_ORG_ID}',
            'excelencia',
            'Excelencia Digital',
            'Excelencia Digital Soft',
            'multi_tenant',
            'llama3.2:1b',
            0.7,
            2048,
            '{{"rag_enabled": true, "primary_org": true}}'::jsonb,
            100,
            10000,
            50,
            'active',
            NOW(),
            NOW()
        ) ON CONFLICT (slug) DO NOTHING;
    """)

    # Get a connection for executing parameterized queries
    connection = op.get_bind()

    # Build credential insert with encryption
    # Use raw SQL with parameter binding for security
    # NOTE: WhatsApp credentials are managed via Admin API, not seeded from env vars
    insert_sql = text("""
        INSERT INTO core.tenant_credentials (
            organization_id,
            dux_api_key_encrypted,
            dux_api_base_url,
            plex_api_url,
            plex_api_user,
            plex_api_pass_encrypted,
            created_at,
            updated_at
        ) VALUES (
            CAST(:org_id AS uuid),
            CASE WHEN :dux_key != '' THEN encode(pgp_sym_encrypt(:dux_key, :key), 'base64') ELSE NULL END,
            CASE WHEN :dux_url != '' THEN :dux_url ELSE NULL END,
            CASE WHEN :plex_url != '' THEN :plex_url ELSE NULL END,
            CASE WHEN :plex_user != '' THEN :plex_user ELSE NULL END,
            CASE WHEN :plex_pass != '' THEN encode(pgp_sym_encrypt(:plex_pass, :key), 'base64') ELSE NULL END,
            NOW(),
            NOW()
        ) ON CONFLICT (organization_id) DO UPDATE SET
            dux_api_key_encrypted = CASE
                WHEN :dux_key != '' THEN encode(pgp_sym_encrypt(:dux_key, :key), 'base64')
                ELSE core.tenant_credentials.dux_api_key_encrypted
            END,
            dux_api_base_url = CASE
                WHEN :dux_url != '' THEN :dux_url
                ELSE core.tenant_credentials.dux_api_base_url
            END,
            plex_api_url = CASE
                WHEN :plex_url != '' THEN :plex_url
                ELSE core.tenant_credentials.plex_api_url
            END,
            plex_api_user = CASE
                WHEN :plex_user != '' THEN :plex_user
                ELSE core.tenant_credentials.plex_api_user
            END,
            plex_api_pass_encrypted = CASE
                WHEN :plex_pass != '' THEN encode(pgp_sym_encrypt(:plex_pass, :key), 'base64')
                ELSE core.tenant_credentials.plex_api_pass_encrypted
            END,
            updated_at = NOW();
    """)

    connection.execute(
        insert_sql,
        {
            "org_id": EXCELENCIA_ORG_ID,
            "key": encryption_key,
            "dux_key": dux_api_key,
            "dux_url": dux_base_url,
            "plex_url": plex_url,
            "plex_user": plex_user,
            "plex_pass": plex_pass,
        },
    )

    print(f"Seeded credentials for excelencia organization ({EXCELENCIA_ORG_ID}):")
    print(f"  - WhatsApp/Chattigo: configure via Admin API")
    print(f"  - DUX: {'configured' if has_dux else 'not configured'}")
    print(f"  - Plex: {'configured' if has_plex else 'not configured'}")


def _create_excelencia_org_only() -> None:
    """Create excelencia org without credentials."""
    op.execute(f"""
        INSERT INTO core.organizations (
            id, slug, name, display_name, mode, llm_model,
            llm_temperature, llm_max_tokens, features,
            max_users, max_documents, max_agents, status,
            created_at, updated_at
        ) VALUES (
            '{EXCELENCIA_ORG_ID}',
            'excelencia',
            'Excelencia Digital',
            'Excelencia Digital Soft',
            'multi_tenant',
            'llama3.2:1b',
            0.7,
            2048,
            '{{"rag_enabled": true, "primary_org": true}}'::jsonb,
            100,
            10000,
            50,
            'active',
            NOW(),
            NOW()
        ) ON CONFLICT (id) DO NOTHING;
    """)
    print(f"Created excelencia organization ({EXCELENCIA_ORG_ID}) without credentials.")
    print("Use Admin API to add credentials: PUT /api/v1/admin/organizations/{org_id}/credentials")


def downgrade() -> None:
    """Remove seeded credentials and organization."""
    # Remove credentials first
    op.execute(f"""
        DELETE FROM core.tenant_credentials
        WHERE organization_id = '{EXCELENCIA_ORG_ID}';
    """)

    # Remove organization
    op.execute(f"""
        DELETE FROM core.organizations
        WHERE id = '{EXCELENCIA_ORG_ID}';
    """)
