"""create_bypass_rules_table

Revision ID: p7j2l01m456k
Revises: o6i1k90l345j
Create Date: 2025-12-28

Creates bypass_rules table for per-tenant bypass routing configuration:
- Supports phone number patterns (e.g., "549264*")
- Supports phone number lists (exact matches)
- Supports WhatsApp Business phone number IDs

Also adds fallback_agent column to tenant_configs and migrates
existing bypass_routing rules from advanced_config JSONB.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p7j2l01m456k"
down_revision: Union[str, Sequence[str], None] = "o6i1k90l345j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create bypass_rules table and add fallback_agent to tenant_configs."""

    # ==========================================================================
    # 1. Create bypass_rules table
    # ==========================================================================
    op.create_table(
        "bypass_rules",
        # Primary key
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique bypass rule identifier",
        ),
        # Foreign key to organization
        sa.Column(
            "organization_id",
            UUID(),
            nullable=False,
            comment="Organization this rule belongs to",
        ),
        # Rule identification
        sa.Column(
            "rule_name",
            sa.String(100),
            nullable=False,
            comment="Human-readable name for the rule",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Description of what this rule does",
        ),
        # Rule type
        sa.Column(
            "rule_type",
            sa.String(50),
            nullable=False,
            comment="Type: phone_number, phone_number_list, whatsapp_phone_number_id",
        ),
        # Pattern fields
        sa.Column(
            "pattern",
            sa.String(100),
            nullable=True,
            comment="Pattern for phone_number type (e.g., '549264*')",
        ),
        sa.Column(
            "phone_numbers",
            ARRAY(sa.String),
            nullable=True,
            comment="List of phone numbers for phone_number_list type",
        ),
        sa.Column(
            "phone_number_id",
            sa.String(100),
            nullable=True,
            comment="WhatsApp Business phone number ID for whatsapp_phone_number_id type",
        ),
        # Routing target
        sa.Column(
            "target_agent",
            sa.String(100),
            nullable=False,
            comment="Agent key to route to (e.g., 'pharmacy_operations_agent')",
        ),
        sa.Column(
            "target_domain",
            sa.String(50),
            nullable=True,
            comment="Optional domain override",
        ),
        # Priority and status
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Priority for rule evaluation (higher = evaluated first)",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Whether this rule is active",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("organization_id", "rule_name", name="uq_org_bypass_rule_name"),
        schema="core",
    )

    # Create indexes
    op.create_index(
        "idx_bypass_rules_org_id",
        "bypass_rules",
        ["organization_id"],
        schema="core",
    )
    op.create_index(
        "idx_bypass_rules_enabled",
        "bypass_rules",
        ["enabled"],
        schema="core",
    )
    op.create_index(
        "idx_bypass_rules_priority",
        "bypass_rules",
        [sa.text("priority DESC")],
        schema="core",
    )
    op.create_index(
        "idx_bypass_rules_rule_type",
        "bypass_rules",
        ["rule_type"],
        schema="core",
    )

    # ==========================================================================
    # 2. Add fallback_agent column to tenant_configs
    # ==========================================================================
    op.add_column(
        "tenant_configs",
        sa.Column(
            "fallback_agent",
            sa.String(100),
            nullable=False,
            server_default="fallback_agent",
            comment="Agent to use when no specific routing matches",
        ),
        schema="core",
    )

    # ==========================================================================
    # 3. Migrate existing bypass_routing rules from advanced_config
    # ==========================================================================
    conn = op.get_bind()

    # Get all tenant configs with bypass_routing in advanced_config
    result = conn.execute(
        sa.text("""
            SELECT
                tc.id,
                tc.organization_id,
                tc.advanced_config->'bypass_routing' as bypass_config
            FROM core.tenant_configs tc
            WHERE tc.advanced_config->'bypass_routing' IS NOT NULL
              AND tc.advanced_config->'bypass_routing'->>'enabled' = 'true'
        """)
    )

    for row in result:
        bypass_config = row.bypass_config
        if not bypass_config or not isinstance(bypass_config, dict):
            continue

        rules = bypass_config.get("rules", [])
        for i, rule in enumerate(rules):
            rule_type = rule.get("type")
            target_agent = rule.get("target_agent")

            if not rule_type or not target_agent:
                continue

            # Generate rule name from type and index
            rule_name = f"migrated_{rule_type}_{i + 1}"

            # Insert into bypass_rules table
            if rule_type == "phone_number":
                pattern = rule.get("pattern")
                if pattern:
                    conn.execute(
                        sa.text("""
                            INSERT INTO core.bypass_rules
                            (organization_id, rule_name, rule_type, pattern, target_agent, priority, enabled)
                            VALUES (:org_id, :name, :type, :pattern, :agent, :priority, true)
                        """),
                        {
                            "org_id": row.organization_id,
                            "name": rule_name,
                            "type": rule_type,
                            "pattern": pattern,
                            "agent": target_agent,
                            "priority": len(rules) - i,  # Higher priority for earlier rules
                        },
                    )

            elif rule_type == "phone_number_list":
                phone_numbers = rule.get("phone_numbers", [])
                if phone_numbers:
                    conn.execute(
                        sa.text("""
                            INSERT INTO core.bypass_rules
                            (organization_id, rule_name, rule_type, phone_numbers, target_agent, priority, enabled)
                            VALUES (:org_id, :name, :type, :phones, :agent, :priority, true)
                        """),
                        {
                            "org_id": row.organization_id,
                            "name": rule_name,
                            "type": rule_type,
                            "phones": phone_numbers,
                            "agent": target_agent,
                            "priority": len(rules) - i,
                        },
                    )

            elif rule_type == "whatsapp_phone_number_id":
                phone_number_id = rule.get("phone_number_id")
                if phone_number_id:
                    conn.execute(
                        sa.text("""
                            INSERT INTO core.bypass_rules
                            (organization_id, rule_name, rule_type, phone_number_id, target_agent, priority, enabled)
                            VALUES (:org_id, :name, :type, :phone_id, :agent, :priority, true)
                        """),
                        {
                            "org_id": row.organization_id,
                            "name": rule_name,
                            "type": rule_type,
                            "phone_id": phone_number_id,
                            "agent": target_agent,
                            "priority": len(rules) - i,
                        },
                    )


def downgrade() -> None:
    """Remove bypass_rules table and fallback_agent column."""

    # Remove fallback_agent column from tenant_configs
    op.drop_column("tenant_configs", "fallback_agent", schema="core")

    # Drop indexes
    op.drop_index("idx_bypass_rules_rule_type", table_name="bypass_rules", schema="core")
    op.drop_index("idx_bypass_rules_priority", table_name="bypass_rules", schema="core")
    op.drop_index("idx_bypass_rules_enabled", table_name="bypass_rules", schema="core")
    op.drop_index("idx_bypass_rules_org_id", table_name="bypass_rules", schema="core")

    # Drop table
    op.drop_table("bypass_rules", schema="core")
