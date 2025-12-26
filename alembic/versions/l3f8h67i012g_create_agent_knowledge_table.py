"""create_agent_knowledge_table

Revision ID: l3f8h67i012g
Revises: k2e7g56h901f
Create Date: 2025-12-23

Creates agent_knowledge table for per-agent document storage with:
- Vector embeddings for semantic search (pgvector, 768 dims)
- Full-text search support (TSVECTOR)
- HNSW index for fast similarity search
- Flexible metadata storage (JSONB)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l3f8h67i012g"
down_revision: Union[str, Sequence[str], None] = "k2e7g56h901f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_knowledge table."""

    # Create the table
    op.create_table(
        "agent_knowledge",
        # Primary key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique document identifier",
        ),
        # Agent association
        sa.Column(
            "agent_key",
            sa.String(100),
            nullable=False,
            comment="Agent this knowledge belongs to (e.g., 'support_agent')",
        ),
        # Document content
        sa.Column(
            "title",
            sa.String(500),
            nullable=False,
            comment="Document title",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="Full document content in markdown/plain text",
        ),
        # Categorization
        sa.Column(
            "document_type",
            sa.String(50),
            nullable=False,
            server_default="general",
            comment="Type of document (faq, guide, manual, etc.)",
        ),
        sa.Column(
            "category",
            sa.String(200),
            nullable=True,
            comment="Secondary category for finer classification",
        ),
        sa.Column(
            "tags",
            ARRAY(sa.String),
            nullable=True,
            server_default="{}",
            comment="Tags for flexible categorization and filtering",
        ),
        # Metadata
        sa.Column(
            "meta_data",
            JSONB,
            nullable=True,
            server_default="{}",
            comment="Flexible metadata (source_filename, page_count, author, etc.)",
        ),
        # Status
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
            comment="Whether this document is active and searchable",
        ),
        # Note: embedding column created via raw SQL after table creation
        # Full-text search
        sa.Column(
            "search_vector",
            TSVECTOR,
            nullable=True,
            comment="Full-text search vector (auto-generated from title + content)",
        ),
        # Sort order
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Order for displaying documents (lower = first)",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )

    # Add embedding column as vector(768) type using raw SQL
    op.execute(
        """
        ALTER TABLE core.agent_knowledge
        ADD COLUMN embedding vector(768)
        """
    )

    # Create indexes
    # Primary index for agent queries
    op.create_index(
        "idx_agent_knowledge_agent_key",
        "agent_knowledge",
        ["agent_key"],
        schema="core",
    )

    # Composite indexes for common query patterns
    op.create_index(
        "idx_agent_knowledge_agent_active",
        "agent_knowledge",
        ["agent_key", "active"],
        schema="core",
    )

    op.create_index(
        "idx_agent_knowledge_agent_type",
        "agent_knowledge",
        ["agent_key", "document_type"],
        schema="core",
    )

    op.create_index(
        "idx_agent_knowledge_type_active",
        "agent_knowledge",
        ["document_type", "active"],
        schema="core",
    )

    op.create_index(
        "idx_agent_knowledge_active",
        "agent_knowledge",
        ["active"],
        schema="core",
    )

    # HNSW index for fast vector similarity search
    op.execute(
        """
        CREATE INDEX idx_agent_knowledge_embedding_hnsw
        ON core.agent_knowledge
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # GIN index for full-text search
    op.execute(
        """
        CREATE INDEX idx_agent_knowledge_search_vector
        ON core.agent_knowledge
        USING gin (search_vector)
        """
    )

    # GIN index for tags array
    op.execute(
        """
        CREATE INDEX idx_agent_knowledge_tags
        ON core.agent_knowledge
        USING gin (tags)
        """
    )

    # Create trigger for auto-updating search_vector
    op.execute(
        """
        CREATE OR REPLACE FUNCTION core.agent_knowledge_search_vector_trigger()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('spanish', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('spanish', COALESCE(NEW.content, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    op.execute(
        """
        CREATE TRIGGER agent_knowledge_search_vector_update
        BEFORE INSERT OR UPDATE ON core.agent_knowledge
        FOR EACH ROW
        EXECUTE FUNCTION core.agent_knowledge_search_vector_trigger()
        """
    )

    # Create trigger for auto-updating updated_at
    op.execute(
        """
        CREATE OR REPLACE FUNCTION core.agent_knowledge_updated_at_trigger()
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
        CREATE TRIGGER agent_knowledge_updated_at_update
        BEFORE UPDATE ON core.agent_knowledge
        FOR EACH ROW
        EXECUTE FUNCTION core.agent_knowledge_updated_at_trigger()
        """
    )


def downgrade() -> None:
    """Drop agent_knowledge table and related objects."""

    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS agent_knowledge_updated_at_update ON core.agent_knowledge")
    op.execute("DROP TRIGGER IF EXISTS agent_knowledge_search_vector_update ON core.agent_knowledge")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS core.agent_knowledge_updated_at_trigger()")
    op.execute("DROP FUNCTION IF EXISTS core.agent_knowledge_search_vector_trigger()")

    # Drop indexes (op.drop_index for those created with op.create_index)
    op.drop_index("idx_agent_knowledge_agent_key", table_name="agent_knowledge", schema="core")
    op.drop_index("idx_agent_knowledge_agent_active", table_name="agent_knowledge", schema="core")
    op.drop_index("idx_agent_knowledge_agent_type", table_name="agent_knowledge", schema="core")
    op.drop_index("idx_agent_knowledge_type_active", table_name="agent_knowledge", schema="core")
    op.drop_index("idx_agent_knowledge_active", table_name="agent_knowledge", schema="core")

    # Drop indexes created with raw SQL
    op.execute("DROP INDEX IF EXISTS core.idx_agent_knowledge_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS core.idx_agent_knowledge_search_vector")
    op.execute("DROP INDEX IF EXISTS core.idx_agent_knowledge_tags")

    # Drop table
    op.drop_table("agent_knowledge", schema="core")
