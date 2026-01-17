"""Add pharmacy info fields (email, website, hours, is_24h)

Revision ID: z7h2i34j567k
Revises: y6g1h23i456j
Create Date: 2025-01-03

Adds new fields to pharmacy_merchant_configs for customer information queries:
- pharmacy_email: Contact email address
- pharmacy_website: Website URL
- pharmacy_hours: Operating hours as JSONB (e.g., {"lun-vie": "08:00-20:00"})
- pharmacy_is_24h: Boolean flag for 24-hour pharmacies
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "z7h2i34j567k"
down_revision = "y6g1h23i456j"
branch_labels = None
depends_on = None

SCHEMA = "core"
TABLE = "pharmacy_merchant_configs"


def upgrade() -> None:
    """Add pharmacy info fields."""
    # Add pharmacy_email column
    op.add_column(
        TABLE,
        sa.Column(
            "pharmacy_email",
            sa.String(255),
            nullable=True,
            comment="Pharmacy contact email address",
        ),
        schema=SCHEMA,
    )

    # Add pharmacy_website column
    op.add_column(
        TABLE,
        sa.Column(
            "pharmacy_website",
            sa.String(500),
            nullable=True,
            comment="Pharmacy website URL",
        ),
        schema=SCHEMA,
    )

    # Add pharmacy_hours column (JSONB for flexible schedule storage)
    # Example: {"lun-vie": "08:00-20:00", "sab": "08:00-13:00", "dom": "cerrado"}
    op.add_column(
        TABLE,
        sa.Column(
            "pharmacy_hours",
            JSONB,
            nullable=True,
            comment="Pharmacy operating hours by day (JSONB format)",
        ),
        schema=SCHEMA,
    )

    # Add pharmacy_is_24h column
    op.add_column(
        TABLE,
        sa.Column(
            "pharmacy_is_24h",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether pharmacy operates 24 hours",
        ),
        schema=SCHEMA,
    )

    # Update test pharmacy with sample data
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE}
        SET
            pharmacy_email = 'contacto@farmacia-prueba.com',
            pharmacy_website = 'https://farmacia-prueba.com',
            pharmacy_hours = '{{"lun-vie": "08:00-20:00", "sab": "08:00-13:00", "dom": "cerrado"}}'::jsonb,
            pharmacy_is_24h = false
        WHERE pharmacy_name = 'Farmacia de Prueba'
        """
    )


def downgrade() -> None:
    """Remove pharmacy info fields."""
    op.drop_column(TABLE, "pharmacy_is_24h", schema=SCHEMA)
    op.drop_column(TABLE, "pharmacy_hours", schema=SCHEMA)
    op.drop_column(TABLE, "pharmacy_website", schema=SCHEMA)
    op.drop_column(TABLE, "pharmacy_email", schema=SCHEMA)
