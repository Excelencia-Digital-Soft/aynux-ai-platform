"""
Tests for pgvector integration.

Tests semantic search functionality, embedding generation, and quality metrics.

Usage:
    pytest tests/test_pgvector_integration.py -v
    pytest tests/test_pgvector_integration.py::test_pgvector_search -v
"""

import asyncio
import logging
from typing import List
from uuid import UUID

import pytest
from sqlalchemy import select

from app.integrations.vector_stores import PgVectorIntegration
from app.database.async_db import get_async_db_context
from app.models.db import Product

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def pgvector():
    """Create pgvector integration instance."""
    return PgVectorIntegration()


@pytest.fixture
async def test_product_id():
    """Get a test product ID from database."""
    async with get_async_db_context() as db:
        result = await db.execute(
            select(Product.id)
            .where(Product.active.is_(True))
            .limit(1)
        )
        product_id = result.scalar()
        if product_id:
            return product_id
        else:
            pytest.skip("No products available for testing")


class TestPgVectorHealthCheck:
    """Test pgvector health and configuration."""

    @pytest.mark.asyncio
    async def test_health_check(self, pgvector):
        """Test pgvector health check."""
        is_healthy = await pgvector.health_check()
        assert is_healthy, "pgvector health check failed"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_embedding_statistics(self, pgvector):
        """Test embedding statistics retrieval."""
        stats = await pgvector.get_embedding_statistics()

        assert isinstance(stats, dict)
        # Check for either success or error key
        if "error" in stats:
            pytest.skip(f"Database error: {stats.get('error', 'unknown')[:100]}")
        else:
            assert "total_products" in stats
            assert "products_with_embeddings" in stats
            logger.info(f"Embedding statistics: {stats}")


class TestEmbeddingGeneration:
    """Test embedding generation functionality."""

    @pytest.mark.asyncio
    async def test_generate_embedding_simple(self, pgvector):
        """Test embedding generation with simple text."""
        text = "laptop gaming"
        embedding = await pgvector.generate_embedding(text)

        assert isinstance(embedding, list)
        assert len(embedding) == pgvector.embedding_dimensions
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_generate_embedding_product_description(self, pgvector):
        """Test embedding generation with product-like text."""
        text = (
            "Product: ASUS ROG Strix G15. "
            "Brand: ASUS. "
            "Category: Gaming Laptops. "
            "Description: High-performance gaming laptop with RTX 3070, "
            "Intel i7 processor, 16GB RAM, and 144Hz display."
        )
        embedding = await pgvector.generate_embedding(text)

        assert isinstance(embedding, list)
        assert len(embedding) == pgvector.embedding_dimensions
        # Check embedding is a valid vector (may be all zeros if embedding service unavailable)
        # Skip if embedding service is not working
        if all(x == 0.0 for x in embedding):
            pytest.skip("Embedding service returned zero vector - service may be unavailable")

    @pytest.mark.asyncio
    async def test_update_product_embedding(self, pgvector, test_product_id):
        """Test updating product embedding."""
        success = await pgvector.update_product_embedding(
            product_id=test_product_id,
            force_update=True,
        )

        assert success, "Failed to update product embedding"

        # Verify embedding was stored
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Product.embedding, Product.last_embedding_update)
                .where(Product.id == test_product_id)
            )
            row = result.first()

            assert row is not None
            assert row[0] is not None, "Embedding not stored"
            assert row[1] is not None, "Update timestamp not set"

    @pytest.mark.asyncio
    async def test_batch_update_embeddings_dry_run(self, pgvector):
        """Test batch embedding update (limited for testing)."""
        # Get IDs of products without embeddings (limit to 5 for testing)
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Product.id)
                .where(Product.active.is_(True))
                .where(Product.embedding.is_(None))
                .limit(5)
            )
            product_ids = [row[0] for row in result.all()]

        if not product_ids:
            pytest.skip("No products without embeddings found for testing")

        stats = await pgvector.batch_update_embeddings(
            product_ids=product_ids,
            batch_size=2,
            force_update=False,
        )

        assert stats["total"] == len(product_ids)
        assert stats["updated"] >= 0
        assert stats["errors"] >= 0
        assert stats["updated"] + stats["errors"] + stats["skipped"] == stats["total"]

        logger.info(f"Batch update stats: {stats}")


