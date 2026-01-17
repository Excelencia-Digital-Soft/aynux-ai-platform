"""Cleanup organizations - keep only system and test-pharmacy.

Revision ID: zz5a6b7c8d9e
Revises: yy4z5a6b7c8d
Create Date: 2026-01-15

Removes all organizations except the two core organizations:
- System (00000000-0000-0000-0000-000000000000): Generic mode fallback
- Test Pharmacy (00000000-0000-0000-0000-000000000001): Multi-tenant pharmacy testing

Organization being removed:
- Excelencia (00000000-0000-0000-0000-000000000002): Legacy organization

Note: All related data (tenant_configs, tenant_agents, domain_intents, etc.)
will be automatically deleted via CASCADE DELETE foreign keys.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "zz5a6b7c8d9e"
down_revision: Union[str, Sequence[str], None] = "yy4z5a6b7c8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Organizations to KEEP (all others will be deleted)
KEEP_ORGANIZATION_IDS = [
    "00000000-0000-0000-0000-000000000000",  # System
    "00000000-0000-0000-0000-000000000001",  # Test Pharmacy
]


def upgrade() -> None:
    """Delete all organizations except system and test-pharmacy."""
    # Build the exclusion list for the SQL query
    keep_ids = ", ".join([f"'{org_id}'" for org_id in KEEP_ORGANIZATION_IDS])

    # Delete organizations not in the keep list
    # CASCADE DELETE will handle all related tables automatically
    op.execute(f"""
        DELETE FROM core.organizations
        WHERE id NOT IN ({keep_ids})
    """)


def downgrade() -> None:
    """
    Recreate the Excelencia organization if needed.

    Note: This only recreates the organization record itself.
    Related configuration data (tenant_configs, domain_intents, etc.)
    would need to be re-seeded separately via the appropriate migrations.
    """
    op.execute("""
        INSERT INTO core.organizations (
            id,
            slug,
            name,
            display_name,
            mode,
            llm_model,
            llm_temperature,
            llm_max_tokens,
            features,
            max_users,
            max_documents,
            max_agents,
            status,
            created_at,
            updated_at
        )
        SELECT
            '00000000-0000-0000-0000-000000000002',
            'excelencia',
            'Excelencia Digital Soft',
            'Excelencia Digital Soft',
            'multi_tenant',
            'llama3.2:1b',
            0.7,
            2048,
            '{"rag_enabled": true, "multi_domain": true, "custom_agents": true}'::jsonb,
            100,
            1000,
            20,
            'active',
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM core.organizations WHERE id = '00000000-0000-0000-0000-000000000002'
        )
    """)
