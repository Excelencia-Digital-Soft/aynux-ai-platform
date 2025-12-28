"""convert_timestamps_to_timezone_aware

Revision ID: m4g9i78j123h
Revises: l3f8h67i012g
Create Date: 2025-12-25

Converts all timestamp columns from TIMESTAMP WITHOUT TIME ZONE to
TIMESTAMP WITH TIME ZONE for consistency with UTC-aware Python datetimes.

Affected tables:
- core.conversation_contexts: created_at, updated_at, last_activity_at
- core.conversation_messages: created_at
- soporte.pending_tickets: started_at, expires_at
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m4g9i78j123h"
down_revision: Union[str, Sequence[str], None] = "l3f8h67i012g"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - convert timestamp columns to timezone-aware."""
    # Convert core.conversation_contexts timestamps (if table exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'core' AND table_name = 'conversation_contexts') THEN
                ALTER TABLE core.conversation_contexts
                    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
                        USING created_at AT TIME ZONE 'UTC',
                    ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE
                        USING updated_at AT TIME ZONE 'UTC',
                    ALTER COLUMN last_activity_at TYPE TIMESTAMP WITH TIME ZONE
                        USING last_activity_at AT TIME ZONE 'UTC';
            END IF;
        END $$;
    """)

    # Convert core.conversation_messages timestamps (if table exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'core' AND table_name = 'conversation_messages') THEN
                ALTER TABLE core.conversation_messages
                    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
                        USING created_at AT TIME ZONE 'UTC';
            END IF;
        END $$;
    """)

    # Convert soporte.pending_tickets timestamps (if table exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'soporte' AND table_name = 'pending_tickets') THEN
                ALTER TABLE soporte.pending_tickets
                    ALTER COLUMN started_at TYPE TIMESTAMP WITH TIME ZONE
                        USING started_at AT TIME ZONE 'UTC',
                    ALTER COLUMN expires_at TYPE TIMESTAMP WITH TIME ZONE
                        USING expires_at AT TIME ZONE 'UTC';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema - revert to naive timestamps."""
    # Revert core.conversation_contexts timestamps (if table exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'core' AND table_name = 'conversation_contexts') THEN
                ALTER TABLE core.conversation_contexts
                    ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE,
                    ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE,
                    ALTER COLUMN last_activity_at TYPE TIMESTAMP WITHOUT TIME ZONE;
            END IF;
        END $$;
    """)

    # Revert core.conversation_messages timestamps (if table exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'core' AND table_name = 'conversation_messages') THEN
                ALTER TABLE core.conversation_messages
                    ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE;
            END IF;
        END $$;
    """)

    # Revert soporte.pending_tickets timestamps (if table exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'soporte' AND table_name = 'pending_tickets') THEN
                ALTER TABLE soporte.pending_tickets
                    ALTER COLUMN started_at TYPE TIMESTAMP WITHOUT TIME ZONE,
                    ALTER COLUMN expires_at TYPE TIMESTAMP WITHOUT TIME ZONE;
            END IF;
        END $$;
    """)
