import logging
from typing import Any, Dict, List, Optional

from app.database import get_db_context
from app.models.database import Product, Brand
from app.models.message import Message
from app.services.category_vector_service import CategoryVectorService
from app.services.embedding_update_service import EmbeddingUpdateService
from app.services.product_service import ProductService

logger = logging.getLogger(__name__)


class EnhancedProductService(ProductService):
    """Enhanced product service with vector search capabilities"""

    def __init__(self):
        super().__init__()
        self.embedding_service = EmbeddingUpdateService()
        self.category_service = CategoryVectorService()

    async def hybrid_search_products(
        self,
        query: str,
        conversation_history: List[Message],
        limit: int = 10,
        price_range: Optional[tuple] = None,
        brand_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector similarity and SQL filters
        """
        try:
            # Determine category from context
            category_info = await self.category_service.determine_search_category(query, conversation_history)

            logger.info(f"Category detection: {category_info}")

            # Enhance query for better semantic search
            enhanced_query = await self.category_service.enhance_search_query(query, category_info["category"])

            # Perform vector search
            vector_results = await self.embedding_service.search_products(
                query=enhanced_query,
                category=category_info["category"],
                k=limit * 2,  # Get more results for filtering
            )

            # Get product IDs from vector search
            product_ids = [result["product_id"] for result in vector_results]

            # Apply SQL filters
            filtered_products = []
            if product_ids:
                with get_db_context() as db:
                    query_builder = db.query(Product).filter(Product.id.in_(product_ids))

                    # Apply price range filter
                    if price_range:
                        query_builder = query_builder.filter(
                            Product.price.between(price_range[0], price_range[1])
                        )

                    # Apply brand filter
                    if brand_filter:
                        query_builder = query_builder.join(Brand).filter(Brand.name == brand_filter)

                    # Only active products
                    query_builder = query_builder.filter(Product.active.is_(True))

                    products = query_builder.all()

                    # Merge with vector scores
                    for product in products:
                        # Find corresponding vector result
                        vector_match = next((vr for vr in vector_results if vr["product_id"] == product.id), None)

                        if vector_match:
                            filtered_products.append(
                                {
                                    "product": product,
                                    "similarity_score": vector_match["similarity_score"],
                                    "category": vector_match["category"],
                                    "subcategory": vector_match["subcategory"],
                                }
                            )

            # Sort by similarity score
            filtered_products.sort(key=lambda x: x["similarity_score"])

            # Limit results
            return filtered_products[:limit]

        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            # Fallback to traditional search
            return await self._fallback_search(query, limit, price_range, brand_filter)

    async def _fallback_search(
        self, query: str, limit: int, price_range: Optional[tuple], brand_filter: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Fallback to traditional SQL search"""
        products = await self.search_products(search_term=query, brand_filter=brand_filter, limit=limit)

        # Filter by price if needed
        if price_range:
            products = [p for p in products if price_range[0] <= p.price <= price_range[1]]

        # Convert to expected format
        return [
            {
                "product": p,
                "similarity_score": 1.0,
                "category": p.category.name if p.category else "",
                "subcategory": p.subcategory.name if p.subcategory else "",
            }
            for p in products
        ]

    async def get_similar_products(self, product_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Get products similar to a given product"""
        try:
            # Get the product
            with get_db_context() as db:
                product = db.query(Product).filter(Product.id == product_id).first()

                if not product:
                    return []

                # Create search query from product attributes
                search_query = f"{product.name} {product.specs or ''}"

                # Search for similar products
                similar_results = await self.embedding_service.search_products(
                    query=search_query,
                    category=product.category.name.lower() if product.category else None,
                    k=limit + 1,  # +1 to exclude the product itself
                )

                # Filter out the original product
                similar_results = [r for r in similar_results if r["product_id"] != product_id]

                return similar_results[:limit]

        except Exception as e:
            logger.error(f"Error getting similar products: {str(e)}")
            return []

    async def update_product_embeddings(self, product_id: Optional[int] = None):
        """Update embeddings for products"""
        await self.embedding_service.update_product_embeddings(product_id)

    async def get_embedding_stats(self) -> Dict[str, int]:
        """Get statistics about product embeddings"""
        return self.embedding_service.get_collection_stats()