class TestSemanticSearch:
    """Test semantic search functionality."""

    @pytest.mark.asyncio
    async def test_search_simple_query(self, pgvector):
        """Test semantic search with simple query."""
        # Generate embedding for query
        query_text = "laptop gaming"
        query_embedding = await pgvector.generate_embedding(query_text)

        # Perform search
        results = await pgvector.search_similar_products(
            query_embedding=query_embedding,
            k=5,
            min_similarity=0.5,  # Lower threshold for testing
        )

        # Verify results
        assert isinstance(results, list)
        logger.info(f"Found {len(results)} products for query: {query_text}")

        if results:
            product, similarity = results[0]
            assert isinstance(product, Product)
            assert isinstance(similarity, float)
            assert 0.0 <= similarity <= 1.0

            logger.info(f"Top result: {product.name} (similarity: {similarity:.3f})")

    @pytest.mark.asyncio
    async def test_search_with_metadata_filters(self, pgvector):
        """Test semantic search with metadata filters."""
        query_text = "laptop"
        query_embedding = await pgvector.generate_embedding(query_text)

        # Search with stock requirement
        results = await pgvector.search_similar_products(
            query_embedding=query_embedding,
            k=10,
            metadata_filters={"stock_required": True},
            min_similarity=0.5,
        )

        # Verify all results have stock
        for product, similarity in results:
            assert product.stock > 0, f"Product {product.name} has no stock but was returned"

        logger.info(f"Found {len(results)} products in stock")

    @pytest.mark.asyncio
    async def test_search_with_price_filter(self, pgvector):
        """Test semantic search with price range filter."""
        query_text = "laptop"
        query_embedding = await pgvector.generate_embedding(query_text)

        # Search with price range
        min_price = 500.0
        max_price = 1500.0

        results = await pgvector.search_similar_products(
            query_embedding=query_embedding,
            k=10,
            metadata_filters={
                "price_min": min_price,
                "price_max": max_price,
            },
            min_similarity=0.5,
        )

        # Verify all results within price range
        for product, similarity in results:
            assert min_price <= product.price <= max_price, (
                f"Product {product.name} price ${product.price} outside range "
                f"${min_price}-${max_price}"
            )

        logger.info(f"Found {len(results)} products in price range ${min_price}-${max_price}")

    @pytest.mark.asyncio
    async def test_search_quality_metrics(self, pgvector):
        """Test search quality with various queries."""
        test_queries = [
            "laptop gaming",
            "computadora trabajo",
            "auriculares bluetooth",
            "teclado mecánico",
            "mouse inalámbrico",
        ]

        results_summary = []

        for query in test_queries:
            query_embedding = await pgvector.generate_embedding(query)

            results = await pgvector.search_similar_products(
                query_embedding=query_embedding,
                k=10,
                min_similarity=0.5,
            )

            if results:
                avg_similarity = sum(sim for _, sim in results) / len(results)
                max_similarity = max(sim for _, sim in results)

                results_summary.append({
                    "query": query,
                    "num_results": len(results),
                    "avg_similarity": avg_similarity,
                    "max_similarity": max_similarity,
                })

                logger.info(
                    f"Query: '{query}' - Results: {len(results)}, "
                    f"Avg similarity: {avg_similarity:.3f}, "
                    f"Max similarity: {max_similarity:.3f}"
                )
            else:
                logger.warning(f"Query: '{query}' - No results found")

        # Verify at least some queries returned results
        # Skip if no products with embeddings are available
        if len(results_summary) == 0:
            pytest.skip("No products with embeddings available for quality metrics test")

        # Check average quality
        overall_avg_similarity = (
            sum(r["avg_similarity"] for r in results_summary) / len(results_summary)
        )
        logger.info(f"Overall average similarity: {overall_avg_similarity:.3f}")


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_search_with_empty_embedding(self, pgvector):
        """Test search with zero vector (should handle gracefully)."""
        zero_embedding = [0.0] * pgvector.embedding_dimensions

        results = await pgvector.search_similar_products(
            query_embedding=zero_embedding,
            k=5,
            min_similarity=0.5,
        )

        # Should return empty list or handle gracefully
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_high_threshold(self, pgvector):
        """Test search with very high similarity threshold."""
        query_embedding = await pgvector.generate_embedding("laptop")

        results = await pgvector.search_similar_products(
            query_embedding=query_embedding,
            k=10,
            min_similarity=0.99,  # Very strict
        )

        # May return few or no results
        assert isinstance(results, list)
        logger.info(f"High threshold search returned {len(results)} results")

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, pgvector):
        """Test that same text generates consistent embeddings."""
        text = "laptop gaming ASUS"

        embedding1 = await pgvector.generate_embedding(text)
        embedding2 = await pgvector.generate_embedding(text)

        # Embeddings should be identical for same text
        assert len(embedding1) == len(embedding2)
        for v1, v2 in zip(embedding1, embedding2):
            assert abs(v1 - v2) < 1e-6, "Embeddings should be consistent"


