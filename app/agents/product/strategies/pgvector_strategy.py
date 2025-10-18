"""
PgVector search strategy using PostgreSQL vector similarity.

Implements semantic search using pgvector extension with embedding-based similarity.
"""

import logging
from typing import Any, Dict

from app.agents.integrations.pgvector_integration import PgVectorIntegration

from ..models import SearchResult, UserIntent
from .base_strategy import BaseSearchStrategy


class PgVectorSearchStrategy(BaseSearchStrategy):
    """
    Search strategy using PostgreSQL pgvector for semantic similarity search.

    Applies SOLID principles:
    - SRP: Focuses solely on pgvector search operations
    - OCP: Extensible through configuration without modification
    - LSP: Fully substitutable with other search strategies
    - DIP: Depends on PgVectorIntegration abstraction
    """

    def __init__(self, pgvector: PgVectorIntegration, config: Dict[str, Any]):
        """
        Initialize pgvector search strategy.

        Args:
            pgvector: PgVectorIntegration instance for vector operations
            config: Strategy configuration including:
                - similarity_threshold: float (0.0-1.0, default 0.7)
                - max_results: int (default 10)
                - stock_required: bool (default True)
        """
        super().__init__(config)
        self.pgvector = pgvector

        # Configuration with defaults
        self.similarity_threshold = config.get("similarity_threshold", 0.7)
        self.max_results = config.get("max_results", 10)
        self.stock_required = config.get("stock_required", True)
        self.priority = 10  # Highest priority for semantic search

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "pgvector"

    @property
    def name(self) -> str:
        """Return strategy name (alias for strategy_name)."""
        return self.strategy_name

    async def search(self, query: str, intent: UserIntent, max_results: int) -> SearchResult:
        """
        Execute pgvector semantic search.

        Args:
            query: User's natural language query
            intent: Analyzed user intent with structured data
            max_results: Maximum number of products to return

        Returns:
            SearchResult with products and metadata
        """
        self._log_search_start(query, intent, max_results)

        try:
            # Build semantic search query from intent
            semantic_query = self._build_semantic_query(query, intent)
            self.logger.debug(f"Semantic query: '{semantic_query}'")

            # Generate query embedding
            query_embedding = await self.pgvector.generate_embedding(semantic_query)

            # Build metadata filters
            metadata_filters = self._build_metadata_filters(intent)

            # Execute vector similarity search
            search_results = await self.pgvector.search_similar_products(
                query_embedding=query_embedding,
                k=max_results,
                min_similarity=self.similarity_threshold,
                metadata_filters=metadata_filters,
                query_text=query,
            )

            # Extract products and metadata
            # search_results is List[Tuple[Product, float]]
            products = []
            similarities = []

            for product, similarity in search_results:
                # Convert Product ORM object to dictionary
                product_data = {
                    "id": str(product.id),
                    "name": product.name,
                    "price": float(product.price),
                    "stock": product.stock,
                    "description": product.description,
                    "short_description": product.short_description,
                    "specs": product.specs,
                    "model": product.model,
                    "sku": product.sku,
                    "category": product.category.display_name if product.category else None,
                    "category_id": str(product.category_id) if product.category_id else None,
                    "brand": product.brand.name if product.brand else None,
                    "brand_id": str(product.brand_id) if product.brand_id else None,
                    "image_url": product.image_url,
                    "featured": product.featured,
                    "on_sale": product.on_sale,
                    "similarity_score": float(similarity)
                }
                products.append(product_data)
                similarities.append(similarity)

            # Build result metadata
            result_metadata = {
                "query": semantic_query,
                "total_results": len(products),
                "avg_similarity": sum(similarities) / len(similarities) if similarities else 0.0,
                "min_similarity": min(similarities) if similarities else 0.0,
                "max_similarity": max(similarities) if similarities else 0.0,
                "similarity_threshold": self.similarity_threshold,
            }

            result = SearchResult(
                success=True,
                products=products,
                source=self.strategy_name,
                metadata=result_metadata,
            )

            self._log_search_result(result)
            return result

        except Exception as e:
            self.logger.error(f"pgvector search failed: {str(e)}")
            return SearchResult(
                success=False,
                products=[],
                source=self.strategy_name,
                error=str(e),
            )

    async def health_check(self) -> bool:
        """
        Check if pgvector is operational.

        Returns:
            True if pgvector can generate embeddings and search
        """
        try:
            # Test embedding generation
            test_embedding = await self.pgvector.generate_embedding("test")
            if not test_embedding or len(test_embedding) == 0:
                return False

            # pgvector is healthy
            self.logger.debug("pgvector health check passed")
            return True

        except Exception as e:
            self.logger.warning(f"pgvector health check failed: {str(e)}")
            return False

    def _build_semantic_query(self, query: str, intent: UserIntent) -> str:
        """
        Build semantic search query from user intent.

        Args:
            query: Original user query
            intent: Analyzed user intent

        Returns:
            Optimized semantic search query
        """
        query_parts = []

        # Prioritize specific product if mentioned
        if intent.specific_product:
            query_parts.append(f"product: {intent.specific_product}")
        elif intent.search_terms:
            query_parts.append(" ".join(intent.search_terms))

        # Add category context
        if intent.category:
            query_parts.append(f"category: {intent.category}")

        # Add brand context
        if intent.brand:
            query_parts.append(f"brand: {intent.brand}")

        # Fallback to original query if no structured terms
        return " ".join(query_parts) if query_parts else query

    def _build_metadata_filters(self, intent: UserIntent) -> Dict[str, Any]:
        """
        Build metadata filters from user intent.

        Args:
            intent: User intent with filter preferences

        Returns:
            Metadata filters for search
        """
        filters = {}

        # Stock filter
        if intent.wants_stock_info or self.stock_required:
            filters["stock_required"] = True

        # Featured products filter
        if intent.wants_featured:
            filters["featured"] = True

        # Sale/discount filter
        if intent.wants_sale:
            filters["on_sale"] = True

        return filters