"""Rename pharmacy_response_configs to response_configs.

Revision ID: df60b7014e72
Revises: aa8i3j45k678l
Create Date: 2026-01-09

Makes the response configs table generic for multi-domain support.
The table now supports pharmacy, healthcare, ecommerce, and any future domains.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "df60b7014e72"
down_revision: Union[str, Sequence[str], None] = "aa8i3j45k678l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename table and indexes to be domain-agnostic."""

    # 1. Drop old indexes (must drop before rename)
    op.drop_index(
        "idx_pharmacy_response_configs_org_domain",
        table_name="pharmacy_response_configs",
        schema="core",
    )
    op.drop_index(
        "idx_pharmacy_response_configs_enabled",
        table_name="pharmacy_response_configs",
        schema="core",
    )
    op.drop_index(
        "idx_pharmacy_response_configs_domain",
        table_name="pharmacy_response_configs",
        schema="core",
    )
    op.drop_index(
        "idx_pharmacy_response_configs_org",
        table_name="pharmacy_response_configs",
        schema="core",
    )

    # 2. Drop unique constraint
    op.drop_constraint(
        "uq_pharmacy_response_configs_org_domain_intent",
        "pharmacy_response_configs",
        schema="core",
        type_="unique",
    )

    # 3. Rename table
    op.rename_table(
        "pharmacy_response_configs",
        "response_configs",
        schema="core",
    )

    # 4. Rename primary key constraint
    op.execute(
        "ALTER TABLE core.response_configs "
        "RENAME CONSTRAINT pharmacy_response_configs_pkey TO response_configs_pkey"
    )

    # 5. Create new indexes with generic names
    op.create_index(
        "idx_response_configs_org",
        "response_configs",
        ["organization_id"],
        schema="core",
    )
    op.create_index(
        "idx_response_configs_domain",
        "response_configs",
        ["domain_key"],
        schema="core",
    )
    op.create_index(
        "idx_response_configs_enabled",
        "response_configs",
        ["organization_id", "is_enabled"],
        schema="core",
    )
    op.create_index(
        "idx_response_configs_org_domain",
        "response_configs",
        ["organization_id", "domain_key"],
        schema="core",
    )

    # 6. Create new unique constraint
    op.create_unique_constraint(
        "uq_response_configs_org_domain_intent",
        "response_configs",
        ["organization_id", "domain_key", "intent_key"],
        schema="core",
    )

    # 7. Update table comment
    op.execute("""
        COMMENT ON TABLE core.response_configs IS
        'Multi-domain response generation configuration. '
        'Supports pharmacy, healthcare, ecommerce, and future domains via domain_key. '
        'Multi-tenant: each organization can customize per domain.'
    """)


def downgrade() -> None:
    """Revert to pharmacy-specific table name."""

    # 1. Drop new indexes
    op.drop_index(
        "idx_response_configs_org_domain",
        table_name="response_configs",
        schema="core",
    )
    op.drop_index(
        "idx_response_configs_enabled",
        table_name="response_configs",
        schema="core",
    )
    op.drop_index(
        "idx_response_configs_domain",
        table_name="response_configs",
        schema="core",
    )
    op.drop_index(
        "idx_response_configs_org",
        table_name="response_configs",
        schema="core",
    )

    # 2. Drop unique constraint
    op.drop_constraint(
        "uq_response_configs_org_domain_intent",
        "response_configs",
        schema="core",
        type_="unique",
    )

    # 3. Rename table back
    op.rename_table(
        "response_configs",
        "pharmacy_response_configs",
        schema="core",
    )

    # 4. Rename primary key constraint back
    op.execute(
        "ALTER TABLE core.pharmacy_response_configs "
        "RENAME CONSTRAINT response_configs_pkey TO pharmacy_response_configs_pkey"
    )

    # 5. Create old indexes
    op.create_index(
        "idx_pharmacy_response_configs_org",
        "pharmacy_response_configs",
        ["organization_id"],
        schema="core",
    )
    op.create_index(
        "idx_pharmacy_response_configs_domain",
        "pharmacy_response_configs",
        ["domain_key"],
        schema="core",
    )
    op.create_index(
        "idx_pharmacy_response_configs_enabled",
        "pharmacy_response_configs",
        ["organization_id", "is_enabled"],
        schema="core",
    )
    op.create_index(
        "idx_pharmacy_response_configs_org_domain",
        "pharmacy_response_configs",
        ["organization_id", "domain_key"],
        schema="core",
    )

    # 6. Create old unique constraint
    op.create_unique_constraint(
        "uq_pharmacy_response_configs_org_domain_intent",
        "pharmacy_response_configs",
        ["organization_id", "domain_key", "intent_key"],
        schema="core",
    )
