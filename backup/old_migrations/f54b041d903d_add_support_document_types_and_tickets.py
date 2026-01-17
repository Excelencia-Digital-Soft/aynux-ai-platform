"""add_support_document_types_and_tickets

Revision ID: f54b041d903d
Revises: ad98b04fa4ed
Create Date: 2025-12-06

Adds:
- New document_type values for support content (support_faq, support_guide, etc.)
- New support_tickets table for incident/feedback tracking
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f54b041d903d"
down_revision: Union[str, Sequence[str], None] = "ad98b04fa4ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New document types to add to the ENUM
NEW_DOCUMENT_TYPES = [
    "support_faq",
    "support_guide",
    "support_contact",
    "support_training",
    "support_module",
]

# Ticket type ENUM values
TICKET_TYPES = ["incident", "feedback", "question", "suggestion"]

# Ticket status ENUM values
TICKET_STATUSES = ["open", "in_progress", "resolved", "closed"]

# Ticket priority ENUM values
TICKET_PRIORITIES = ["low", "medium", "high", "critical"]


def upgrade() -> None:
    """Upgrade schema - add support document types and tickets table."""
    # Add new values to existing document_type_enum
    # PostgreSQL requires ALTER TYPE to add enum values
    for doc_type in NEW_DOCUMENT_TYPES:
        op.execute(f"ALTER TYPE document_type_enum ADD VALUE IF NOT EXISTS '{doc_type}'")

    # Create ENUMs for support_tickets table
    ticket_type_enum = postgresql.ENUM(
        *TICKET_TYPES,
        name="ticket_type_enum",
        create_type=False,
    )
    ticket_status_enum = postgresql.ENUM(
        *TICKET_STATUSES,
        name="ticket_status_enum",
        create_type=False,
    )
    ticket_priority_enum = postgresql.ENUM(
        *TICKET_PRIORITIES,
        name="ticket_priority_enum",
        create_type=False,
    )

    # Create the ENUMs in PostgreSQL
    op.execute("CREATE TYPE ticket_type_enum AS ENUM ('incident', 'feedback', 'question', 'suggestion')")
    op.execute("CREATE TYPE ticket_status_enum AS ENUM ('open', 'in_progress', 'resolved', 'closed')")
    op.execute("CREATE TYPE ticket_priority_enum AS ENUM ('low', 'medium', 'high', 'critical')")

    # Create support_tickets table
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.UUID(), nullable=False),
        # User information
        sa.Column(
            "user_phone",
            sa.String(length=50),
            nullable=False,
            comment="WhatsApp phone number of the user",
        ),
        sa.Column(
            "user_name",
            sa.String(length=200),
            nullable=True,
            comment="Name of the user (if known)",
        ),
        sa.Column(
            "conversation_id",
            sa.UUID(),
            nullable=True,
            comment="Link to the conversation where ticket was created",
        ),
        # Ticket content
        sa.Column(
            "ticket_type",
            ticket_type_enum,
            nullable=False,
            comment="Type of ticket: incident, feedback, question, suggestion",
        ),
        sa.Column(
            "category",
            sa.String(length=100),
            nullable=True,
            comment="Category: tecnico, facturacion, capacitacion, etc.",
        ),
        sa.Column(
            "module",
            sa.String(length=100),
            nullable=True,
            comment="Affected module if applicable",
        ),
        sa.Column(
            "subject",
            sa.String(length=500),
            nullable=False,
            comment="Brief subject/title of the ticket",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            comment="Full description of the issue/feedback",
        ),
        # Status and tracking
        sa.Column(
            "status",
            ticket_status_enum,
            nullable=False,
            server_default="open",
            comment="Ticket status: open, in_progress, resolved, closed",
        ),
        sa.Column(
            "priority",
            ticket_priority_enum,
            nullable=False,
            server_default="medium",
            comment="Ticket priority: low, medium, high, critical",
        ),
        # Resolution
        sa.Column(
            "resolution",
            sa.Text(),
            nullable=True,
            comment="Resolution notes when ticket is resolved",
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(),
            nullable=True,
            comment="Timestamp when ticket was resolved",
        ),
        sa.Column(
            "resolved_by",
            sa.String(length=200),
            nullable=True,
            comment="Name/ID of person who resolved the ticket",
        ),
        # Metadata
        sa.Column(
            "meta_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Additional context from chat (message history, etc.)",
        ),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )

    # Create indexes for support_tickets
    op.create_index(
        "idx_ticket_status",
        "support_tickets",
        ["status"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_ticket_user_phone",
        "support_tickets",
        ["user_phone"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_ticket_type",
        "support_tickets",
        ["ticket_type"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_ticket_priority",
        "support_tickets",
        ["priority"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_ticket_created_at",
        "support_tickets",
        ["created_at"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema - remove support_tickets table and ENUMs.

    Note: Removing ENUM values from PostgreSQL is complex and requires
    recreating the column. This downgrade only removes the new table and ENUMs.
    The new document_type values are left in place to avoid data loss.
    """
    # Drop indexes
    op.drop_index("idx_ticket_created_at", table_name="support_tickets", schema="core")
    op.drop_index("idx_ticket_priority", table_name="support_tickets", schema="core")
    op.drop_index("idx_ticket_type", table_name="support_tickets", schema="core")
    op.drop_index("idx_ticket_user_phone", table_name="support_tickets", schema="core")
    op.drop_index("idx_ticket_status", table_name="support_tickets", schema="core")

    # Drop support_tickets table
    op.drop_table("support_tickets", schema="core")

    # Drop ENUMs
    op.execute("DROP TYPE IF EXISTS ticket_priority_enum")
    op.execute("DROP TYPE IF EXISTS ticket_status_enum")
    op.execute("DROP TYPE IF EXISTS ticket_type_enum")

    # Note: We don't remove the new document_type_enum values because:
    # 1. PostgreSQL doesn't support removing enum values easily
    # 2. Existing data might reference these values
