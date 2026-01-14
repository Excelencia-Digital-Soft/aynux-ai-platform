"""Remove unused domain intents.

Revision ID: uu0v1w2x3y4z
Revises: 142e9279af3f
Create Date: 2026-01-13

Removes domain intents that were seeded but never used in code:
- pharmacy: register, summary, data_query
- excelencia: module_query

These intents have no active code references and are safe to remove.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "uu0v1w2x3y4z"
down_revision: Union[str, Sequence[str], None] = "142e9279af3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Intents to remove by domain
UNUSED_INTENTS: dict[str, list[str]] = {
    "pharmacy": ["register", "summary", "data_query"],
    "excelencia": ["module_query"],
}


def upgrade() -> None:
    """Remove unused domain intents from all organizations."""
    for domain_key, intent_keys in UNUSED_INTENTS.items():
        for intent_key in intent_keys:
            op.execute(f"""
                DELETE FROM core.domain_intents
                WHERE domain_key = '{domain_key}'
                AND intent_key = '{intent_key}'
            """)


def downgrade() -> None:
    """
    No-op: intents can be re-seeded via API if needed.

    The seed data has been removed from seed_domain_intents.py,
    so manual re-creation would be required if rollback is needed.
    """
    pass
