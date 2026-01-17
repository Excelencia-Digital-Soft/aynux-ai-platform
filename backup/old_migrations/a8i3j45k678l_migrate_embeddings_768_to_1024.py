"""Migrate vector embeddings from 768 to 1024 dimensions.

Migration for switching from nomic-embed-text (768d) to BAAI/bge-m3 (1024d) via Infinity.

Revision ID: a8i3j45k678l
Revises: z7h2i34j567k
Create Date: 2025-01-05

Changes:
- Drop all HNSW indexes on embedding columns
- Clear existing embeddings (data loss accepted - will regenerate)
- Alter all vector columns from 768 to 1024 dimensions
- Recreate HNSW indexes with new dimensions

Tables affected:
- ecommerce.products
- core.agent_knowledge
- core.company_knowledge
- core.tenant_documents
- excelencia.software_modules
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8i3j45k678l"
down_revision: Union[str, None] = "z7h2i34j567k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables with embedding columns and their HNSW indexes
EMBEDDING_TABLES = [
    # (schema, table, index_name_or_None)
    ("ecommerce", "products", "idx_products_embedding_hnsw"),
    ("core", "agent_knowledge", "idx_agent_knowledge_embedding_hnsw"),
    ("core", "company_knowledge", "idx_knowledge_embedding_hnsw"),
    ("core", "tenant_documents", None),  # No HNSW index
    ("excelencia", "software_modules", "idx_software_modules_embedding_hnsw"),
]


def upgrade() -> None:
    """Migrate from 768 to 1024 dimensions."""
    for schema, table, index_name in EMBEDDING_TABLES:
        full_table = f"{schema}.{table}"

        # 1. Drop existing HNSW index if exists
        if index_name:
            op.execute(f"DROP INDEX IF EXISTS {schema}.{index_name}")

        # 2. Clear existing embeddings (data loss accepted - will regenerate)
        op.execute(f"UPDATE {full_table} SET embedding = NULL")

        # 3. Alter column dimension from 768 to 1024
        # Note: With NULL values, this is a metadata-only operation
        op.execute(f"ALTER TABLE {full_table} ALTER COLUMN embedding TYPE vector(1024)")

        # 4. Recreate HNSW index with 1024 dimensions
        if index_name:
            op.execute(f"""
                CREATE INDEX {index_name}
                ON {full_table}
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)

    # Update comments to reflect new embedding model
    op.execute("""
        COMMENT ON COLUMN ecommerce.products.embedding IS
            'Vector embedding (1024-dim) for semantic search using BAAI/bge-m3 via Infinity';
        COMMENT ON COLUMN core.agent_knowledge.embedding IS
            'Vector embedding (1024-dim) for semantic search using BAAI/bge-m3 via Infinity';
        COMMENT ON COLUMN core.company_knowledge.embedding IS
            'Vector embedding (1024-dim) for semantic search using BAAI/bge-m3 via Infinity';
        COMMENT ON COLUMN core.tenant_documents.embedding IS
            'Vector embedding (1024-dim) for semantic search using BAAI/bge-m3 via Infinity';
        COMMENT ON COLUMN excelencia.software_modules.embedding IS
            'Vector embedding (1024-dim) for semantic search using BAAI/bge-m3 via Infinity';
    """)


def downgrade() -> None:
    """Revert to 768 dimensions (data loss - embeddings cleared)."""
    for schema, table, index_name in EMBEDDING_TABLES:
        full_table = f"{schema}.{table}"

        # Drop HNSW index if exists
        if index_name:
            op.execute(f"DROP INDEX IF EXISTS {schema}.{index_name}")

        # Clear embeddings and revert dimension
        op.execute(f"UPDATE {full_table} SET embedding = NULL")
        op.execute(f"ALTER TABLE {full_table} ALTER COLUMN embedding TYPE vector(768)")

        # Recreate index with 768 dimensions
        if index_name:
            op.execute(f"""
                CREATE INDEX {index_name}
                ON {full_table}
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)

    # Revert comments
    op.execute("""
        COMMENT ON COLUMN ecommerce.products.embedding IS
            'Vector embedding (768-dim) for semantic search using nomic-embed-text via Ollama';
        COMMENT ON COLUMN core.agent_knowledge.embedding IS
            'Vector embedding (768-dim) for semantic search using nomic-embed-text via Ollama';
        COMMENT ON COLUMN core.company_knowledge.embedding IS
            'Vector embedding (768-dim) for semantic search using nomic-embed-text via Ollama';
        COMMENT ON COLUMN core.tenant_documents.embedding IS
            'Vector embedding (768-dim) for semantic search using nomic-embed-text via Ollama';
        COMMENT ON COLUMN excelencia.software_modules.embedding IS
            'Vector embedding (768-dim) for semantic search using nomic-embed-text via Ollama';
    """)
