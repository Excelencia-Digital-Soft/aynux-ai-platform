"""Create routing_configs table for DB-driven routing.

Revision ID: ss8t9u0v1w2x
Revises: rr7s8t9u0v1w
Create Date: 2026-01-13

Creates table for database-driven routing configuration:
- routing_configs: Maps keywords, buttons, and menu options to intents and nodes
  - config_type: 'global_keyword', 'button_mapping', 'menu_option'
  - trigger_value: The value that triggers the routing (e.g., 'menu', 'btn_pay_full', '1')
  - target_intent: Intent to set (e.g., 'show_menu', 'pay_full')
  - target_node: Node to route to (e.g., 'debt_manager', 'payment_processor')
  - priority: Higher priority = processed first

Multi-tenant: Each organization can customize their own routing configs.
Multi-domain: Supports pharmacy, healthcare, ecommerce, etc. via domain_key.

Replaces hardcoded:
- GLOBAL_KEYWORDS dict in router.py
- MENU_OPTIONS dict in router.py
- Button ID to intent mapping
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ss8t9u0v1w2x"
down_revision: Union[str, Sequence[str], None] = "rr7s8t9u0v1w"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# System organization UUID for seed data
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    """Create routing_configs table with seed data."""

    # ==========================================================================
    # 1. Clean up any leftover artifacts from failed migrations
    # ==========================================================================
    op.execute("DROP TABLE IF EXISTS core.routing_configs CASCADE")

    # ==========================================================================
    # 2. Create routing_configs table
    # ==========================================================================
    op.create_table(
        "routing_configs",
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
        # Configuration type
        sa.Column(
            "config_type",
            sa.String(50),
            nullable=False,
            comment="Type: global_keyword, button_mapping, menu_option, list_selection",
        ),
        # Trigger and target
        sa.Column(
            "trigger_value",
            sa.String(100),
            nullable=False,
            comment="Value that triggers routing (keyword, button_id, menu number)",
        ),
        sa.Column(
            "target_intent",
            sa.String(100),
            nullable=False,
            comment="Intent to set when triggered (e.g., show_menu, pay_full)",
        ),
        sa.Column(
            "target_node",
            sa.String(100),
            nullable=True,
            comment="Node to route to (NULL to use default for intent)",
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
        sa.Column(
            "requires_auth",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether this route requires authentication",
        ),
        sa.Column(
            "clears_context",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether to clear pending flow context",
        ),
        # Metadata for extensibility
        sa.Column(
            "metadata",
            JSONB(),
            nullable=True,
            comment="Additional configuration (e.g., aliases, conditions)",
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
            "config_type",
            "trigger_value",
            name="uq_routing_configs_org_domain_type_trigger",
        ),
        schema="core",
    )

    # ==========================================================================
    # 3. Create indexes for fast lookups
    # ==========================================================================
    op.create_index(
        "idx_routing_configs_lookup",
        "routing_configs",
        ["organization_id", "domain_key", "config_type", "is_enabled"],
        schema="core",
    )
    op.create_index(
        "idx_routing_configs_trigger",
        "routing_configs",
        ["trigger_value"],
        schema="core",
    )
    op.create_index(
        "idx_routing_configs_priority",
        "routing_configs",
        ["priority"],
        schema="core",
    )

    # ==========================================================================
    # 4. Add table comment
    # ==========================================================================
    op.execute("""
        COMMENT ON TABLE core.routing_configs IS
        'Database-driven routing configuration for multi-domain chatbot flows. '
        'Replaces hardcoded GLOBAL_KEYWORDS, MENU_OPTIONS, and button mappings. '
        'Multi-tenant: each organization can customize. '
        'Multi-domain: supports pharmacy, healthcare, ecommerce via domain_key.'
    """)

    # ==========================================================================
    # 5. Seed data for system organization
    # ==========================================================================
    _seed_routing_configs()


def _seed_routing_configs() -> None:
    """Seed routing configurations for system organization."""
    configs = _get_seed_configs()

    for config in configs:
        metadata_json = "NULL"
        if config.get("metadata"):
            import json
            metadata_json = f"'{json.dumps(config['metadata'])}'"

        op.execute(f"""
            INSERT INTO core.routing_configs
            (organization_id, domain_key, config_type, trigger_value, target_intent,
             target_node, priority, requires_auth, clears_context, metadata, display_name)
            VALUES (
                NULL,
                'pharmacy',
                '{config['config_type']}',
                '{config['trigger_value']}',
                '{config['target_intent']}',
                {f"'{config['target_node']}'" if config.get('target_node') else 'NULL'},
                {config.get('priority', 0)},
                {str(config.get('requires_auth', False)).lower()},
                {str(config.get('clears_context', False)).lower()},
                {metadata_json},
                '{config.get('display_name', config['trigger_value']).replace("'", "''")}'
            )
            ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO NOTHING
        """)


def _get_seed_configs() -> list[dict]:
    """Get seed configurations - extracted from hardcoded router.py."""
    return [
        # ======================================================================
        # GLOBAL KEYWORDS (priority=100) - Always interrupt any flow
        # ======================================================================
        {
            "config_type": "global_keyword",
            "trigger_value": "menu",
            "target_intent": "show_menu",
            "target_node": "main_menu_node",
            "priority": 100,
            "display_name": "Show Menu",
            "metadata": {"aliases": ["menú"]},
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "menú",
            "target_intent": "show_menu",
            "target_node": "main_menu_node",
            "priority": 100,
            "display_name": "Show Menu (accented)",
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "ayuda",
            "target_intent": "help",
            "target_node": "help_center_node",
            "priority": 100,
            "display_name": "Help",
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "cancelar",
            "target_intent": "cancel_flow",
            "target_node": "main_menu_node",
            "priority": 100,
            "clears_context": True,
            "display_name": "Cancel Flow",
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "salir",
            "target_intent": "farewell",
            "target_node": "farewell_node",
            "priority": 100,
            "display_name": "Exit/Farewell",
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "humano",
            "target_intent": "human_escalation",
            "target_node": "human_escalation_node",
            "priority": 100,
            "display_name": "Human Agent",
            "metadata": {"aliases": ["agente", "persona", "operador"]},
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "agente",
            "target_intent": "human_escalation",
            "target_node": "human_escalation_node",
            "priority": 100,
            "display_name": "Human Agent (alias)",
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "persona",
            "target_intent": "human_escalation",
            "target_node": "human_escalation_node",
            "priority": 100,
            "display_name": "Human Agent (alias)",
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "operador",
            "target_intent": "human_escalation",
            "target_node": "human_escalation_node",
            "priority": 100,
            "display_name": "Human Operator",
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "inicio",
            "target_intent": "show_menu",
            "target_node": "main_menu_node",
            "priority": 100,
            "display_name": "Start/Home",
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "volver",
            "target_intent": "go_back",
            "target_node": None,
            "priority": 90,
            "display_name": "Go Back",
            "metadata": {"aliases": ["atrás", "atras"]},
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "atrás",
            "target_intent": "go_back",
            "target_node": None,
            "priority": 90,
            "display_name": "Go Back (accented)",
        },
        {
            "config_type": "global_keyword",
            "trigger_value": "atras",
            "target_intent": "go_back",
            "target_node": None,
            "priority": 90,
            "display_name": "Go Back (no accent)",
        },
        # ======================================================================
        # BUTTON MAPPINGS (priority=50) - WhatsApp Interactive Buttons
        # ======================================================================
        {
            "config_type": "button_mapping",
            "trigger_value": "btn_pay_full",
            "target_intent": "pay_full",
            "target_node": "payment_processor",
            "priority": 50,
            "requires_auth": True,
            "display_name": "Pay Full Amount",
        },
        {
            "config_type": "button_mapping",
            "trigger_value": "btn_pay_partial",
            "target_intent": "pay_partial",
            "target_node": "payment_processor",
            "priority": 50,
            "requires_auth": True,
            "display_name": "Pay Partial Amount",
        },
        {
            "config_type": "button_mapping",
            "trigger_value": "btn_check_debt",
            "target_intent": "check_debt",
            "target_node": "debt_manager",
            "priority": 50,
            "requires_auth": True,
            "display_name": "Check Debt",
        },
        {
            "config_type": "button_mapping",
            "trigger_value": "btn_switch_account",
            "target_intent": "switch_account",
            "target_node": "account_switcher",
            "priority": 50,
            "requires_auth": True,
            "display_name": "Switch Account",
        },
        {
            "config_type": "button_mapping",
            "trigger_value": "btn_confirm_yes",
            "target_intent": "confirm_yes",
            "target_node": None,
            "priority": 50,
            "display_name": "Confirm Yes",
        },
        {
            "config_type": "button_mapping",
            "trigger_value": "btn_confirm_no",
            "target_intent": "confirm_no",
            "target_node": None,
            "priority": 50,
            "display_name": "Confirm No",
        },
        {
            "config_type": "button_mapping",
            "trigger_value": "btn_add_new_person",
            "target_intent": "add_new_person",
            "target_node": "auth_plex",
            "priority": 50,
            "display_name": "Add New Person",
        },
        {
            "config_type": "button_mapping",
            "trigger_value": "btn_own_debt",
            "target_intent": "own_debt",
            "target_node": None,
            "priority": 50,
            "display_name": "Own Debt",
        },
        {
            "config_type": "button_mapping",
            "trigger_value": "btn_other_debt",
            "target_intent": "other_debt",
            "target_node": None,
            "priority": 50,
            "display_name": "Other's Debt",
        },
        # ======================================================================
        # MENU OPTIONS (priority=40) - Main Menu 1-6, 0
        # ======================================================================
        {
            "config_type": "menu_option",
            "trigger_value": "1",
            "target_intent": "debt_query",
            "target_node": "debt_manager",
            "priority": 40,
            "requires_auth": True,
            "display_name": "Check Debt (Menu 1)",
        },
        {
            "config_type": "menu_option",
            "trigger_value": "2",
            "target_intent": "payment_link",
            "target_node": "payment_processor",
            "priority": 40,
            "requires_auth": True,
            "display_name": "Payment Link (Menu 2)",
        },
        {
            "config_type": "menu_option",
            "trigger_value": "3",
            "target_intent": "payment_history",
            "target_node": "payment_history_node",
            "priority": 40,
            "requires_auth": True,
            "display_name": "Payment History (Menu 3)",
        },
        {
            "config_type": "menu_option",
            "trigger_value": "4",
            "target_intent": "info_query",
            "target_node": "info_node",
            "priority": 40,
            "display_name": "Pharmacy Info (Menu 4)",
        },
        {
            "config_type": "menu_option",
            "trigger_value": "5",
            "target_intent": "switch_account",
            "target_node": "account_switcher",
            "priority": 40,
            "requires_auth": True,
            "display_name": "Change Person (Menu 5)",
        },
        {
            "config_type": "menu_option",
            "trigger_value": "6",
            "target_intent": "help",
            "target_node": "help_center_node",
            "priority": 40,
            "display_name": "Help (Menu 6)",
        },
        {
            "config_type": "menu_option",
            "trigger_value": "0",
            "target_intent": "farewell",
            "target_node": "farewell_node",
            "priority": 40,
            "display_name": "Exit (Menu 0)",
        },
        # ======================================================================
        # LIST SELECTION (priority=45) - WhatsApp Interactive Lists
        # ======================================================================
        # Account selections will be dynamic based on registered accounts,
        # but we can have some default patterns
        {
            "config_type": "list_selection",
            "trigger_value": "account_*",
            "target_intent": "select_account",
            "target_node": "debt_manager",
            "priority": 45,
            "display_name": "Select Account Pattern",
            "metadata": {"is_pattern": True},
        },
    ]


def downgrade() -> None:
    """Remove routing_configs table."""

    # Drop indexes
    op.drop_index(
        "idx_routing_configs_priority",
        table_name="routing_configs",
        schema="core",
    )
    op.drop_index(
        "idx_routing_configs_trigger",
        table_name="routing_configs",
        schema="core",
    )
    op.drop_index(
        "idx_routing_configs_lookup",
        table_name="routing_configs",
        schema="core",
    )

    # Drop table
    op.drop_table("routing_configs", schema="core")
