"""
Product Embedding Manager.

Handles generation and management of product embeddings.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.langsmith_config import trace_integration
from app.database.async_db import get_async_db_context
from app.integrations.llm import OllamaLLM
from app.integrations.vector_stores.pgvector_metrics_service import get_metrics_service
from app.models.db import Product

logger = logging.getLogger(__name__)


class ProductEmbeddingManager:
    """
    Manages product embeddings generation and updates.

    Responsibilities:
    - Generate embeddings using LLM
    - Update product embeddings
    - Batch update operations
    - Get embedding statistics
    """

    def __init__(self, ollama: OllamaLLM | None = None, metrics_service=None):
        """
        Initialize embedding manager.

        Args:
            ollama: OllamaLLM instance for embedding generation
            metrics_service: Optional metrics service
        """
        self.ollama = ollama or OllamaLLM()
        self.metrics = metrics_service or get_metrics_service()
        self.embedding_model = "nomic-embed-text"
        self.embedding_dimensions = 768
        self._text_builder = EmbeddingTextBuilder()

    @trace_integration("pgvector_generate_embedding")
    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for given text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            import asyncio

            embeddings = self.ollama.get_embeddings(model=self.embedding_model)
            embedding_result = await asyncio.to_thread(embeddings.embed_query, text)

            if len(embedding_result) != self.embedding_dimensions:
                logger.warning(f"Embedding dimension mismatch: {len(embedding_result)} vs {self.embedding_dimensions}")

            return embedding_result

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return [0.0] * self.embedding_dimensions

    @trace_integration("pgvector_update_product_embedding")
    async def update_product_embedding(
        self,
        product_id: UUID,
        db: AsyncSession | None = None,
        force_update: bool = False,
    ) -> bool:
        """
        Update embedding for a specific product.

        Args:
            product_id: Product UUID
            db: Optional database session
            force_update: Force update even if embedding exists

        Returns:
            True if update successful
        """
        try:
            if db:
                return await self._update_embedding_impl(product_id, db, force_update)
            else:
                async with get_async_db_context() as new_db:
                    return await self._update_embedding_impl(product_id, new_db, force_update)

        except Exception as e:
            logger.error(f"Error updating product embedding {product_id}: {e}")
            return False

    async def _update_embedding_impl(
        self,
        product_id: UUID,
        db: AsyncSession,
        force_update: bool,
    ) -> bool:
        """Internal implementation of embedding update."""
        start_time = time.perf_counter()
        error = None
        success = False

        try:
            result = await db.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()

            if not product:
                error = "Product not found"
                logger.warning(f"Product {product_id} not found")
                return False

            if product.embedding is not None and not force_update:
                logger.debug(f"Product {product_id} already has embedding")
                return True

            # Generate embedding text and embedding
            embedding_text = self._text_builder.create_embedding_text(product)
            embedding = await self.generate_embedding(embedding_text)

            if not embedding or all(v == 0.0 for v in embedding):
                error = "Failed to generate valid embedding"
                logger.error(f"Failed to generate embedding for {product_id}")
                return False

            # Update product
            product.embedding = embedding  # type: ignore[assignment]
            product.last_embedding_update = datetime.now(UTC)
            product.embedding_model = self.embedding_model

            await db.commit()
            logger.info(f"Updated embedding for product {product_id}")

            success = True
            return True

        except Exception as e:
            error = str(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.record_embedding_operation(
                product_id=str(product_id),
                operation="update",
                duration_ms=duration_ms,
                success=success,
                error=error,
            )

    @trace_integration("pgvector_batch_update_embeddings")
    async def batch_update_embeddings(
        self,
        product_ids: list[UUID] | None = None,
        batch_size: int = 50,
        force_update: bool = False,
    ) -> dict[str, int]:
        """
        Update embeddings for multiple products in batches.

        Args:
            product_ids: Optional list of product UUIDs (None = all)
            batch_size: Products per batch
            force_update: Force update even if embeddings exist

        Returns:
            Dictionary with update statistics
        """
        stats = {"total": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            async with get_async_db_context() as db:
                query = select(Product.id).where(Product.active.is_(True))

                if product_ids:
                    query = query.where(Product.id.in_(product_ids))
                elif not force_update:
                    query = query.where(Product.embedding.is_(None))

                result = await db.execute(query)
                ids_to_update = [row[0] for row in result.all()]

                stats["total"] = len(ids_to_update)
                logger.info(f"Batch update for {stats['total']} products")

                for i in range(0, len(ids_to_update), batch_size):
                    batch = ids_to_update[i : i + batch_size]

                    for pid in batch:
                        success = await self.update_product_embedding(pid, db, force_update)
                        if success:
                            stats["updated"] += 1
                        else:
                            stats["errors"] += 1

                    logger.info(f"Batch {i // batch_size + 1}: {stats['updated']} updated, {stats['errors']} errors")

                stats["skipped"] = stats["total"] - stats["updated"] - stats["errors"]
                logger.info(f"Batch update complete: {stats}")
                return stats

        except Exception as e:
            logger.error(f"Error in batch update: {e}")
            stats["errors"] = stats["total"] - stats["updated"]
            return stats

    async def get_embedding_statistics(self) -> dict[str, Any]:
        """
        Get statistics about product embeddings.

        Returns:
            Dictionary with embedding statistics
        """
        try:
            async with get_async_db_context() as db:
                # Try materialized view first
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
                    pass

                # Direct query fallback
                total = await db.scalar(select(func.count(Product.id)).where(Product.active.is_(True)))
                with_embeddings = await db.scalar(
                    select(func.count(Product.id)).where(and_(Product.active.is_(True), Product.embedding.isnot(None)))
                )

                total_count = total or 0
                with_embeddings_count = with_embeddings or 0

                return {
                    "total_products": total_count,
                    "products_with_embeddings": with_embeddings_count,
                    "missing_embeddings": total_count - with_embeddings_count,
                    "coverage_percentage": (with_embeddings_count / total_count * 100 if total_count > 0 else 0),
                }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"error": str(e)}


class EmbeddingTextBuilder:
    """
    Builds text representations for product embeddings.

    Responsibilities:
    - Create embedding text from product data
    - Expand abbreviations for better semantic understanding
    - Add brand context for disambiguation
    """

    def create_embedding_text(self, product: Product) -> str:
        """
        Create comprehensive text for embedding generation.

        Args:
            product: Product model instance

        Returns:
            Combined text for embedding
        """
        parts = []

        # Get brand name
        brand_name = ""
        if product.brand is not None and hasattr(product.brand, "name"):
            name_value = product.brand.name
            brand_name = str(name_value) if name_value is not None else ""

        # Product name with expansion
        if product.name is not None:
            name_str = str(product.name)
            expanded_name = self._expand_abbreviations(name_str, brand_name)
            parts.append(f"Product: {expanded_name}")

        # Brand with context
        if brand_name:
            brand_context = self._get_brand_context(brand_name)
            parts.append(f"Brand: {brand_name} {brand_context}")

        # Category
        if product.category is not None and hasattr(product.category, "display_name"):
            parts.append(f"Category: {product.category.display_name}")

        # Model
        if product.model is not None:
            parts.append(f"Model: {product.model}")

        # Description
        if product.description is not None:
            desc = str(product.description)[:500]
            parts.append(f"Description: {desc}")

        # Specs
        if product.specs is not None:
            specs = str(product.specs)[:300]
            parts.append(f"Specifications: {specs}")

        # Technical specs
        if product.technical_specs and isinstance(product.technical_specs, dict):
            specs_text = ", ".join(f"{k}: {v}" for k, v in product.technical_specs.items() if v)
            if specs_text:
                parts.append(f"Technical: {specs_text}")

        # Features
        if product.features and isinstance(product.features, list):
            features_text = ", ".join(str(f) for f in product.features if f)
            if features_text:
                parts.append(f"Features: {features_text}")

        return ". ".join(parts)

    def _expand_abbreviations(self, name: str, brand_name: str) -> str:
        """Expand common abbreviations in product names."""
        expanded = name

        abbreviations = {
            "MOTOS.": "motosierra chainsaw power-tool garden-equipment",
            "MOTOG.": "motoguadaña brush-cutter power-tool garden-equipment",
        }

        for abbrev, expansion in abbreviations.items():
            if abbrev in expanded:
                if self._is_power_tool_brand(brand_name):
                    expanded = expanded.replace(abbrev, expansion)
                else:
                    if abbrev == "MOTOS.":
                        expanded = expanded.replace(abbrev, "motosierra")
                    elif abbrev == "MOTOG.":
                        expanded = expanded.replace(abbrev, "motoguadaña")

        # Add motorcycle context
        motorcycle_indicators = ["WAVE", "HONDA", "YAMAHA", "ZANELLA", "MOTOMEL", "BAJAJ"]
        if any(ind in name.upper() for ind in motorcycle_indicators):
            if "motorcycle" not in expanded.lower() and "moto " not in expanded.lower():
                expanded += " motorcycle-part motorcycle-component"

        return expanded

    def _get_brand_context(self, brand_name: str) -> str:
        """Get semantic context for brand."""
        if not brand_name:
            return ""

        brand_upper = brand_name.upper()

        power_tool_brands = {
            "SHINDAIWA": "power-tools garden-equipment chainsaw manufacturer",
            "STIHL": "power-tools garden-equipment chainsaw manufacturer",
            "HUSQVARNA": "power-tools garden-equipment chainsaw manufacturer",
        }

        motorcycle_brands = {
            "CATI-MOTO": "motorcycle-parts motorcycle-components",
            "MOTOMEL": "motorcycle manufacturer motorcycle-parts",
            "ZANELLA": "motorcycle manufacturer motorcycle-parts",
            "HONDA": "motorcycle manufacturer automotive",
            "YAMAHA": "motorcycle manufacturer automotive",
            "BAJAJ": "motorcycle manufacturer automotive",
            "HADA": "motorcycle-parts accessories",
            "THE-ORANGE": "motorcycle-parts accessories",
        }

        for brand_key, context in power_tool_brands.items():
            if brand_key in brand_upper:
                return f"({context})"

        for brand_key, context in motorcycle_brands.items():
            if brand_key in brand_upper:
                return f"({context})"

        return ""

    def _is_power_tool_brand(self, brand_name: str) -> bool:
        """Check if brand is a power tool manufacturer."""
        if not brand_name:
            return False

        power_tool_brands = ["SHINDAIWA", "STIHL", "HUSQVARNA", "MAKITA", "DEWALT", "BLACK+DECKER"]
        return any(b in brand_name.upper() for b in power_tool_brands)
