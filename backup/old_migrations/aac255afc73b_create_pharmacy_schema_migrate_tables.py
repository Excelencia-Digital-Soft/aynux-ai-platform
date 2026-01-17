"""Create pharmacy schema and migrate tables.

Revision ID: aac255afc73b
Revises: dd3e4f5g6h7i
Create Date: 2026-01-11

Creates the pharmacy schema and migrates pharmacy-related tables:
- pharmacy_merchant_configs (from core)
- registered_persons (from core)
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "aac255afc73b"
down_revision = "dd3e4f5g6h7i"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create pharmacy schema and migrate tables from core."""
    # 1. Create pharmacy schema
    op.execute("CREATE SCHEMA IF NOT EXISTS pharmacy")

    # 2. Move pharmacy_merchant_configs to pharmacy schema
    # First, drop dependent foreign keys
    op.execute("""
        ALTER TABLE core.registered_persons
        DROP CONSTRAINT IF EXISTS registered_persons_pharmacy_id_fkey
    """)

    op.execute("""
        ALTER TABLE core.bypass_rules
        DROP CONSTRAINT IF EXISTS bypass_rules_pharmacy_id_fkey
    """)

    # Move the table
    op.execute("ALTER TABLE core.pharmacy_merchant_configs SET SCHEMA pharmacy")

    # Recreate foreign keys pointing to new location
    op.execute("""
        ALTER TABLE core.bypass_rules
        ADD CONSTRAINT bypass_rules_pharmacy_id_fkey
        FOREIGN KEY (pharmacy_id)
        REFERENCES pharmacy.pharmacy_merchant_configs(id)
        ON DELETE SET NULL
    """)

    # 3. Move registered_persons to pharmacy schema
    op.execute("ALTER TABLE core.registered_persons SET SCHEMA pharmacy")

    # Recreate foreign key for registered_persons -> pharmacy_merchant_configs
    op.execute("""
        ALTER TABLE pharmacy.registered_persons
        ADD CONSTRAINT registered_persons_pharmacy_id_fkey
        FOREIGN KEY (pharmacy_id)
        REFERENCES pharmacy.pharmacy_merchant_configs(id)
        ON DELETE CASCADE
    """)


def downgrade() -> None:
    """Revert tables back to core schema."""
    # 1. Drop foreign keys
    op.execute("""
        ALTER TABLE pharmacy.registered_persons
        DROP CONSTRAINT IF EXISTS registered_persons_pharmacy_id_fkey
    """)

    op.execute("""
        ALTER TABLE core.bypass_rules
        DROP CONSTRAINT IF EXISTS bypass_rules_pharmacy_id_fkey
    """)

    # 2. Move registered_persons back to core
    op.execute("ALTER TABLE pharmacy.registered_persons SET SCHEMA core")

    # 3. Move pharmacy_merchant_configs back to core
    op.execute("ALTER TABLE pharmacy.pharmacy_merchant_configs SET SCHEMA core")

    # 4. Recreate foreign keys
    op.execute("""
        ALTER TABLE core.registered_persons
        ADD CONSTRAINT registered_persons_pharmacy_id_fkey
        FOREIGN KEY (pharmacy_id)
        REFERENCES core.pharmacy_merchant_configs(id)
        ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE core.bypass_rules
        ADD CONSTRAINT bypass_rules_pharmacy_id_fkey
        FOREIGN KEY (pharmacy_id)
        REFERENCES core.pharmacy_merchant_configs(id)
        ON DELETE SET NULL
    """)

    # 5. Drop pharmacy schema (only if empty)
    op.execute("DROP SCHEMA IF EXISTS pharmacy")
