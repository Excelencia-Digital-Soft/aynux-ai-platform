"""
PgVector Integration (Facade).

Provides backward-compatible facade that delegates to specialized components.
This is the main entry point for pgvector functionality.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.langsmith_config import trace_integration
from app.config.settings import get_settings
from app.integrations.llm import TEIEmbeddingModel
from app.integrations.vector_stores.pgvector.embedding_manager import (
    EmbeddingTextBuilder,
    ProductEmbeddingManager,
)
from app.integrations.vector_stores.pgvector.search import PgVectorProductSearch
from app.integrations.vector_stores.pgvector_metrics_service import get_metrics_service
from app.models.db import Product

logger = logging.getLogger(__name__)


class PgVectorIntegration:
    """
    PostgreSQL pgvector integration for semantic search.

    This facade delegates to specialized components:
    - PgVectorProductSearch: Vector similarity search
    - ProductEmbeddingManager: Embedding generation and updates
    - EmbeddingTextBuilder: Text preparation for embeddings

    Follows SRP by delegating to specialized components.
    """

    def __init__(self, embedder: TEIEmbeddingModel | None = None):
        """
        Initialize pgvector integration.

        Args:
            embedder: TEIEmbeddingModel instance for embedding generation
        """
        settings = get_settings()
        self.embedder = embedder or TEIEmbeddingModel()
        self.metrics = get_metrics_service()

        # Configuration (exposed for compatibility)
        self.embedding_model = settings.TEI_MODEL
        self.embedding_dimensions = settings.TEI_EMBEDDING_DIMENSION
        self.default_similarity_threshold = 0.6
        self.default_k = 10

        # Initialize specialized components
        self._search = PgVectorProductSearch(metrics_service=self.metrics)
        self._embedding_manager = ProductEmbeddingManager(embedder=self.embedder, metrics_service=self.metrics)
        self._text_builder = EmbeddingTextBuilder()

    def _format_vector_for_query(self, vector: list[float]) -> str:
        """Delegate to search component."""
        return self._search.format_vector_for_query(vector)

    @trace_integration("pgvector_search_products")
    async def search_similar_products(
        self,
        query_embedding: list[float],
        k: int = 10,
        metadata_filters: dict[str, Any] | None = None,
        min_similarity: float = 0.7,
        query_text: str | None = None,
    ) -> list[tuple[Product, float]]:
        """Delegate to search component."""
        return await self._search.search_similar_products(
            query_embedding=query_embedding,
            k=k,
            metadata_filters=metadata_filters,
            min_similarity=min_similarity,
            query_text=query_text,
        )

    @trace_integration("pgvector_generate_embedding")
    async def generate_embedding(self, text: str) -> list[float]:
        """Delegate to embedding manager."""
        return await self._embedding_manager.generate_embedding(text)

    @trace_integration("pgvector_update_product_embedding")
    async def update_product_embedding(
        self,
        product_id: UUID,
        db: AsyncSession | None = None,
        force_update: bool = False,
    ) -> bool:
        """Delegate to embedding manager."""
        return await self._embedding_manager.update_product_embedding(
            product_id=product_id, db=db, force_update=force_update
        )

    def _create_embedding_text(self, product: Product) -> str:
        """Delegate to text builder."""
        return self._text_builder.create_embedding_text(product)

    @trace_integration("pgvector_batch_update_embeddings")
    async def batch_update_embeddings(
        self,
        product_ids: list[UUID] | None = None,
        batch_size: int = 50,
        force_update: bool = False,
    ) -> dict[str, int]:
        """Delegate to embedding manager."""
        return await self._embedding_manager.batch_update_embeddings(
            product_ids=product_ids, batch_size=batch_size, force_update=force_update
        )

    async def get_embedding_statistics(self) -> dict[str, Any]:
        """Delegate to embedding manager."""
        return await self._embedding_manager.get_embedding_statistics()

    async def health_check(self) -> bool:
        """Delegate to search component."""
        return await self._search.health_check()

    # Expose helper methods for backward compatibility
    def _expand_product_name_abbreviations(self, name: str, brand_name: str) -> str:
        """Delegate to text builder."""
        return self._text_builder._expand_abbreviations(name, brand_name)

    def _get_brand_context(self, brand_name: str) -> str:
        """Delegate to text builder."""
        return self._text_builder._get_brand_context(brand_name)

    def _is_power_tool_brand(self, brand_name: str) -> bool:
        """Delegate to text builder."""
        return self._text_builder._is_power_tool_brand(brand_name)
