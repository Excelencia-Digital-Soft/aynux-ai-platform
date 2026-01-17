"""Seed intent-node mappings in routing_configs table.

Revision ID: yy4z5a6b7c8d
Revises: xx3y4z5a6b7c
Create Date: 2026-01-14

Seeds routing_configs table with intent_node_mapping entries that replace
the hardcoded DEFAULT_INTENT_NODE_MAP dictionary in router_supervisor.py.

Also consolidates AUTH_REQUIRED_INTENTS frozenset by setting requires_auth=true
on the appropriate intent_node_mapping entries (single source of truth).

This migration:
1. Adds config_type='intent_node_mapping' entries to routing_configs
2. Sets requires_auth=true on 8 intents that require authentication
3. Removes the need for hardcoded DEFAULT_INTENT_NODE_MAP and AUTH_REQUIRED_INTENTS

Replaces hardcoded:
- DEFAULT_INTENT_NODE_MAP dict (lines 44-68)
- AUTH_REQUIRED_INTENTS frozenset (lines 71-82)
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "yy4z5a6b7c8d"
down_revision: Union[str, Sequence[str], None] = "xx3y4z5a6b7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed intent-node mappings in routing_configs table."""
    _seed_intent_node_mappings()


def _seed_intent_node_mappings() -> None:
    """Seed intent -> default node mappings from DEFAULT_INTENT_NODE_MAP."""
    configs = _get_seed_configs()

    for config in configs:
        target_node = config.get("target_node")
        target_node_sql = f"'{target_node}'" if target_node else "NULL"

        op.execute(f"""
            INSERT INTO core.routing_configs
            (organization_id, domain_key, config_type, trigger_value, target_intent,
             target_node, priority, requires_auth, clears_context, display_name, description)
            VALUES (
                NULL,
                'pharmacy',
                'intent_node_mapping',
                '{config['intent']}',
                '{config['intent']}',
                {target_node_sql},
                30,
                {str(config.get('requires_auth', False)).lower()},
                false,
                '{config.get('display_name', config['intent']).replace("'", "''")}',
                '{config.get('description', '').replace("'", "''")}'
            )
            ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE SET
                target_node = EXCLUDED.target_node,
                requires_auth = EXCLUDED.requires_auth,
                display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                updated_at = CURRENT_TIMESTAMP
        """)


