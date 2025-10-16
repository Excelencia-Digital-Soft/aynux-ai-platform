"""
PostgreSQL pgvector integration for semantic product search.

This module provides native PostgreSQL vector similarity search using pgvector extension,
offering better performance and integration compared to standalone vector databases.

Features:
- Native SQL vector similarity search with metadata filtering
- HNSW/IVFFlat indexing for sub-100ms query performance
- Transactional consistency with product data
- Automatic embedding generation and updates
- Quality metrics and monitoring integration
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.langsmith_config import trace_integration
from app.database.async_db import get_async_db_context
from app.models.db import Brand, Category, Product
from app.services.pgvector_metrics_service import get_metrics_service

from .ollama_integration import OllamaIntegration

logger = logging.getLogger(__name__)


class PgVectorIntegration:
    """
    PostgreSQL pgvector integration for semantic search.

    Uses pgvector extension for efficient vector similarity search with native SQL,
    providing better performance and integration than standalone vector databases.
    """

    def __init__(self, ollama: Optional[OllamaIntegration] = None):
        """
        Initialize pgvector integration.

        Args:
            ollama: OllamaIntegration instance for embedding generation
        """
        self.ollama = ollama or OllamaIntegration()

        # Configuration
        self.embedding_model = "nomic-embed-text:v1.5"
        self.embedding_dimensions = 1024
        self.default_similarity_threshold = 0.7  # Higher than ChromaDB for better precision
        self.default_k = 10

        # Metrics service
        self.metrics = get_metrics_service()

    @trace_integration("pgvector_search_products")
    async def search_similar_products(
        self,
        query_embedding: List[float],
        k: int = 10,
        metadata_filters: Optional[Dict[str, Any]] = None,
        min_similarity: float = 0.7,
        query_text: Optional[str] = None,  # For metrics tracking
    ) -> List[Tuple[Product, float]]:
        """
        Search for similar products using vector similarity.

        Args:
            query_embedding: Query vector (1024 dimensions)
            k: Number of results to return
            metadata_filters: Optional filters (category_id, brand_id, price_range, stock_required)
            min_similarity: Minimum similarity threshold (0.0-1.0)
            query_text: Original query text for metrics tracking

        Returns:
            List of (Product, similarity_score) tuples, ordered by similarity descending
        """
        start_time = time.perf_counter()
        error = None
        results = []

        try:
            async with get_async_db_context() as db:
                # Build base query with vector similarity
                query = (
                    select(
                        Product,
                        Category,
                        Brand,
                        # Cosine similarity: 1 - cosine_distance
                        (1 - func.cosine_distance(Product.embedding, query_embedding)).label("similarity"),
                    )
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(
                        and_(
                            Product.embedding.isnot(None),
                            Product.active.is_(True),
                            # Similarity filter
                            (1 - func.cosine_distance(Product.embedding, query_embedding)) >= min_similarity,
                        )
                    )
                )

                # Apply metadata filters if provided
                if metadata_filters:
                    query = self._apply_metadata_filters(query, metadata_filters)

                # Order by similarity and limit results
                query = query.order_by(text("similarity DESC")).limit(k)

                # Execute query
                result = await db.execute(query)
                rows = result.all()

                # Format results as (Product, similarity) tuples
                products_with_scores = []
                for row in rows:
                    product = row[0]  # Product object
                    category = row[1]  # Category object
                    brand = row[2]  # Brand object
                    similarity = float(row[3])  # Similarity score

                    # Attach relationships for convenience
                    product.category = category
                    product.brand = brand

                    products_with_scores.append((product, similarity))

                results = products_with_scores
                logger.info(
                    f"pgvector search found {len(products_with_scores)} products (similarity >= {min_similarity})"
                )

                return products_with_scores

        except Exception as e:
            error = str(e)
            logger.error(f"Error in pgvector search: {e}")
            return []
        finally:
            # Record metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self.metrics.record_search(
                query=query_text or "unknown",
                duration_ms=duration_ms,
                results=results,
                filters_applied=bool(metadata_filters),
                error=error,
            )

    def _apply_metadata_filters(self, query, filters: Dict[str, Any]):
        """
        Apply metadata filters to vector search query.

        Supported filters:
        - category_id: UUID
        - brand_id: UUID
        - price_min: float
        - price_max: float
        - stock_required: bool
        - featured_only: bool
        - on_sale_only: bool
        """
        filter_conditions = []

        # Category filter
        if filters.get("category_id"):
            filter_conditions.append(Product.category_id == filters["category_id"])

        # Brand filter
        if filters.get("brand_id"):
            filter_conditions.append(Product.brand_id == filters["brand_id"])

        # Price range filters
        if filters.get("price_min") is not None:
            filter_conditions.append(Product.price >= filters["price_min"])

        if filters.get("price_max") is not None:
            filter_conditions.append(Product.price <= filters["price_max"])

        # Stock filter
        if filters.get("stock_required", False):
            filter_conditions.append(Product.stock > 0)

        # Featured products only
        if filters.get("featured_only", False):
            filter_conditions.append(Product.featured.is_(True))

        # On sale products only
        if filters.get("on_sale_only", False):
            filter_conditions.append(Product.on_sale.is_(True))

        # Apply all filters
        if filter_conditions:
            query = query.where(and_(*filter_conditions))

        return query

    @trace_integration("pgvector_generate_embedding")
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for given text using Ollama.

        Args:
            text: Text to embed (product description, query, etc.)

        Returns:
            List of floats representing the embedding vector
        """
        try:
            embeddings = self.ollama.get_embeddings(model=self.embedding_model)
            embedding_result = await embeddings.aembed_query(text)

            if len(embedding_result) != self.embedding_dimensions:
                logger.warning(
                    f"Embedding dimension mismatch: got {len(embedding_result)}, expected {self.embedding_dimensions}"
                )

            return embedding_result

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * self.embedding_dimensions

    @trace_integration("pgvector_update_product_embedding")
    async def update_product_embedding(
        self, product_id: UUID, db: Optional[AsyncSession] = None, force_update: bool = False
    ) -> bool:
        """
        Update embedding for a specific product.

        Args:
            product_id: Product UUID
            db: Optional database session (creates new if None)
            force_update: Force update even if embedding exists

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Use provided session or create new one
            if db:
                return await self._update_embedding_impl(product_id, db, force_update)
            else:
                async with get_async_db_context() as new_db:
                    return await self._update_embedding_impl(product_id, new_db, force_update)

        except Exception as e:
            logger.error(f"Error updating product embedding {product_id}: {e}")
            return False

    async def _update_embedding_impl(self, product_id: UUID, db: AsyncSession, force_update: bool) -> bool:
        """Internal implementation of embedding update."""
        start_time = time.perf_counter()
        error = None
        success = False

        try:
            # Fetch product
            result = await db.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()

            if not product:
                error = "Product not found"
                logger.warning(f"Product {product_id} not found")
                return False

            # Skip if embedding exists and not forcing update
            if product.embedding and not force_update:
                logger.debug(f"Product {product_id} already has embedding, skipping")
                return True

            # Generate embedding text from product data
            embedding_text = self._create_embedding_text(product)

            # Generate embedding
            embedding = await self.generate_embedding(embedding_text)

            if not embedding or all(v == 0.0 for v in embedding):
                error = "Failed to generate valid embedding"
                logger.error(f"Failed to generate valid embedding for product {product_id}")
                return False

            # Update product with new embedding
            product.embedding = embedding
            product.last_embedding_update = func.now()
            product.embedding_model = self.embedding_model

            await db.commit()
            logger.info(f"Updated embedding for product {product_id}")

            success = True
            return True

        except Exception as e:
            error = str(e)
            raise
        finally:
            # Record metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self.metrics.record_embedding_operation(
                product_id=str(product_id), operation="update", duration_ms=duration_ms, success=success, error=error
            )

    def _create_embedding_text(self, product: Product) -> str:
        """
        Create comprehensive text representation for embedding generation.

        Combines multiple product fields into single text for better semantic search.

        Args:
            product: Product model instance

        Returns:
            Combined text for embedding
        """
        parts = []

        # Product name (highest weight)
        if product.name:
            parts.append(f"Product: {product.name}")

        # Brand
        if product.brand and hasattr(product.brand, "name"):
            parts.append(f"Brand: {product.brand.name}")

        # Category
        if product.category and hasattr(product.category, "display_name"):
            parts.append(f"Category: {product.category.display_name}")

        # Model
        if product.model:
            parts.append(f"Model: {product.model}")

        # Description
        if product.description:
            # Limit description length
            desc = product.description[:500] if len(product.description) > 500 else product.description
            parts.append(f"Description: {desc}")

        # Specs
        if product.specs:
            specs = product.specs[:300] if len(product.specs) > 300 else product.specs
            parts.append(f"Specifications: {specs}")

        # Technical specs (JSONB)
        if product.technical_specs and isinstance(product.technical_specs, dict):
            specs_text = ", ".join(f"{k}: {v}" for k, v in product.technical_specs.items() if v)
            if specs_text:
                parts.append(f"Technical: {specs_text}")

        # Features (JSONB array)
        if product.features and isinstance(product.features, list):
            features_text = ", ".join(str(f) for f in product.features if f)
            if features_text:
                parts.append(f"Features: {features_text}")

        return ". ".join(parts)

    @trace_integration("pgvector_batch_update_embeddings")
    async def batch_update_embeddings(
        self, product_ids: Optional[List[UUID]] = None, batch_size: int = 50, force_update: bool = False
    ) -> Dict[str, int]:
        """
        Update embeddings for multiple products in batches.

        Args:
            product_ids: Optional list of product UUIDs (None = all products)
            batch_size: Number of products to process per batch
            force_update: Force update even if embeddings exist

        Returns:
            Dictionary with update statistics
        """
        stats = {"total": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            async with get_async_db_context() as db:
                # Build query for products needing embeddings
                query = select(Product.id).where(Product.active.is_(True))

                if product_ids:
                    query = query.where(Product.id.in_(product_ids))
                elif not force_update:
                    # Only products without embeddings
                    query = query.where(Product.embedding.is_(None))

                result = await db.execute(query)
                product_ids_to_update = [row[0] for row in result.all()]

                stats["total"] = len(product_ids_to_update)
                logger.info(f"Starting batch embedding update for {stats['total']} products")

                # Process in batches
                for i in range(0, len(product_ids_to_update), batch_size):
                    batch = product_ids_to_update[i : i + batch_size]

                    for product_id in batch:
                        success = await self.update_product_embedding(product_id, db, force_update)

                        if success:
                            stats["updated"] += 1
                        else:
                            stats["errors"] += 1

                    logger.info(
                        f"Processed batch {i // batch_size + 1}, updated: {stats['updated']}, errors: {stats['errors']}"
                    )

                stats["skipped"] = stats["total"] - stats["updated"] - stats["errors"]

                logger.info(f"Batch embedding update complete: {stats}")
                return stats

        except Exception as e:
            logger.error(f"Error in batch embedding update: {e}")
            stats["errors"] = stats["total"] - stats["updated"]
            return stats

    async def get_embedding_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about product embeddings.

        Returns:
            Dictionary with embedding statistics
        """
        try:
            async with get_async_db_context() as db:
                # Use materialized view if available
                try:
                    result = await db.execute(text("SELECT * FROM product_embedding_stats"))
                    row = result.first()

                    if row:
                        return {
                            "total_products": row[0],
                            "products_with_embeddings": row[1],
                            "missing_embeddings": row[2],
                            "stale_embeddings": row[3],
                            "avg_hours_since_update": float(row[4]) if row[4] else None,
                            "oldest_update": row[5],
                            "newest_update": row[6],
                            "embedding_models_used": row[7],
                        }
                except Exception:
                    # Fallback to direct query if materialized view not available
                    pass

                # Direct query fallback
                total = await db.scalar(select(func.count(Product.id)).where(Product.active.is_(True)))

                with_embeddings = await db.scalar(
                    select(func.count(Product.id)).where(and_(Product.active.is_(True), Product.embedding.isnot(None)))
                )

                missing_embeddings = total - with_embeddings

                return {
                    "total_products": total or 0,
                    "products_with_embeddings": with_embeddings or 0,
                    "missing_embeddings": missing_embeddings,
                    "coverage_percentage": (with_embeddings / total * 100) if total > 0 else 0,
                }

        except Exception as e:
            logger.error(f"Error getting embedding statistics: {e}")
            return {"error": str(e)}

    async def health_check(self) -> bool:
        """
        Check if pgvector is available and working.

        Returns:
            True if pgvector is operational, False otherwise
        """
        try:
            async with get_async_db_context() as db:
                # Check if vector extension is installed
                result = await db.execute(text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"))
                extension_count = result.scalar()

                if extension_count == 0:
                    logger.error("pgvector extension not installed")
                    return False

                # Check if products table has embedding column
                result = await db.execute(
                    text(
                        """
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_name = 'products' AND column_name = 'embedding'
                    """
                    )
                )
                column_count = result.scalar()

                if column_count == 0:
                    logger.error("products.embedding column not found")
                    return False

                # Check if we can perform vector operations
                test_vector = [0.1] * self.embedding_dimensions
                result = await db.execute(
                    select(func.count(Product.id)).where(
                        and_(
                            Product.embedding.isnot(None),
                            (1 - func.cosine_distance(Product.embedding, test_vector)) > 0,
                        )
                    )
                )

                logger.info("pgvector health check passed")
                return True

        except Exception as e:
            logger.error(f"pgvector health check failed: {e}")
            return False
