"""Create awaiting_type_configs table for DB-driven awaiting input routing.

Revision ID: xx3y4z5a6b7c
Revises: ww2x3y4z5a6b
Create Date: 2026-01-14

Creates table for database-driven awaiting type configuration:
- awaiting_type_configs: Maps awaiting input types to handler nodes and valid responses
  - awaiting_type: Type of awaited input (dni, amount, payment_confirmation, etc.)
  - target_node: Node to route to when awaiting this type
  - valid_response_intents: Intent keys for Priority 0 validation (bypass global keywords)
  - validation_pattern: Optional regex for validating responses

Multi-tenant: Each organization can customize their own awaiting type configs.
Multi-domain: Supports pharmacy, healthcare, ecommerce, etc. via domain_key.

Replaces hardcoded:
- awaiting_node_map in router_supervisor.py (lines 386-398)
- awaiting_intent_map in router_supervisor.py (lines 434-439)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "xx3y4z5a6b7c"
down_revision: Union[str, Sequence[str], None] = "ww2x3y4z5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create awaiting_type_configs table with seed data."""

    # ==========================================================================
    # 1. Clean up any leftover artifacts from failed migrations
    # ==========================================================================
    op.execute("DROP TABLE IF EXISTS core.awaiting_type_configs CASCADE")

    # ==========================================================================
    # 2. Create awaiting_type_configs table
    # ==========================================================================
    op.create_table(
        "awaiting_type_configs",
        # Primary key
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique configuration identifier",
        ),
        # Multi-tenant association (nullable for system-wide configs)
        sa.Column(
            "organization_id",
            UUID(),
            nullable=True,
            comment="Organization that owns this configuration (NULL for system defaults)",
        ),
        # Domain scope
        sa.Column(
            "domain_key",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'pharmacy'"),
            comment="Domain: pharmacy, healthcare, ecommerce, etc.",
        ),
        # Awaiting type identifier
        sa.Column(
            "awaiting_type",
            sa.String(100),
            nullable=False,
            comment="Awaiting input type (dni, amount, payment_confirmation, etc.)",
        ),
        # Target node for routing
        sa.Column(
            "target_node",
            sa.String(100),
            nullable=False,
            comment="Node to route to when awaiting this type",
        ),
        # Valid response intents for Priority 0 validation (JSONB array)
        sa.Column(
            "valid_response_intents",
            JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
            comment="Intent keys for validating responses (bypasses global keywords)",
        ),
        # Optional validation pattern (regex)
        sa.Column(
            "validation_pattern",
            sa.String(255),
            nullable=True,
            comment="Optional regex pattern for validating responses (e.g., amount format)",
        ),
        # Priority and flags
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Processing priority (higher = first)",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether configuration is active",
        ),
        # Display information
        sa.Column(
            "display_name",
            sa.String(200),
            nullable=True,
            comment="Human-readable name",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Usage notes",
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
        sa.UniqueConstraint(
            "organization_id",
            "domain_key",
            "awaiting_type",
            name="uq_awaiting_type_configs_org_domain_type",
        ),
        schema="core",
    )

    # ==========================================================================
    # 3. Create indexes for fast lookups
    # ==========================================================================
    op.create_index(
        "idx_awaiting_type_configs_lookup",
        "awaiting_type_configs",
        ["organization_id", "domain_key", "is_enabled"],
        schema="core",
    )
    op.create_index(
        "idx_awaiting_type_configs_type",
        "awaiting_type_configs",
        ["awaiting_type"],
        schema="core",
    )
    op.create_index(
        "idx_awaiting_type_configs_priority",
        "awaiting_type_configs",
        ["priority"],
        schema="core",
    )

    # ==========================================================================
    # 4. Add table comment
    # ==========================================================================
    op.execute("""
        COMMENT ON TABLE core.awaiting_type_configs IS
        'Database-driven awaiting type routing configuration. '
        'Replaces hardcoded awaiting_node_map and awaiting_intent_map in router_supervisor.py. '
        'Multi-tenant: each organization can customize. '
        'Multi-domain: supports pharmacy, healthcare, ecommerce via domain_key.'
    """)

    # ==========================================================================
    # 5. Seed data for system organization (NULL = system-wide defaults)
    # ==========================================================================
    _seed_awaiting_type_configs()


def _seed_awaiting_type_configs() -> None:
    """Seed awaiting type configurations from hardcoded router_supervisor.py."""
    import json

    configs = _get_seed_configs()

    for config in configs:
        valid_intents_json = f"'{json.dumps(config.get('valid_response_intents', []))}'"
        validation_pattern = config.get("validation_pattern")
        pattern_sql = f"'{validation_pattern}'" if validation_pattern else "NULL"

        op.execute(f"""
            INSERT INTO core.awaiting_type_configs
            (organization_id, domain_key, awaiting_type, target_node,
             valid_response_intents, validation_pattern, priority, display_name, description)
            VALUES (
                NULL,
                'pharmacy',
                '{config['awaiting_type']}',
                '{config['target_node']}',
                {valid_intents_json},
                {pattern_sql},
                {config.get('priority', 0)},
                '{config.get('display_name', config['awaiting_type']).replace("'", "''")}',
                '{config.get('description', '').replace("'", "''")}'
            )
            ON CONFLICT (organization_id, domain_key, awaiting_type) DO NOTHING
        """)


