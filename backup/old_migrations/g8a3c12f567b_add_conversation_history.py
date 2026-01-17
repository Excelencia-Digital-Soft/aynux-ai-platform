"""add_conversation_history

Revision ID: g8a3c12f567b
Revises: f54b041d903d
Create Date: 2025-12-06

Adds conversation history management tables for:
- Persistent conversation context with rolling summaries
- Individual message storage for history retrieval
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g8a3c12f567b"
down_revision: Union[str, Sequence[str], None] = "f54b041d903d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Sender type ENUM values
SENDER_TYPES = ["user", "assistant", "system"]


def upgrade() -> None:
    """Upgrade schema - add conversation history tables."""
    # Create sender_type ENUM
    op.execute("CREATE TYPE sender_type_enum AS ENUM ('user', 'assistant', 'system')")

    # Create conversation_contexts table
    op.create_table(
        "conversation_contexts",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        # Identification
        sa.Column(
            "conversation_id",
            sa.String(length=255),
            nullable=False,
            unique=True,
            comment="Unique identifier for the conversation (e.g., whatsapp_{phone})",
        ),
        sa.Column(
            "organization_id",
            sa.UUID(),
            nullable=True,
            comment="Multi-tenancy: organization that owns this conversation",
        ),
        sa.Column(
            "user_phone",
            sa.String(length=50),
            nullable=True,
            comment="User phone number for WhatsApp conversations",
        ),
        # Context data
        sa.Column(
            "rolling_summary",
            sa.Text(),
            nullable=True,
            comment="LLM-generated rolling summary of the conversation",
        ),
        sa.Column(
            "topic_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="List of topics discussed in the conversation",
        ),
        sa.Column(
            "key_entities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Key entities mentioned (names, products, preferences)",
        ),
        # Tracking metrics
        sa.Column(
            "total_turns",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Total number of conversation turns",
        ),
        sa.Column(
            "last_user_message",
            sa.Text(),
            nullable=True,
            comment="Last message from user for quick access",
        ),
        sa.Column(
            "last_bot_response",
            sa.Text(),
            nullable=True,
            comment="Last response from assistant for quick access",
        ),
        # Extra context data
        sa.Column(
            "extra_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Additional context data (channel, language, etc.)",
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
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Last activity timestamp for cleanup queries",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )

    # Create indexes for conversation_contexts
    op.create_index(
        "idx_conv_ctx_conversation_id",
        "conversation_contexts",
        ["conversation_id"],
        unique=True,
        schema="core",
    )
    op.create_index(
        "idx_conv_ctx_user_phone_org",
        "conversation_contexts",
        ["user_phone", "organization_id"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_conv_ctx_last_activity",
        "conversation_contexts",
        ["last_activity_at"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_conv_ctx_organization",
        "conversation_contexts",
        ["organization_id"],
        unique=False,
        schema="core",
    )

    # Create conversation_messages table
    sender_type_enum = postgresql.ENUM(
        *SENDER_TYPES,
        name="sender_type_enum",
        create_type=False,
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        # Foreign key to context
        sa.Column(
            "conversation_id",
            sa.String(length=255),
            nullable=False,
            comment="Reference to conversation_contexts.conversation_id",
        ),
        # Message content
        sa.Column(
            "sender_type",
            sender_type_enum,
            nullable=False,
            comment="Who sent the message: user, assistant, or system",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="Message content",
        ),
        sa.Column(
            "agent_name",
            sa.String(length=100),
            nullable=True,
            comment="Name of agent that generated response (for assistant messages)",
        ),
        # Extra message data
        sa.Column(
            "extra_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Additional message data (intent, confidence, etc.)",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["core.conversation_contexts.conversation_id"],
            ondelete="CASCADE",
        ),
        schema="core",
    )

    # Create indexes for conversation_messages
    op.create_index(
        "idx_conv_msg_conversation_id",
        "conversation_messages",
        ["conversation_id"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_conv_msg_created_at",
        "conversation_messages",
        ["created_at"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "idx_conv_msg_sender_type",
        "conversation_messages",
        ["sender_type"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema - remove conversation history tables."""
    # Drop indexes for conversation_messages
    op.drop_index("idx_conv_msg_sender_type", table_name="conversation_messages", schema="core")
    op.drop_index("idx_conv_msg_created_at", table_name="conversation_messages", schema="core")
    op.drop_index("idx_conv_msg_conversation_id", table_name="conversation_messages", schema="core")

    # Drop conversation_messages table
    op.drop_table("conversation_messages", schema="core")

    # Drop indexes for conversation_contexts
    op.drop_index("idx_conv_ctx_organization", table_name="conversation_contexts", schema="core")
    op.drop_index("idx_conv_ctx_last_activity", table_name="conversation_contexts", schema="core")
    op.drop_index("idx_conv_ctx_user_phone_org", table_name="conversation_contexts", schema="core")
    op.drop_index("idx_conv_ctx_conversation_id", table_name="conversation_contexts", schema="core")

    # Drop conversation_contexts table
    op.drop_table("conversation_contexts", schema="core")

    # Drop ENUM
    op.execute("DROP TYPE IF EXISTS sender_type_enum")
