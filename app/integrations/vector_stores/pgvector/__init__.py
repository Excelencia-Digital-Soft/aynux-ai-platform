"""
PgVector Module.

This module provides PostgreSQL pgvector integration for semantic search.

Components:
- PgVectorStore: IVectorStore implementation
- PgVectorIntegration: Product-specific integration facade
- PgVectorProductSearch: Vector similarity search for products
- ProductEmbeddingManager: Embedding generation and updates
- EmbeddingTextBuilder: Text preparation for embeddings
"""

from app.integrations.vector_stores.pgvector.embedding_manager import (
    EmbeddingTextBuilder,
    ProductEmbeddingManager,
)
from app.integrations.vector_stores.pgvector.pgvector_integration import (
    PgVectorIntegration,
)
from app.integrations.vector_stores.pgvector.search import PgVectorProductSearch
from app.integrations.vector_stores.pgvector.store import PgVectorStore

__all__ = [
    "PgVectorStore",
    "PgVectorIntegration",
    "PgVectorProductSearch",
    "ProductEmbeddingManager",
    "EmbeddingTextBuilder",
]
