"""enable_pgcrypto_extension

Revision ID: i0c5e34f789d
Revises: h9b4d23e678c
Create Date: 2025-12-22

Enables pgcrypto extension for symmetric encryption of tenant credentials.
Required for encrypting/decrypting sensitive data like API tokens and passwords.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i0c5e34f789d"
down_revision: Union[str, Sequence[str], None] = "h9b4d23e678c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable pgcrypto extension for encryption functions."""
    # pgcrypto provides:
    # - pgp_sym_encrypt(data, key) - Symmetric encryption
    # - pgp_sym_decrypt(data, key) - Symmetric decryption
    # - gen_random_bytes(n) - Random bytes generation
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    """Disable pgcrypto extension.

    WARNING: This will break any encrypted data in the database.
    Only run if no encrypted credentials exist.
    """
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
