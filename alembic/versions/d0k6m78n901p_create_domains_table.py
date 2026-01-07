"""create_domains_table

Revision ID: d0k6m78n901p
Revises: b9j4k56l789m
Create Date: 2026-01-06

Creates centralized domains table for managing business domains.
Domains are shared between agent catalog and bypass rules.
Seeds initial 5 domains: excelencia, ecommerce, pharmacy, credit, healthcare.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0k6m78n901p"
down_revision: Union[str, Sequence[str], None] = "b9j4k56l789m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create domains table and seed initial domains."""

    # ==========================================================================
    # 1. Create domains table in core schema
    # ==========================================================================
    op.create_table(
        "domains",
        # Primary key
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique domain identifier",
        ),
        # Domain identification
        sa.Column(
            "domain_key",
            sa.String(50),
            nullable=False,
            comment="Unique domain key (e.g., 'excelencia', 'pharmacy')",
        ),
        # Display properties
        sa.Column(
            "display_name",
            sa.String(255),
            nullable=False,
            comment="Human-readable name for UI display",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Domain description and purpose",
        ),
        sa.Column(
            "icon",
            sa.String(100),
            nullable=True,
            comment="PrimeVue icon class (e.g., 'pi-building')",
        ),
        sa.Column(
            "color",
            sa.String(50),
            nullable=True,
            comment="Tag severity color (e.g., 'info', 'success')",
        ),
        # Status and ordering
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether domain is available for selection",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Display order in dropdowns (lower = first)",
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
        # Primary key constraint
        sa.PrimaryKeyConstraint("id"),
        # Unique constraint
        sa.UniqueConstraint("domain_key", name="uq_core_domains_domain_key"),
        # Schema
        schema="core",
    )

    # ==========================================================================
    # 2. Create indexes
    # ==========================================================================
    op.create_index(
        "ix_core_domains_domain_key",
        "domains",
        ["domain_key"],
        schema="core",
    )
    op.create_index(
        "ix_core_domains_enabled",
        "domains",
        ["enabled"],
        schema="core",
    )

    # ==========================================================================
    # 3. Seed initial domains
    # ==========================================================================
    op.execute("""
        INSERT INTO core.domains (id, domain_key, display_name, description, icon, color, enabled, sort_order, created_at, updated_at)
        VALUES
        (gen_random_uuid(), 'excelencia', 'Excelencia', 'Software ERP Excelencia', 'pi-building', 'help', true, 1, NOW(), NOW()),
        (gen_random_uuid(), 'ecommerce', 'E-commerce', 'Comercio electronico', 'pi-shopping-cart', 'success', true, 2, NOW(), NOW()),
        (gen_random_uuid(), 'pharmacy', 'Farmacia', 'Operaciones de farmacia', 'pi-heart', 'info', true, 3, NOW(), NOW()),
        (gen_random_uuid(), 'credit', 'Credito', 'Servicios financieros y credito', 'pi-wallet', 'warn', true, 4, NOW(), NOW()),
        (gen_random_uuid(), 'healthcare', 'Salud', 'Servicios de salud', 'pi-heart-fill', 'secondary', true, 5, NOW(), NOW())
    """)


def downgrade() -> None:
    """Drop domains table."""
    op.drop_index("ix_core_domains_enabled", table_name="domains", schema="core")
    op.drop_index("ix_core_domains_domain_key", table_name="domains", schema="core")
    op.drop_table("domains", schema="core")
