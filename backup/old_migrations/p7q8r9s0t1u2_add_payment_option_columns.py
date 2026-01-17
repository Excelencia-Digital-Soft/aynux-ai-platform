"""Add payment option columns to pharmacy_merchant_configs

Revision ID: p7q8r9s0t1u2
Revises: cc0k5l67m890n
Create Date: 2026-01-09

Adds three new columns for Smart Debt Negotiation:
- payment_option_half_percent: Percentage for 'half' payment option (default 50)
- payment_option_minimum_percent: Percentage for 'minimum' payment option (default 30)
- payment_minimum_amount: Minimum payment amount in currency units (default 1000)
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p7q8r9s0t1u2'
down_revision = 'cc0k5l67m890n'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add payment option columns for Smart Debt Negotiation."""
    # Add payment_option_half_percent column
    op.add_column(
        'pharmacy_merchant_configs',
        sa.Column(
            'payment_option_half_percent',
            sa.Integer(),
            nullable=False,
            server_default='50',
            comment="Percentage for 'half' payment option (e.g., 50 for 50%)",
        ),
        schema='core',
    )

    # Add payment_option_minimum_percent column
    op.add_column(
        'pharmacy_merchant_configs',
        sa.Column(
            'payment_option_minimum_percent',
            sa.Integer(),
            nullable=False,
            server_default='30',
            comment="Percentage for 'minimum' payment option (e.g., 30 for 30%)",
        ),
        schema='core',
    )

    # Add payment_minimum_amount column
    op.add_column(
        'pharmacy_merchant_configs',
        sa.Column(
            'payment_minimum_amount',
            sa.Integer(),
            nullable=False,
            server_default='1000',
            comment="Minimum payment amount in currency units (e.g., 1000 for $1000)",
        ),
        schema='core',
    )


def downgrade() -> None:
    """Remove payment option columns."""
    op.drop_column('pharmacy_merchant_configs', 'payment_minimum_amount', schema='core')
    op.drop_column('pharmacy_merchant_configs', 'payment_option_minimum_percent', schema='core')
    op.drop_column('pharmacy_merchant_configs', 'payment_option_half_percent', schema='core')
