"""Add is_escape_intent to menu-related global keywords.

Revision ID: 005_add_menu_escape_intents
Revises: 004_add_awaiting_type_metadata
Create Date: 2026-01-18

This migration updates menu-related global keywords to include
is_escape_intent: true in their metadata. This allows users to use
natural language (e.g., "pagar deuda", "consultar deuda") while in
menu_selection awaiting state.

Without this flag, global keywords are blocked when awaiting_input=menu_selection,
causing a routing loop where the system keeps showing the main menu instead of
processing the user's intent.

Affected keywords:
- pagar deuda → pay_debt_menu
- consultar deuda → debt_query
- menu → show_menu
- ayuda → help
- info → info_query
- otra cuenta → switch_account
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_add_menu_escape_intents"
down_revision: Union[str, Sequence[str], None] = "004_add_awaiting_type_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_escape_intent to menu-related global keywords."""
    # For keywords with existing metadata, merge is_escape_intent
    # For keywords without metadata, set is_escape_intent

    # pagar deuda - has existing aliases metadata
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = metadata || '{"is_escape_intent": true}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'pagar deuda'
          AND metadata IS NOT NULL
    """)

    # consultar deuda - has existing aliases metadata
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = metadata || '{"is_escape_intent": true}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'consultar deuda'
          AND metadata IS NOT NULL
    """)

    # menu - has existing aliases metadata
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = metadata || '{"is_escape_intent": true}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'menu'
          AND metadata IS NOT NULL
    """)

    # menu without metadata (just in case)
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = '{"is_escape_intent": true}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'menu'
          AND metadata IS NULL
    """)

    # menú (with accent)
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = '{"is_escape_intent": true}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'menú'
          AND metadata IS NULL
    """)

    # inicio
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = '{"is_escape_intent": true}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'inicio'
          AND metadata IS NULL
    """)

    # ayuda - no existing metadata
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = '{"is_escape_intent": true}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'ayuda'
    """)

    # info - has existing aliases metadata
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = metadata || '{"is_escape_intent": true}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'info'
          AND metadata IS NOT NULL
    """)

    # otra cuenta - has existing aliases metadata
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = metadata || '{"is_escape_intent": true}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'otra cuenta'
          AND metadata IS NOT NULL
    """)


def downgrade() -> None:
    """Remove is_escape_intent from menu-related global keywords."""
    # For keywords with other metadata, remove just is_escape_intent
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = metadata - 'is_escape_intent'
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value IN ('pagar deuda', 'consultar deuda', 'menu', 'info', 'otra cuenta')
          AND metadata ? 'is_escape_intent'
    """)

    # For keywords that only had is_escape_intent, set to NULL
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = NULL
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value IN ('menú', 'inicio', 'ayuda')
    """)