def _get_seed_configs() -> list[dict]:
    """
    Get seed configurations from hardcoded DEFAULT_INTENT_NODE_MAP and AUTH_REQUIRED_INTENTS.

    Source: router_supervisor.py lines 44-82
    """
    return [
        # ======================================================================
        # DEBT RELATED - requires_auth=True
        # ======================================================================
        {
            "intent": "check_debt",
            "target_node": "debt_manager",
            "requires_auth": True,
            "display_name": "Check Debt",
            "description": "Route to debt_manager for checking debt. Requires authentication.",
        },
        {
            "intent": "debt_query",
            "target_node": "debt_manager",
            "requires_auth": True,
            "display_name": "Debt Query",
            "description": "Route to debt_manager for debt queries. Requires authentication.",
        },
        # ======================================================================
        # PAYMENT RELATED - requires_auth=True
        # ======================================================================
        {
            "intent": "pay_full",
            "target_node": "payment_processor",
            "requires_auth": True,
            "display_name": "Pay Full",
            "description": "Route to payment_processor for full payment. Requires authentication.",
        },
        {
            "intent": "pay_partial",
            "target_node": "payment_processor",
            "requires_auth": True,
            "display_name": "Pay Partial",
            "description": "Route to payment_processor for partial payment. Requires authentication.",
        },
        {
            "intent": "payment_link",
            "target_node": "payment_processor",
            "requires_auth": True,
            "display_name": "Payment Link",
            "description": "Route to payment_processor for payment link. Requires authentication.",
        },
        {
            "intent": "payment_history",
            "target_node": "payment_history_node",
            "requires_auth": True,
            "display_name": "Payment History",
            "description": "Route to payment_history_node. Requires authentication.",
        },
        # ======================================================================
        # ACCOUNT MANAGEMENT - requires_auth=True
        # ======================================================================
        {
            "intent": "switch_account",
            "target_node": "account_switcher",
            "requires_auth": True,
            "display_name": "Switch Account",
            "description": "Route to account_switcher for switching accounts. Requires authentication.",
        },
        {
            "intent": "change_person",
            "target_node": "account_switcher",
            "requires_auth": True,
            "display_name": "Change Person",
            "description": "Route to account_switcher for changing person. Requires authentication.",
        },
        {
            "intent": "select_account",
            "target_node": "debt_manager",
            "requires_auth": False,
            "display_name": "Select Account",
            "description": "Route to debt_manager after account selection.",
        },
        {
            "intent": "add_new_person",
            "target_node": "auth_plex",
            "requires_auth": False,
            "display_name": "Add New Person",
            "description": "Route to auth_plex for adding new person.",
        },
        # ======================================================================
        # INFORMATION & HELP - No auth required
        # ======================================================================
        {
            "intent": "info_query",
            "target_node": "info_node",
            "requires_auth": False,
            "display_name": "Info Query",
            "description": "Route to info_node for pharmacy information.",
        },
        {
            "intent": "help",
            "target_node": "help_center_node",
            "requires_auth": False,
            "display_name": "Help",
            "description": "Route to help_center_node.",
        },
        # ======================================================================
        # NAVIGATION - No auth required
        # ======================================================================
        {
            "intent": "farewell",
            "target_node": "farewell_node",
            "requires_auth": False,
            "display_name": "Farewell",
            "description": "Route to farewell_node for goodbye.",
        },
        {
            "intent": "show_menu",
            "target_node": "main_menu_node",
            "requires_auth": False,
            "display_name": "Show Menu",
            "description": "Route to main_menu_node.",
        },
        {
            "intent": "go_back",
            "target_node": "main_menu_node",
            "requires_auth": False,
            "display_name": "Go Back",
            "description": "Route to main_menu_node for going back.",
        },
        {
            "intent": "human_escalation",
            "target_node": "human_escalation_node",
            "requires_auth": False,
            "display_name": "Human Escalation",
            "description": "Route to human_escalation_node for human agent.",
        },
        {
            "intent": "cancel_flow",
            "target_node": "main_menu_node",
            "requires_auth": False,
            "display_name": "Cancel Flow",
            "description": "Route to main_menu_node when cancelling flow.",
        },
        # ======================================================================
        # V2 FLOW INTENTS - No auth required (handled by node)
        # ======================================================================
        {
            "intent": "pay_debt_menu",
            "target_node": "debt_manager",
            "requires_auth": False,
            "display_name": "Pay Debt Menu",
            "description": "Route to debt_manager for PAY_DEBT_MENU.",
        },
        {
            "intent": "view_invoice_detail",
            "target_node": "debt_manager",
            "requires_auth": False,
            "display_name": "View Invoice Detail",
            "description": "Route to debt_manager for invoice detail.",
        },
        # ======================================================================
        # CONFIRMATION INTENTS - NULL target_node (handled by current node)
        # ======================================================================
        {
            "intent": "confirm_yes",
            "target_node": None,
            "requires_auth": False,
            "display_name": "Confirm Yes",
            "description": "Handled by current node - no routing.",
        },
        {
            "intent": "confirm_no",
            "target_node": None,
            "requires_auth": False,
            "display_name": "Confirm No",
            "description": "Handled by current node - no routing.",
        },
        {
            "intent": "own_debt",
            "target_node": None,
            "requires_auth": False,
            "display_name": "Own Debt",
            "description": "Handled by current node - own debt selection.",
        },
        {
            "intent": "other_debt",
            "target_node": None,
            "requires_auth": False,
            "display_name": "Other Debt",
            "description": "Handled by current node - other's debt selection.",
        },
    ]


def downgrade() -> None:
    """Remove intent-node mapping entries from routing_configs."""
    op.execute("""
        DELETE FROM core.routing_configs
        WHERE config_type = 'intent_node_mapping'
        AND organization_id IS NULL
        AND domain_key = 'pharmacy'
    """)