def _get_seed_configs() -> list[dict]:
    """Get seed configurations - extracted from hardcoded router_supervisor.py."""
    return [
        # ======================================================================
        # AUTHENTICATION FLOW - Awaiting DNI/Name input
        # ======================================================================
        {
            "awaiting_type": "dni",
            "target_node": "auth_plex",
            "valid_response_intents": [],
            "validation_pattern": None,
            "priority": 0,
            "display_name": "DNI Input",
            "description": "Awaiting user DNI for authentication. Routes to auth_plex.",
        },
        {
            "awaiting_type": "name",
            "target_node": "auth_plex",
            "valid_response_intents": [],
            "validation_pattern": None,
            "priority": 0,
            "display_name": "Name Input",
            "description": "Awaiting user name for authentication. Routes to auth_plex.",
        },
        # ======================================================================
        # PAYMENT FLOW - Awaiting amount or confirmation
        # ======================================================================
        {
            "awaiting_type": "amount",
            "target_node": "payment_processor",
            "valid_response_intents": [],
            "validation_pattern": r"^\$?\d+([.,]\d{1,2})?$",
            "priority": 0,
            "display_name": "Payment Amount",
            "description": "Awaiting payment amount. Validates numeric format with optional currency symbol.",
        },
        {
            "awaiting_type": "payment_confirmation",
            "target_node": "payment_processor",
            "valid_response_intents": ["confirm_yes", "confirm_no"],
            "validation_pattern": None,
            "priority": 10,
            "display_name": "Payment Confirmation",
            "description": "Awaiting yes/no confirmation for payment. Protected - bypasses global keywords.",
        },
        # ======================================================================
        # ACCOUNT MANAGEMENT - Awaiting account selection or own/other choice
        # ======================================================================
        {
            "awaiting_type": "account_selection",
            "target_node": "account_switcher",
            "valid_response_intents": ["account_add_new"],
            "validation_pattern": r"^\d{1,2}$",
            "priority": 0,
            "display_name": "Account Selection",
            "description": "Awaiting account number selection. Accepts numeric 1-99 or 'add new' intent.",
        },
        {
            "awaiting_type": "own_or_other",
            "target_node": "account_switcher",
            "valid_response_intents": ["account_own_selection", "account_other_selection"],
            "validation_pattern": None,
            "priority": 10,
            "display_name": "Own or Other Selection",
            "description": "Awaiting 'own debt' or 'other person' selection. Protected - bypasses global keywords.",
        },
        # ======================================================================
        # MENU NAVIGATION - Awaiting menu option selection
        # ======================================================================
        {
            "awaiting_type": "menu_selection",
            "target_node": "main_menu_node",
            "valid_response_intents": [],
            "validation_pattern": None,
            "priority": 0,
            "display_name": "Menu Selection",
            "description": "Awaiting main menu option selection (1-6, 0).",
        },
        # ======================================================================
        # V2 FLOW TYPES - Debt manager menus
        # ======================================================================
        {
            "awaiting_type": "debt_action",
            "target_node": "debt_manager",
            "valid_response_intents": [],
            "validation_pattern": None,
            "priority": 0,
            "display_name": "Debt Action Menu",
            "description": "Awaiting SHOW_DEBT 4-option menu selection.",
        },
        {
            "awaiting_type": "pay_debt_action",
            "target_node": "debt_manager",
            "valid_response_intents": [],
            "validation_pattern": None,
            "priority": 0,
            "display_name": "Pay Debt Action Menu",
            "description": "Awaiting PAY_DEBT_MENU 3-option menu selection.",
        },
        {
            "awaiting_type": "invoice_detail_action",
            "target_node": "debt_manager",
            "valid_response_intents": [],
            "validation_pattern": None,
            "priority": 0,
            "display_name": "Invoice Detail Action Menu",
            "description": "Awaiting INVOICE_DETAIL 3-option menu selection.",
        },
    ]


def downgrade() -> None:
    """Remove awaiting_type_configs table."""

    # Drop indexes
    op.drop_index(
        "idx_awaiting_type_configs_priority",
        table_name="awaiting_type_configs",
        schema="core",
    )
    op.drop_index(
        "idx_awaiting_type_configs_type",
        table_name="awaiting_type_configs",
        schema="core",
    )
    op.drop_index(
        "idx_awaiting_type_configs_lookup",
        table_name="awaiting_type_configs",
        schema="core",
    )

    # Drop table
    op.drop_table("awaiting_type_configs", schema="core")
