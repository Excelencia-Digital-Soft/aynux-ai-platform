"""add_bot_service_hours_to_pharmacy_config

Revision ID: e9c2be43fb21
Revises: aa1b2c3d4e5f
Create Date: 2026-01-10 10:06:46.987285

Adds columns for bot service hours configuration:
- bot_service_hours: JSONB for per-day service hours
- bot_service_enabled: Boolean to enforce service hours
- emergency_phone: Contact for outside service hours
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'e9c2be43fb21'
down_revision: Union[str, Sequence[str], None] = 'aa1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add bot service hours columns to pharmacy_merchant_configs."""
    op.add_column(
        'pharmacy_merchant_configs',
        sa.Column(
            'bot_service_hours',
            JSONB,
            nullable=True,
            comment="Bot service hours by day (JSONB format, e.g., {'lunes': '08:00-20:00'})",
        ),
        schema='core',
    )
    op.add_column(
        'pharmacy_merchant_configs',
        sa.Column(
            'bot_service_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment="Whether to enforce bot service hours (if False, bot is always available)",
        ),
        schema='core',
    )
    op.add_column(
        'pharmacy_merchant_configs',
        sa.Column(
            'emergency_phone',
            sa.String(50),
            nullable=True,
            comment="Emergency contact phone for outside service hours",
        ),
        schema='core',
    )


def downgrade() -> None:
    """Remove bot service hours columns from pharmacy_merchant_configs."""
    op.drop_column('pharmacy_merchant_configs', 'emergency_phone', schema='core')
    op.drop_column('pharmacy_merchant_configs', 'bot_service_enabled', schema='core')
    op.drop_column('pharmacy_merchant_configs', 'bot_service_hours', schema='core')