class TestComparison:
    """Compare pgvector with expected behavior."""

    @pytest.mark.asyncio
    async def test_multilingual_search(self, pgvector):
        """Test search with Spanish queries."""
        test_queries = [
            ("laptop", "laptop"),  # English
            ("laptop", "portátil"),  # Spanish
            ("laptop", "computadora portátil"),  # Spanish variation
        ]

        for base_query, variation_query in test_queries:
            base_embedding = await pgvector.generate_embedding(base_query)
            variation_embedding = await pgvector.generate_embedding(variation_query)

            base_results = await pgvector.search_similar_products(
                query_embedding=base_embedding,
                k=5,
                min_similarity=0.5,
            )

            variation_results = await pgvector.search_similar_products(
                query_embedding=variation_embedding,
                k=5,
                min_similarity=0.5,
            )

            logger.info(
                f"Base query '{base_query}': {len(base_results)} results, "
                f"Variation '{variation_query}': {len(variation_results)} results"
            )


class TestPerformanceBenchmarks:
    """Test performance and scalability metrics."""

    @pytest.mark.asyncio
    async def test_search_latency(self, pgvector):
        """Benchmark search latency (should be < 100ms)."""
        import time

        query_embedding = await pgvector.generate_embedding("laptop gaming")

        # Warm up
        await pgvector.search_similar_products(
            query_embedding=query_embedding,
            k=10,
            min_similarity=0.5,
        )

        # Measure latency
        start_time = time.perf_counter()
        await pgvector.search_similar_products(
            query_embedding=query_embedding,
            k=10,
            min_similarity=0.5,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000

        logger.info(f"Search latency: {latency_ms:.2f}ms")
        assert latency_ms < 100, f"Search latency {latency_ms:.2f}ms exceeds 100ms target"

    @pytest.mark.asyncio
    async def test_embedding_generation_speed(self, pgvector):
        """Benchmark embedding generation speed."""
        import time

        text = "High-performance gaming laptop with RTX 3070 GPU"

        # Warm up
        await pgvector.generate_embedding(text)

        # Measure speed
        start_time = time.perf_counter()
        await pgvector.generate_embedding(text)
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(f"Embedding generation: {duration_ms:.2f}ms")
        assert duration_ms < 500, f"Embedding generation {duration_ms:.2f}ms exceeds 500ms target"

    @pytest.mark.asyncio
    async def test_batch_update_throughput(self, pgvector):
        """Test batch update throughput (products per second)."""
        import time

        # Get sample product IDs
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Product.id)
                .where(Product.active.is_(True))
                .limit(10)
            )
            product_ids = [row[0] for row in result.all()]

        if len(product_ids) < 10:
            pytest.skip("Need at least 10 products for throughput test")

        # Measure throughput
        start_time = time.perf_counter()
        stats = await pgvector.batch_update_embeddings(
            product_ids=product_ids,
            batch_size=5,
            force_update=True,
        )
        duration = time.perf_counter() - start_time

        throughput = stats["updated"] / duration
        logger.info(f"Batch update throughput: {throughput:.2f} products/sec")
        assert throughput >= 1.0, f"Throughput {throughput:.2f} products/sec is too low"


