"""
PgVector Module.

PostgreSQL pgvector integration for semantic search.

Components:
- PgVectorStore: IVectorStore implementation (CRUD + search orchestration)
- PgVectorMetrics: Metrics collection for vector operations
- PgVectorProductSearch: Vector similarity search for products
- ProductEmbeddingManager: Embedding generation and updates
- EmbeddingTextBuilder: Text preparation for embeddings
- PgVectorIntegration: Product-specific integration facade
- vector_helpers: Vector formatting utilities
"""

from app.integrations.vector_stores.pgvector.embedding_manager import (
    EmbeddingTextBuilder,
    ProductEmbeddingManager,
)
from app.integrations.vector_stores.pgvector.metrics import PgVectorMetrics
from app.integrations.vector_stores.pgvector.pgvector_integration import (
    PgVectorIntegration,
)
from app.integrations.vector_stores.pgvector.search import PgVectorProductSearch
from app.integrations.vector_stores.pgvector.search_engine import PgVectorSearchEngine
from app.integrations.vector_stores.pgvector.store import PgVectorStore
from app.integrations.vector_stores.pgvector.vector_helpers import (
    format_vector_for_query,
    vector_from_string,
)

__all__ = [
    # Core store
    "PgVectorStore",
    "PgVectorMetrics",
    # Search
    "PgVectorProductSearch",
    "PgVectorSearchEngine",
    # Embeddings
    "ProductEmbeddingManager",
    "EmbeddingTextBuilder",
    # Integration
    "PgVectorIntegration",
    # Helpers
    "format_vector_for_query",
    "vector_from_string",
]
