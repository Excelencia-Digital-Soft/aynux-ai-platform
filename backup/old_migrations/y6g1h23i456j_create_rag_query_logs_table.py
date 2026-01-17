"""create_rag_query_logs_table

Revision ID: y6g1h23i456j
Revises: x5f0g12h345i
Create Date: 2025-12-31

Creates rag_query_logs table for RAG analytics with:
- Query and response logging
- Performance metrics (latency, token count)
- Quality metrics (relevance score, user feedback)
- Agent association for per-agent analytics
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "y6g1h23i456j"
down_revision: Union[str, Sequence[str], None] = "x5f0g12h345i"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create rag_query_logs table."""

    # Create the table
    op.create_table(
        "rag_query_logs",
        # Primary key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique query log identifier",
        ),
        # Query content
        sa.Column(
            "query",
            sa.Text(),
            nullable=False,
            comment="User query text that was searched",
        ),
        # Context used for response generation
        sa.Column(
            "context_used",
            JSONB,
            nullable=True,
            server_default="[]",
            comment="Document titles/IDs used as RAG context",
        ),
        # Response
        sa.Column(
            "response",
            sa.Text(),
            nullable=True,
            comment="Generated response text",
        ),
        # Performance metrics
        sa.Column(
            "token_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Tokens used in response generation",
        ),
        sa.Column(
            "latency_ms",
            sa.Float(),
            nullable=False,
            server_default="0.0",
            comment="Search latency in milliseconds",
        ),
        # Quality metrics
        sa.Column(
            "relevance_score",
            sa.Float(),
            nullable=True,
            comment="Average relevance score of retrieved documents (0-1)",
        ),
        sa.Column(
            "user_feedback",
            sa.String(20),
            nullable=True,
            comment="User feedback: 'positive' or 'negative'",
        ),
        # Agent association
        sa.Column(
            "agent_key",
            sa.String(100),
            nullable=True,
            comment="Agent that performed the search (e.g., 'support_agent')",
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
        schema="core",
    )

    # Create indexes
    # Index for time-based queries (analytics dashboards)
    op.create_index(
        "idx_rag_query_logs_created_at",
        "rag_query_logs",
        ["created_at"],
        schema="core",
    )

    # Index for agent-specific analytics
    op.create_index(
        "idx_rag_query_logs_agent_key",
        "rag_query_logs",
        ["agent_key"],
        schema="core",
    )

    # Composite index for agent + time queries
    op.create_index(
        "idx_rag_query_logs_agent_created",
        "rag_query_logs",
        ["agent_key", "created_at"],
        schema="core",
    )

    # Partial index for feedback analysis (only when feedback exists)
    op.execute(
        """
        CREATE INDEX idx_rag_query_logs_feedback
        ON core.rag_query_logs (user_feedback)
        WHERE user_feedback IS NOT NULL
        """
    )

    # Create trigger for auto-updating updated_at
    op.execute(
        """
        CREATE OR REPLACE FUNCTION core.rag_query_logs_updated_at_trigger()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    op.execute(
        """
        CREATE TRIGGER rag_query_logs_updated_at_update
        BEFORE UPDATE ON core.rag_query_logs
        FOR EACH ROW
        EXECUTE FUNCTION core.rag_query_logs_updated_at_trigger()
        """
    )


def downgrade() -> None:
    """Drop rag_query_logs table and related objects."""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS rag_query_logs_updated_at_update ON core.rag_query_logs")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS core.rag_query_logs_updated_at_trigger()")

    # Drop indexes created with op.create_index
    op.drop_index("idx_rag_query_logs_created_at", table_name="rag_query_logs", schema="core")
    op.drop_index("idx_rag_query_logs_agent_key", table_name="rag_query_logs", schema="core")
    op.drop_index("idx_rag_query_logs_agent_created", table_name="rag_query_logs", schema="core")

    # Drop partial index created with raw SQL
    op.execute("DROP INDEX IF EXISTS core.idx_rag_query_logs_feedback")

    # Drop table
    op.drop_table("rag_query_logs", schema="core")
