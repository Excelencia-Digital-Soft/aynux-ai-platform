"""
Embedding Update Service - Product Embedding Management (pgvector)

This service handles generation and synchronization of vector embeddings for
products using pgvector (PostgreSQL).

Responsibilities:
- Generate embeddings for products using Ollama (nomic-embed-text)
- Sync embeddings to pgvector (PostgreSQL)
- Provide statistics and health check methods
"""

import logging
from datetime import UTC, datetime
from typing import Any

from langchain_ollama import OllamaEmbeddings
from sqlalchemy import func, select, text

from app.config.settings import get_settings
from app.database.async_db import get_async_db
from app.models.db import Product

logger = logging.getLogger(__name__)


class EmbeddingUpdateService:
    """
    Service for managing product vector embeddings using pgvector.

    Handles embedding generation and synchronization to PostgreSQL pgvector.

    Features:
    - Performance: pgvector with HNSW index for fast search
    - Native SQL integration with application data
    - Automatic embedding generation with Ollama
    """

    def __init__(self):
        """
        Initialize the embedding service.
        """
        settings = get_settings()
        self.embedding_model = settings.OLLAMA_API_MODEL_EMBEDDING
        self.embeddings = OllamaEmbeddings(
            model=settings.OLLAMA_API_MODEL_EMBEDDING, base_url=settings.OLLAMA_API_URL
        )

        logger.info(f"EmbeddingUpdateService initialized with model={self.embedding_model} (pgvector)")

    def _create_product_content(self, product: Product) -> str:
        """
        Create searchable content from a Product instance.

        Args:
            product: Product database model

        Returns:
            String content for embedding generation
        """
        content_parts: list[str] = []

        if product.name:
            content_parts.append(str(product.name))

        if product.description:
            content_parts.append(str(product.description))

        if product.sku:
            content_parts.append(f"SKU: {product.sku}")

        return " ".join(content_parts)

    async def generate_embedding(self, text: str, max_chars: int = 6000) -> list[float]:
        """
        Generate embedding vector for a given text.

        Args:
            text: Text to generate embedding for
            max_chars: Maximum characters to use for embedding (default 6000)

        Returns:
            List of floats representing the embedding vector (768 dimensions)
        """
        try:
            # Truncate text if too long to avoid exceeding model's context length
            if len(text) > max_chars:
                logger.warning(
                    f"Text too long ({len(text)} chars), truncating to {max_chars} chars"
                )
                text = text[:max_chars]

            embedding = await self.embeddings.aembed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def update_all_embeddings(self) -> dict[str, Any]:
        """
        Update embeddings for all active products in pgvector.

        Returns:
            Dictionary with update statistics
        """
        total_processed = 0
        successful = 0
        errors = 0
        start_time = datetime.now(UTC).isoformat()
        end_time: str | None = None

        async for db in get_async_db():
            try:
                # Get all active products
                stmt = select(Product).where(Product.active.is_(True))
                result = await db.execute(stmt)
                products = result.scalars().all()

                logger.info(f"Updating pgvector embeddings for {len(products)} products")

                for product in products:
                    total_processed += 1
                    try:
                        # Create content for embedding
                        content = self._create_product_content(product)

                        if not content.strip():
                            logger.warning(f"Empty content for product {product.id}, skipping")
                            continue

                        # Generate embedding
                        embedding = await self.generate_embedding(content)
                        embedding_str = f"[{','.join(str(v) for v in embedding)}]"

                        # Update pgvector (PostgreSQL) - using raw SQL for vector type
                        # Note: Use CAST() instead of :: to avoid asyncpg parameter confusion
                        update_stmt = text(
                            """
                            UPDATE products
                            SET embedding = CAST(:embedding AS vector),
                                updated_at = NOW()
                            WHERE id = :product_id
                        """
                        )
                        await db.execute(
                            update_stmt,
                            {"embedding": embedding_str, "product_id": product.id},
                        )

                        successful += 1

                        if successful % 50 == 0:
                            logger.info(f"Progress: {successful}/{len(products)} embeddings updated")

                    except Exception as e:
                        logger.error(f"Error updating embedding for product {product.id}: {e}")
                        errors += 1
                        continue

                # Commit all updates
                await db.commit()

                end_time = datetime.now(UTC).isoformat()
                logger.info(
                    f"Embedding update completed - "
                    f"Processed: {total_processed}, "
                    f"Successful: {successful}, "
                    f"Errors: {errors}"
                )

            except Exception as e:
                logger.error(f"Error updating product embeddings: {e}")
                await db.rollback()
                errors += 1
                raise

        return {
            "total_processed": total_processed,
            "successful": successful,
            "errors": errors,
            "start_time": start_time,
            "end_time": end_time,
        }

    async def update_product_embedding(self, product_id: int) -> bool:
        """
        Update embedding for a single product.

        Args:
            product_id: ID of the product to update

        Returns:
            True if successful, False otherwise
        """
        async for db in get_async_db():
            try:
                stmt = select(Product).where(Product.id == product_id)
                result = await db.execute(stmt)
                product = result.scalar_one_or_none()

                if not product:
                    logger.warning(f"Product {product_id} not found")
                    return False

                content = self._create_product_content(product)
                if not content.strip():
                    logger.warning(f"Empty content for product {product_id}")
                    return False

                embedding = await self.generate_embedding(content)
                embedding_str = f"[{','.join(str(v) for v in embedding)}]"

                # Note: Use CAST() instead of :: to avoid asyncpg parameter confusion
                update_stmt = text(
                    """
                    UPDATE products
                    SET embedding = CAST(:embedding AS vector),
                        updated_at = NOW()
                    WHERE id = :product_id
                """
                )
                await db.execute(
                    update_stmt,
                    {"embedding": embedding_str, "product_id": product_id},
                )
                await db.commit()

                logger.info(f"Updated embedding for product {product_id}")
                return True

            except Exception as e:
                logger.error(f"Error updating embedding for product {product_id}: {e}")
                await db.rollback()
                return False

        return False

    def get_collection_stats(self) -> dict[str, int]:
        """
        Get statistics about product embeddings.

        Returns:
            Dictionary with collection statistics

        Note:
            This is a synchronous method for compatibility with existing code.
            It returns cached/static data. Use get_embedding_stats_async for real-time data.
        """
        # Return placeholder stats - actual stats should be fetched async
        return {
            "products": 0,  # This would be populated by async method
        }

    async def get_embedding_stats_async(self) -> dict[str, Any]:
        """
        Get detailed statistics about product embeddings.

        Returns:
            Dictionary with embedding statistics
        """
        async for db in get_async_db():
            try:
                # Get total count
                total_stmt = select(func.count(Product.id)).where(Product.active.is_(True))
                total_result = await db.execute(total_stmt)
                total_count = total_result.scalar() or 0

                # Get count with embeddings
                embedded_stmt = select(func.count(Product.id)).where(
                    Product.active.is_(True),
                    Product.embedding.isnot(None),
                )
                embedded_result = await db.execute(embedded_stmt)
                embedded_count = embedded_result.scalar() or 0

                return {
                    "total_products": total_count,
                    "embedded_products": embedded_count,
                    "missing_embeddings": total_count - embedded_count,
                    "embedding_coverage": (embedded_count / total_count * 100) if total_count > 0 else 0,
                    "store_type": "pgvector",
                }

            except Exception as e:
                logger.error(f"Error getting embedding stats: {e}")
                return {}

        return {}


def create_vector_ingestion_service() -> EmbeddingUpdateService:
    """
    Factory function to create an EmbeddingUpdateService instance.

    Returns:
        Configured EmbeddingUpdateService instance
    """
    return EmbeddingUpdateService()
