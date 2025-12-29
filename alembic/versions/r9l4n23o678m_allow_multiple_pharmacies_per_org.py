"""allow_multiple_pharmacies_per_org

Revision ID: r9l4n23o678m
Revises: q8k3m12n567l
Create Date: 2025-12-29

Removes the unique constraint on organization_id to allow multiple pharmacies
per organization. Admin/owner roles can now create multiple pharmacy configs.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r9l4n23o678m"
down_revision: Union[str, Sequence[str], None] = "q8k3m12n567l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove unique constraint to allow multiple pharmacies per organization."""
    op.drop_constraint(
        "uq_pharmacy_merchant_configs_org",
        "pharmacy_merchant_configs",
        schema="core",
    )


def downgrade() -> None:
    """Re-create unique constraint (will fail if duplicates exist)."""
    op.create_unique_constraint(
        "uq_pharmacy_merchant_configs_org",
        "pharmacy_merchant_configs",
        ["organization_id"],
        schema="core",
    )
