"""
Search Products Use Case

Use case for searching products using semantic search and filters.
Follows Clean Architecture and SOLID principles.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.interfaces.repository import ISearchableRepository
from app.core.interfaces.vector_store import IVectorStore
from app.core.interfaces.llm import ILLM

logger = logging.getLogger(__name__)


@dataclass
class SearchProductsRequest:
    """Request for product search"""

    query: str
    category: Optional[str] = None
    brand: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    limit: int = 10
    use_semantic_search: bool = True


@dataclass
class SearchProductsResponse:
    """Response from product search"""

    products: List[Dict[str, Any]]
    total_count: int
    search_method: str  # 'semantic', 'database', 'hybrid'
    metadata: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class SearchProductsUseCase:
    """
    Use case for searching products.

    Single Responsibility: Only handles product search logic
    Dependency Inversion: Depends on interfaces, not implementations
    """

    def __init__(
        self,
        product_repository: ISearchableRepository,
        vector_store: IVectorStore,
        llm: Optional[ILLM] = None,
    ):
        """
        Initialize use case with dependencies.

        Args:
            product_repository: Repository for product data access
            vector_store: Vector store for semantic search
            llm: Optional LLM for query enhancement
        """
        self.product_repo = product_repository
        self.vector_store = vector_store
        self.llm = llm

    async def execute(self, request: SearchProductsRequest) -> SearchProductsResponse:
        """
        Execute product search use case.

        Args:
            request: Search request parameters

        Returns:
            Search response with products
        """
        try:
            # Strategy 1: Semantic search if enabled
            if request.use_semantic_search:
                semantic_result = await self._semantic_search(request)
                if semantic_result and len(semantic_result.products) >= 2:
                    logger.info(f"Semantic search returned {len(semantic_result.products)} products")
                    return semantic_result

            # Strategy 2: Database search (fallback)
            database_result = await self._database_search(request)
            logger.info(f"Database search returned {len(database_result.products)} products")
            return database_result

        except Exception as e:
            logger.error(f"Error in search products use case: {e}", exc_info=True)
            return SearchProductsResponse(
                products=[],
                total_count=0,
                search_method="error",
                metadata={"error": str(e)},
                success=False,
                error=str(e),
            )

    async def _semantic_search(
        self, request: SearchProductsRequest
    ) -> Optional[SearchProductsResponse]:
        """
        Perform semantic search using vector store.

        Args:
            request: Search request

        Returns:
            Search response or None if failed
        """
        try:
            # Enhance query with LLM if available
            enhanced_query = request.query
            if self.llm:
                enhanced_query = await self._enhance_query(request.query, request.category)

            # Build filter metadata
            filter_metadata = {}
            if request.category:
                filter_metadata["category"] = request.category
            if request.brand:
                filter_metadata["brand"] = request.brand
            if request.min_price is not None or request.max_price is not None:
                filter_metadata["price_range"] = {
                    "min": request.min_price,
                    "max": request.max_price,
                }

            # Perform vector search
            results = await self.vector_store.search(
                query=enhanced_query,
                top_k=request.limit,
                filter_metadata=filter_metadata if filter_metadata else None,
            )

            if not results:
                return None

            # Convert vector results to product dicts
            products = []
            for result in results:
                product_data = result.document.metadata or {}
                product_data["_similarity_score"] = result.score
                products.append(product_data)

            return SearchProductsResponse(
                products=products,
                total_count=len(products),
                search_method="semantic",
                metadata={
                    "enhanced_query": enhanced_query,
                    "original_query": request.query,
                    "min_score": min(r.score for r in results) if results else 0,
                    "max_score": max(r.score for r in results) if results else 0,
                },
                success=True,
            )

        except Exception as e:
            logger.error(f"Error in semantic search: {e}", exc_info=True)
            return None

    async def _database_search(
        self, request: SearchProductsRequest
    ) -> SearchProductsResponse:
        """
        Perform traditional database search.

        Args:
            request: Search request

        Returns:
            Search response
        """
        try:
            # Build filters
            filters = {}
            if request.category:
                filters["category"] = request.category
            if request.brand:
                filters["brand"] = request.brand
            if request.min_price is not None:
                filters["min_price"] = request.min_price
            if request.max_price is not None:
                filters["max_price"] = request.max_price

            # Search using repository
            products = await self.product_repo.search(
                query=request.query,
                filters=filters,
                limit=request.limit,
            )

            # Convert ORM models to dicts
            product_dicts = [self._product_to_dict(p) for p in products]

            return SearchProductsResponse(
                products=product_dicts,
                total_count=len(product_dicts),
                search_method="database",
                metadata={
                    "filters": filters,
                    "query": request.query,
                },
                success=True,
            )

        except Exception as e:
            logger.error(f"Error in database search: {e}", exc_info=True)
            return SearchProductsResponse(
                products=[],
                total_count=0,
                search_method="database",
                metadata={"error": str(e)},
                success=False,
                error=str(e),
            )

    async def _enhance_query(self, query: str, category: Optional[str]) -> str:
        """
        Enhance search query using LLM.

        Args:
            query: Original query
            category: Optional category context

        Returns:
            Enhanced query
        """
        if not self.llm:
            return query

        try:
            prompt = f"""Enhance this product search query for better semantic search:

Query: "{query}"
Category: {category if category else "Any"}

Generate an enhanced version that includes:
- Synonyms
- Related terms
- Technical specifications if applicable

Return ONLY the enhanced query, no explanations."""

            enhanced = await self.llm.generate(prompt, temperature=0.3, max_tokens=100)
            return enhanced.strip()

        except Exception as e:
            logger.warning(f"Could not enhance query: {e}")
            return query

    def _product_to_dict(self, product: Any) -> Dict[str, Any]:
        """
        Convert product model to dictionary.

        Args:
            product: Product model (SQLAlchemy or dict)

        Returns:
            Product as dictionary
        """
        if isinstance(product, dict):
            return product

        # Convert SQLAlchemy model to dict
        return {
            "id": product.id,
            "name": product.name,
            "description": getattr(product, "description", None),
            "price": product.price,
            "stock": product.stock,
            "category": product.category.display_name if product.category else None,
            "brand": product.brand.name if product.brand else None,
            "specs": getattr(product, "specs", None),
            "featured": getattr(product, "featured", False),
            "on_sale": getattr(product, "on_sale", False),
            "active": getattr(product, "active", True),
        }
