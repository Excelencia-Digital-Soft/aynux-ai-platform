"""
ChromaDB search strategy using vector similarity.

Implements semantic search using ChromaDB with embedding-based similarity.
"""

from typing import Any, Dict, List, Tuple, cast

from langchain_core.documents import Document

from app.agents.integrations.chroma_integration import ChromaDBIntegration

from ..models import SearchResult, UserIntent
from .base_strategy import BaseSearchStrategy


class ChromaDBSearchStrategy(BaseSearchStrategy):
    """
    Search strategy using ChromaDB for semantic similarity search.

    Applies SOLID principles:
    - SRP: Focuses solely on ChromaDB search operations
    - OCP: Extensible through configuration without modification
    - LSP: Fully substitutable with other search strategies
    - DIP: Depends on ChromaDBIntegration abstraction
    """

    def __init__(self, chroma: ChromaDBIntegration, collection_name: str, config: Dict[str, Any]):
        """
        Initialize ChromaDB search strategy.

        Args:
            chroma: ChromaDBIntegration instance for vector operations
            collection_name: Name of ChromaDB collection to search
            config: Strategy configuration including:
                - similarity_threshold: float (0.0-1.0, default 0.5)
                - max_results: int (default 10)
        """
        super().__init__(config)
        self.chroma = chroma
        self.collection_name = collection_name

        # Configuration with defaults
        self.similarity_threshold = config.get("similarity_threshold", 0.5)
        self.max_results = config.get("max_results", 10)
        self.priority = 30  # Medium priority for vector search fallback

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "chroma"

    @property
    def name(self) -> str:
        """Return strategy name (alias for strategy_name)."""
        return self.strategy_name

    async def search(self, query: str, intent: UserIntent, max_results: int) -> SearchResult:
        """
        Execute ChromaDB semantic search.

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
            self.logger.debug(f"ChromaDB query: '{semantic_query}'")

            # Perform semantic search with scores
            results = await self.chroma.search_similar(
                collection_name=self.collection_name,
                query=semantic_query,
                k=max_results,
                include_scores=True,
            )

            # Cast to correct type since include_scores=True returns tuples
            results = cast(List[Tuple[Document, float]], results)

            if not results:
                self.logger.info("No results from ChromaDB")
                return SearchResult(
                    success=True,
                    products=[],
                    source=self.strategy_name,
                    metadata={"query": semantic_query, "total_results": 0},
                )

            # Process results and extract products
            products = []
            similarities = []

            for result in results:
                try:
                    # Unpack tuple (Document, score)
                    if isinstance(result, tuple) and len(result) == 2:
                        doc, score = result
                    else:
                        self.logger.warning(f"Unexpected result format: {type(result)}")
                        continue

                    # Extract product from document metadata
                    product = doc.metadata.copy() if hasattr(doc, "metadata") else {}

                    if product:
                        # Add similarity score
                        product["similarity_score"] = float(score)
                        products.append(product)
                        similarities.append(float(score))

                except Exception as e:
                    self.logger.warning(f"Error processing ChromaDB result: {str(e)}")
                    continue

            # Filter by similarity threshold
            filtered_products = [p for p in products if p.get("similarity_score", 0.0) >= self.similarity_threshold]

            # Build result metadata
            result_metadata = {
                "query": semantic_query,
                "total_results": len(filtered_products),
                "avg_similarity": sum(similarities) / len(similarities) if similarities else 0.0,
                "min_similarity": min(similarities) if similarities else 0.0,
                "max_similarity": max(similarities) if similarities else 0.0,
                "similarity_threshold": self.similarity_threshold,
                "filtered_count": len(products) - len(filtered_products),
            }

            result = SearchResult(
                success=True,
                products=filtered_products,
                source=self.strategy_name,
                metadata=result_metadata,
            )

            self._log_search_result(result)
            return result

        except Exception as e:
            self.logger.error(f"ChromaDB search failed: {str(e)}")
            return SearchResult(
                success=False,
                products=[],
                source=self.strategy_name,
                error=str(e),
            )

    async def health_check(self) -> bool:
        """
        Check if ChromaDB is operational.

        Returns:
            True if ChromaDB collection is accessible
        """
        try:
            # Test collection access with minimal query
            results = await self.chroma.search_similar(
                collection_name=self.collection_name,
                query="test",
                k=1,
                include_scores=False,
            )

            # ChromaDB is healthy if no exception thrown
            self.logger.debug(f"ChromaDB health check passed {results}")
            return True

        except Exception as e:
            self.logger.warning(f"ChromaDB health check failed: {str(e)}")
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
