"""Fix cancelar global_keyword to be an escape_intent.

Revision ID: 003_fix_cancelar_escape_intent
Revises: 002_workflow_schema
Create Date: 2026-01-17

This migration updates the "cancelar" routing config to include
is_escape_intent: true in its metadata. This allows the cancel keyword
to interrupt awaiting_input states (e.g., debt_action) and route users
back to the main menu.

Without this flag, global keywords are ignored when the system is
awaiting input, causing "Cancelar" to be treated as invalid input
rather than a cancel command.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_fix_cancelar_escape_intent"
down_revision: Union[str, Sequence[str], None] = "002_workflow_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_escape_intent metadata to cancelar global_keyword."""
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = '{"is_escape_intent": true}'::jsonb,
            clears_context = true
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'cancelar'
    """)


def downgrade() -> None:
    """Remove is_escape_intent metadata from cancelar global_keyword."""
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = NULL,
            clears_context = false
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'cancelar'
    """)
