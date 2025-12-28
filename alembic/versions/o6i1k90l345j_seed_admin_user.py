"""seed_admin_user

Revision ID: o6i1k90l345j
Revises: n5h0j89k234i
Create Date: 2025-12-28

Creates an admin user for production deployment.

IMPORTANT: This migration requires the following environment variables:
- ADMIN_EMAIL: Admin user email (default: admin@aynux.com)
- ADMIN_PASSWORD: Admin user password (REQUIRED - no default for security)
- ADMIN_USERNAME: Admin username (default: admin)
- ADMIN_FULL_NAME: Admin full name (default: System Administrator)

Run with: ADMIN_PASSWORD=your_secure_password alembic upgrade head
"""

import os
from typing import Sequence, Union

import bcrypt
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o6i1k90l345j"
down_revision: Union[str, Sequence[str], None] = "n5h0j89k234i"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Well-known admin user UUID
ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"


def _hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hash_bytes = bcrypt.hashpw(password_bytes, salt)
    return hash_bytes.decode("utf-8")


def upgrade() -> None:
    """Create admin user from environment variables."""

    # Get admin credentials from environment
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@aynux.com")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_full_name = os.environ.get("ADMIN_FULL_NAME", "System Administrator")

    if not admin_password:
        print("WARNING: ADMIN_PASSWORD not set. Skipping admin user creation.")
        print("Run this migration with ADMIN_PASSWORD=your_password to create admin user.")
        print("Or use the API endpoint POST /api/v1/auth/register to create users.")
        return

    # Hash the password
    password_hash = _hash_password(admin_password)

    # Get connection for parameterized query
    connection = op.get_bind()

    # Insert admin user with ON CONFLICT to handle re-runs
    insert_sql = text("""
        INSERT INTO core.users (
            id,
            username,
            email,
            password_hash,
            full_name,
            disabled,
            scopes,
            created_at,
            updated_at
        ) VALUES (
            :user_id::uuid,
            :username,
            :email,
            :password_hash,
            :full_name,
            false,
            ARRAY['admin', 'users:read', 'users:write', 'orgs:read', 'orgs:write']::text[],
            NOW(),
            NOW()
        ) ON CONFLICT (id) DO UPDATE SET
            username = EXCLUDED.username,
            email = EXCLUDED.email,
            password_hash = EXCLUDED.password_hash,
            full_name = EXCLUDED.full_name,
            scopes = EXCLUDED.scopes,
            updated_at = NOW();
    """)

    connection.execute(
        insert_sql,
        {
            "user_id": ADMIN_USER_ID,
            "username": admin_username,
            "email": admin_email,
            "password_hash": password_hash,
            "full_name": admin_full_name,
        },
    )

    print("Admin user created/updated successfully:")
    print(f"  - ID: {ADMIN_USER_ID}")
    print(f"  - Username: {admin_username}")
    print(f"  - Email: {admin_email}")
    print("  - Scopes: admin, users:read, users:write, orgs:read, orgs:write")


def downgrade() -> None:
    """Remove admin user."""
    op.execute(f"""
        DELETE FROM core.users
        WHERE id = '{ADMIN_USER_ID}';
    """)
    print(f"Admin user ({ADMIN_USER_ID}) removed.")
