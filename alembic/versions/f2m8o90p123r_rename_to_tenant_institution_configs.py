"""rename_to_tenant_institution_configs

Revision ID: f2m8o90p123r
Revises: e1l7n89o012q
Create Date: 2025-01-07

Renames medical_institution_configs to tenant_institution_configs
for a more generic, reusable table name that follows the tenant_* pattern.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2m8o90p123r"
down_revision: Union[str, Sequence[str], None] = "e1l7n89o012q"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename table and its indexes/constraints."""

    # Drop old indexes first
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

    # Rename table
    op.rename_table(
        "medical_institution_configs",
        "tenant_institution_configs",
        schema="core",
    )

    # Rename constraint
    op.execute("""
        ALTER TABLE core.tenant_institution_configs
        RENAME CONSTRAINT uq_org_institution_key TO uq_tenant_org_institution_key;
    """)

    # Rename FK constraint
    op.execute("""
        ALTER TABLE core.tenant_institution_configs
        RENAME CONSTRAINT medical_institution_configs_organization_id_fkey
        TO tenant_institution_configs_organization_id_fkey;
    """)

    # Recreate indexes with new names
    op.create_index(
        "idx_tenant_institution_configs_org",
        "tenant_institution_configs",
        ["organization_id"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_tenant_institution_configs_key",
        "tenant_institution_configs",
        ["institution_key"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_tenant_institution_configs_enabled",
        "tenant_institution_configs",
        ["enabled"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_tenant_institution_configs_wa",
        "tenant_institution_configs",
        ["whatsapp_phone_number_id"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    """Revert table rename."""

    # Drop new indexes
    op.drop_index(
        "idx_tenant_institution_configs_wa",
        table_name="tenant_institution_configs",
        schema="core",
    )
    op.drop_index(
        "idx_tenant_institution_configs_enabled",
        table_name="tenant_institution_configs",
        schema="core",
    )
    op.drop_index(
        "idx_tenant_institution_configs_key",
        table_name="tenant_institution_configs",
        schema="core",
    )
    op.drop_index(
        "idx_tenant_institution_configs_org",
        table_name="tenant_institution_configs",
        schema="core",
    )

    # Rename constraints back
    op.execute("""
        ALTER TABLE core.tenant_institution_configs
        RENAME CONSTRAINT uq_tenant_org_institution_key TO uq_org_institution_key;
    """)

    op.execute("""
        ALTER TABLE core.tenant_institution_configs
        RENAME CONSTRAINT tenant_institution_configs_organization_id_fkey
        TO medical_institution_configs_organization_id_fkey;
    """)

    # Rename table back
    op.rename_table(
        "tenant_institution_configs",
        "medical_institution_configs",
        schema="core",
    )

    # Recreate original indexes
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
    )
