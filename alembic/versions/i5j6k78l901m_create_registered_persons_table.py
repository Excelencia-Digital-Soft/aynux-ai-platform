"""create_registered_persons_table

Revision ID: i5j6k78l901m
Revises: 061df17a83c1
Create Date: 2026-01-08

Creates registered_persons table for locally caching authorized persons
for debt queries in the pharmacy flow.

Features:
- One phone number can have multiple registered persons (e.g., family members)
- Each registration expires after 180 days but is renewed on each use
- Soft-delete support via is_active flag
- Unique constraint on (phone_number, dni, pharmacy_id)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i5j6k78l901m"
down_revision: Union[str, Sequence[str], None] = "061df17a83c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create registered_persons table."""

    op.create_table(
        "registered_persons",
        # Primary key
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique registration identifier",
        ),
        # WhatsApp phone number that registered this person
        sa.Column(
            "phone_number",
            sa.String(20),
            nullable=False,
            comment="WhatsApp phone number that registered this person",
        ),
        # Document number (validated against PLEX)
        sa.Column(
            "dni",
            sa.String(20),
            nullable=False,
            comment="Document number (validated against PLEX)",
        ),
        # Full name (validated with LLM fuzzy matching)
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Full name (validated with LLM fuzzy matching)",
        ),
        # PLEX customer ID for debt queries
        sa.Column(
            "plex_customer_id",
            sa.Integer(),
            nullable=False,
            comment="PLEX customer ID for debt queries",
        ),
        # Foreign key to pharmacy_merchant_configs
        sa.Column(
            "pharmacy_id",
            UUID(),
            nullable=False,
            comment="Pharmacy this registration belongs to",
        ),
        # True if person is the phone owner (auto-detected)
        sa.Column(
            "is_self",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if person is the phone owner (auto-detected)",
        ),
        # Registration expiration (refreshed to +180 days on each use)
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Registration expiration (refreshed to +180 days on each use)",
        ),
        # Soft-delete flag
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Soft-delete flag",
        ),
        # Last time this registration was used
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last time this registration was used",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["pharmacy_id"],
            ["core.pharmacy_merchant_configs.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "phone_number",
            "dni",
            "pharmacy_id",
            name="uq_registered_persons_phone_dni_pharmacy",
        ),
        schema="core",
    )

    # Create indexes for efficient queries
    op.create_index(
        "idx_registered_persons_phone",
        "registered_persons",
        ["phone_number"],
        unique=False,
        schema="core",
    )

    op.create_index(
        "idx_registered_persons_phone_pharmacy",
        "registered_persons",
        ["phone_number", "pharmacy_id"],
        unique=False,
        schema="core",
    )

    op.create_index(
        "idx_registered_persons_dni_pharmacy",
        "registered_persons",
        ["dni", "pharmacy_id"],
        unique=False,
        schema="core",
    )

    op.create_index(
        "idx_registered_persons_expires",
        "registered_persons",
        ["expires_at"],
        unique=False,
        schema="core",
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_index(
        "idx_registered_persons_active",
        "registered_persons",
        ["is_active"],
        unique=False,
        schema="core",
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    """Drop registered_persons table."""
    # Drop indexes
    op.drop_index(
        "idx_registered_persons_active",
        table_name="registered_persons",
        schema="core",
    )
    op.drop_index(
        "idx_registered_persons_expires",
        table_name="registered_persons",
        schema="core",
    )
    op.drop_index(
        "idx_registered_persons_dni_pharmacy",
        table_name="registered_persons",
        schema="core",
    )
    op.drop_index(
        "idx_registered_persons_phone_pharmacy",
        table_name="registered_persons",
        schema="core",
    )
    op.drop_index(
        "idx_registered_persons_phone",
        table_name="registered_persons",
        schema="core",
    )

    # Drop table
    op.drop_table("registered_persons", schema="core")