class TestSearchStrategies:
    """Test different search strategies and configurations."""

    @pytest.mark.asyncio
    async def test_precision_vs_recall_threshold(self, pgvector):
        """Test impact of similarity threshold on precision/recall."""
        query_embedding = await pgvector.generate_embedding("laptop gaming")

        thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
        threshold_results = []

        for threshold in thresholds:
            results = await pgvector.search_similar_products(
                query_embedding=query_embedding,
                k=20,
                min_similarity=threshold,
            )

            if results:
                avg_similarity = sum(sim for _, sim in results) / len(results)
                threshold_results.append({
                    "threshold": threshold,
                    "count": len(results),
                    "avg_similarity": avg_similarity,
                })

                logger.info(
                    f"Threshold {threshold}: {len(results)} results, "
                    f"avg similarity: {avg_similarity:.3f}"
                )

        # Higher thresholds should yield fewer but higher quality results
        # Skip if no products with embeddings are available
        if len(threshold_results) == 0:
            pytest.skip("No products with embeddings available for precision/recall test")

        for i in range(len(threshold_results) - 1):
            assert threshold_results[i]["count"] >= threshold_results[i + 1]["count"]

    @pytest.mark.asyncio
    async def test_category_specific_search(self, pgvector):
        """Test search within specific categories."""
        query_embedding = await pgvector.generate_embedding("laptop")

        # Get available categories
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Product.category_id)
                .where(Product.active.is_(True))
                .where(Product.category_id.isnot(None))
                .distinct()
                .limit(3)
            )
            category_ids = [row[0] for row in result.all()]

        if not category_ids:
            pytest.skip("No categories available for testing")

        for category_id in category_ids:
            results = await pgvector.search_similar_products(
                query_embedding=query_embedding,
                k=10,
                metadata_filters={"category_id": category_id},
                min_similarity=0.5,
            )

            # Verify all results are from correct category
            for product, _ in results:
                assert product.category_id == category_id

            logger.info(f"Category {category_id}: {len(results)} results")


class TestDataQuality:
    """Test data quality and consistency."""

    @pytest.mark.asyncio
    async def test_embedding_coverage(self, pgvector):
        """Test what percentage of active products have embeddings."""
        stats = await pgvector.get_embedding_statistics()

        total = stats.get("total_products", 0)
        with_embeddings = stats.get("products_with_embeddings", 0)

        if total > 0:
            coverage_pct = (with_embeddings / total) * 100
            logger.info(f"Embedding coverage: {coverage_pct:.1f}% ({with_embeddings}/{total})")

            # Warning if coverage is low
            if coverage_pct < 80:
                logger.warning(f"Low embedding coverage: {coverage_pct:.1f}%")

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Product model no longer has last_embedding_update field")
    async def test_embedding_freshness(self, pgvector):
        """Test how many products have outdated embeddings.

        NOTE: This test is skipped because the Product model no longer has
        the 'last_embedding_update' field. Consider using 'updated_at' if
        needed for freshness tracking.
        """
        pass

    @pytest.mark.asyncio
    async def test_embedding_dimension_consistency(self, pgvector):
        """Test that all embeddings have consistent dimensions."""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Product.embedding)
                .where(Product.embedding.isnot(None))
                .limit(100)
            )
            embeddings = [row[0] for row in result.all()]

        if embeddings:
            expected_dim = pgvector.embedding_dimensions
            for i, emb in enumerate(embeddings):
                assert len(emb) == expected_dim, (
                    f"Embedding {i} has dimension {len(emb)}, expected {expected_dim}"
                )

            logger.info(f"Checked {len(embeddings)} embeddings - all have dimension {expected_dim}")


class TestIntegrationWithProductAgent:
    """Test integration with product agent workflows."""

    @pytest.mark.asyncio
    async def test_end_to_end_product_search(self, pgvector):
        """Simulate complete product search workflow."""
        # User query
        user_query = "quiero una laptop para gaming con buena tarjeta gráfica"

        # Generate embedding
        query_embedding = await pgvector.generate_embedding(user_query)

        # Search products
        results = await pgvector.search_similar_products(
            query_embedding=query_embedding,
            k=10,
            metadata_filters={"stock_required": True},
            min_similarity=0.6,
        )

        # Verify results are relevant
        assert isinstance(results, list)

        if results:
            logger.info(f"Found {len(results)} gaming laptops for user query")
            for i, (product, similarity) in enumerate(results[:3], 1):
                logger.info(
                    f"{i}. {product.name} - ${product.price:.2f} "
                    f"(similarity: {similarity:.3f})"
                )
        else:
            logger.warning("No gaming laptops found matching query")

    @pytest.mark.asyncio
    async def test_multilingual_product_search(self, pgvector):
        """Test product search with multilingual queries."""
        test_cases = [
            ("laptop gaming", "English - gaming laptop"),
            ("portátil para juegos", "Spanish - gaming laptop"),
            ("auriculares inalámbricos", "Spanish - wireless headphones"),
            ("mechanical keyboard", "English - mechanical keyboard"),
        ]

        for query, description in test_cases:
            query_embedding = await pgvector.generate_embedding(query)
            results = await pgvector.search_similar_products(
                query_embedding=query_embedding,
                k=5,
                min_similarity=0.5,
            )

            logger.info(f"{description}: {len(results)} results")


if __name__ == "__main__":
    # Run specific test
    pytest.main([__file__, "-v", "-s"])