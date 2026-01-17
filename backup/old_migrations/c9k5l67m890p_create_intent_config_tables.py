"""create_intent_config_tables

Revision ID: a8i3j45k678l
Revises: z7h2i34j567k
Create Date: 2025-01-10

Creates tables for managing intent-to-agent configurations:
- intent_agent_mappings: Maps intents to target agents (replaces AGENT_TO_INTENT_MAPPING)
- flow_agent_configs: Configures multi-turn flow agents (replaces FLOW_AGENTS)
- keyword_agent_mappings: Keyword-based fallback routing (replaces KEYWORD_TO_AGENT)

These tables enable multi-tenant intent configuration via admin UI,
eliminating hardcoded values in intent_validator.py.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9k5l67m890p"
down_revision: Union[str, Sequence[str], None] = "bb2c3d4e5f6g"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create intent config tables and seed from hardcoded values."""

    # ==========================================================================
    # 1. Create intent_agent_mappings table (replaces AGENT_TO_INTENT_MAPPING)
    # ==========================================================================
    op.create_table(
        "intent_agent_mappings",
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique mapping identifier",
        ),
        sa.Column(
            "organization_id",
            UUID(),
            nullable=False,
            comment="Organization that owns this mapping",
        ),
        sa.Column(
            "domain_key",
            sa.String(50),
            nullable=True,
            comment="Domain scope: NULL (global), excelencia, pharmacy, etc.",
        ),
        sa.Column(
            "intent_key",
            sa.String(100),
            nullable=False,
            comment="Intent identifier (e.g., 'saludo', 'soporte', 'excelencia')",
        ),
        sa.Column(
            "intent_name",
            sa.String(255),
            nullable=False,
            comment="Human-readable intent name",
        ),
        sa.Column(
            "intent_description",
            sa.Text(),
            nullable=True,
            comment="Intent description for documentation",
        ),
        sa.Column(
            "agent_key",
            sa.String(100),
            nullable=False,
            comment="Target agent key (e.g., 'greeting_agent', 'support_agent')",
        ),
        sa.Column(
            "confidence_threshold",
            sa.Numeric(3, 2),
            nullable=False,
            server_default=sa.text("0.75"),
            comment="Minimum confidence to route (0.00-1.00)",
        ),
        sa.Column(
            "requires_handoff",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether intent requires human handoff",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("50"),
            comment="Evaluation priority (100 = highest, 0 = lowest)",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether mapping is active",
        ),
        sa.Column(
            "examples",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Example phrases for this intent",
        ),
        sa.Column(
            "config",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Additional configuration",
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            name="fk_intent_agent_mappings_org",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "domain_key",
            "intent_key",
            name="uq_intent_agent_mappings_org_domain_intent",
        ),
        schema="core",
    )

    # Indexes for intent_agent_mappings
    op.create_index(
        "idx_intent_agent_mappings_org",
        "intent_agent_mappings",
        ["organization_id"],
        schema="core",
    )
    op.create_index(
        "idx_intent_agent_mappings_org_domain",
        "intent_agent_mappings",
        ["organization_id", "domain_key"],
        schema="core",
    )
    op.create_index(
        "idx_intent_agent_mappings_enabled",
        "intent_agent_mappings",
        ["organization_id", "is_enabled"],
        schema="core",
    )

    # ==========================================================================
    # 2. Create flow_agent_configs table (replaces FLOW_AGENTS)
    # ==========================================================================
    op.create_table(
        "flow_agent_configs",
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique flow config identifier",
        ),
        sa.Column(
            "organization_id",
            UUID(),
            nullable=False,
            comment="Organization that owns this config",
        ),
        sa.Column(
            "agent_key",
            sa.String(100),
            nullable=False,
            comment="Agent key (e.g., 'pharmacy_operations_agent')",
        ),
        sa.Column(
            "is_flow_agent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether agent has multi-turn conversational flow",
        ),
        sa.Column(
            "flow_description",
            sa.Text(),
            nullable=True,
            comment="Description of the flow behavior",
        ),
        sa.Column(
            "max_turns",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
            comment="Maximum conversation turns in flow",
        ),
        sa.Column(
            "timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("300"),
            comment="Flow timeout in seconds",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether flow config is active",
        ),
        sa.Column(
            "config",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Additional flow configuration",
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            name="fk_flow_agent_configs_org",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "agent_key",
            name="uq_flow_agent_configs_org_agent",
        ),
        schema="core",
    )

    # Indexes for flow_agent_configs
    op.create_index(
        "idx_flow_agent_configs_org",
        "flow_agent_configs",
        ["organization_id"],
        schema="core",
    )
    op.create_index(
        "idx_flow_agent_configs_org_enabled",
        "flow_agent_configs",
        ["organization_id", "is_enabled"],
        schema="core",
    )

    # ==========================================================================
    # 3. Create keyword_agent_mappings table (replaces KEYWORD_TO_AGENT)
    # ==========================================================================
    op.create_table(
        "keyword_agent_mappings",
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique keyword mapping identifier",
        ),
        sa.Column(
            "organization_id",
            UUID(),
            nullable=False,
            comment="Organization that owns this mapping",
        ),
        sa.Column(
            "agent_key",
            sa.String(100),
            nullable=False,
            comment="Target agent key",
        ),
        sa.Column(
            "keyword",
            sa.String(255),
            nullable=False,
            comment="Keyword or phrase to match",
        ),
        sa.Column(
            "match_type",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'contains'"),
            comment="Match type: exact, contains, prefix, regex",
        ),
        sa.Column(
            "case_sensitive",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether match is case-sensitive",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("50"),
            comment="Evaluation priority (100 = highest)",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether keyword is active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            name="fk_keyword_agent_mappings_org",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "agent_key",
            "keyword",
            name="uq_keyword_agent_mappings_org_agent_keyword",
        ),
        schema="core",
    )

    # Indexes for keyword_agent_mappings
    op.create_index(
        "idx_keyword_agent_mappings_org",
        "keyword_agent_mappings",
        ["organization_id"],
        schema="core",
    )
    op.create_index(
        "idx_keyword_agent_mappings_org_agent",
        "keyword_agent_mappings",
        ["organization_id", "agent_key"],
        schema="core",
    )
    op.create_index(
        "idx_keyword_agent_mappings_keyword",
        "keyword_agent_mappings",
        ["organization_id", "keyword"],
        schema="core",
    )

    # ==========================================================================
    # 4. Add table comments
    # ==========================================================================
    op.execute("""
        COMMENT ON TABLE core.intent_agent_mappings IS
        'Maps intents to target agents. Replaces hardcoded AGENT_TO_INTENT_MAPPING. Multi-tenant via organization_id.'
    """)
    op.execute("""
        COMMENT ON TABLE core.flow_agent_configs IS
        'Configures agents with multi-turn flows. Replaces hardcoded FLOW_AGENTS set. Multi-tenant via organization_id.'
    """)
    op.execute("""
        COMMENT ON TABLE core.keyword_agent_mappings IS
        'Keyword-based fallback routing. Replaces hardcoded KEYWORD_TO_AGENT dict. Multi-tenant via organization_id.'
    """)


def downgrade() -> None:
    """Remove intent config tables."""

    # Drop indexes
    op.drop_index("idx_keyword_agent_mappings_keyword", table_name="keyword_agent_mappings", schema="core")
    op.drop_index("idx_keyword_agent_mappings_org_agent", table_name="keyword_agent_mappings", schema="core")
    op.drop_index("idx_keyword_agent_mappings_org", table_name="keyword_agent_mappings", schema="core")

    op.drop_index("idx_flow_agent_configs_org_enabled", table_name="flow_agent_configs", schema="core")
    op.drop_index("idx_flow_agent_configs_org", table_name="flow_agent_configs", schema="core")

    op.drop_index("idx_intent_agent_mappings_enabled", table_name="intent_agent_mappings", schema="core")
    op.drop_index("idx_intent_agent_mappings_org_domain", table_name="intent_agent_mappings", schema="core")
    op.drop_index("idx_intent_agent_mappings_org", table_name="intent_agent_mappings", schema="core")

    # Drop tables
    op.drop_table("keyword_agent_mappings", schema="core")
    op.drop_table("flow_agent_configs", schema="core")
    op.drop_table("intent_agent_mappings", schema="core")
