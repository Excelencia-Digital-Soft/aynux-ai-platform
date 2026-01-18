"""Add config_metadata column to awaiting_type_configs for intent overrides.

Revision ID: 004_add_awaiting_type_metadata
Revises: 003_fix_cancelar_escape_intent
Create Date: 2026-01-17

This migration:
1. Adds config_metadata JSONB column to core.awaiting_type_configs
2. Populates intent_overrides for payment_confirmation and pay_debt_action

The intent_overrides feature allows users to change their mind during
confirmation flows. For example, during payment_confirmation, if the user
says "pago parcial", the system will switch to partial payment flow instead
of requiring a full cancel and restart.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_add_awaiting_type_metadata"
down_revision: Union[str, Sequence[str], None] = "003_fix_cancelar_escape_intent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add config_metadata column and populate intent_overrides."""
    # 1. Add the config_metadata column
    op.execute("""
        ALTER TABLE core.awaiting_type_configs
        ADD COLUMN IF NOT EXISTS config_metadata JSONB DEFAULT NULL;
    """)

    # 2. Add comment for the new column
    op.execute("""
        COMMENT ON COLUMN core.awaiting_type_configs.config_metadata
        IS 'Additional config: intent_overrides, etc.';
    """)

    # 3. Add intent_overrides for payment_confirmation
    # Allows switching between pay_partial, pay_full, check_debt during confirmation
    op.execute("""
        UPDATE core.awaiting_type_configs
        SET config_metadata = '{"intent_overrides": ["pay_partial", "pay_full", "check_debt"]}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND awaiting_type = 'payment_confirmation';
    """)

    # 4. Add intent_overrides for pay_debt_action
    # Allows switching payment type during the debt action menu
    op.execute("""
        UPDATE core.awaiting_type_configs
        SET config_metadata = '{"intent_overrides": ["pay_partial", "pay_full", "check_debt"]}'::jsonb
        WHERE domain_key = 'pharmacy'
          AND awaiting_type = 'pay_debt_action';
    """)


def downgrade() -> None:
    """Remove config_metadata column."""
    op.execute("""
        ALTER TABLE core.awaiting_type_configs
        DROP COLUMN IF EXISTS config_metadata;
    """)
