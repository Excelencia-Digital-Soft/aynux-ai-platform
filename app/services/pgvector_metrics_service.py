"""
PgVector Metrics Service

Provides comprehensive monitoring and metrics collection for pgvector operations including:
- Search performance metrics
- Embedding quality metrics
- Coverage statistics
- Error tracking
- Performance benchmarks
"""

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Product

logger = logging.getLogger(__name__)


@dataclass
class SearchMetrics:
    """Metrics for a single search operation."""

    timestamp: datetime
    query: str
    duration_ms: float
    results_count: int
    avg_similarity: float
    max_similarity: float
    min_similarity: Optional[float]
    filters_applied: bool
    error: Optional[str] = None


@dataclass
class EmbeddingMetrics:
    """Metrics for embedding operations."""

    timestamp: datetime
    product_id: str
    operation: str  # "generate", "update", "batch"
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class AggregatedMetrics:
    """Aggregated metrics over a time period."""

    time_range: str
    start_time: datetime
    end_time: datetime

    # Search metrics
    total_searches: int = 0
    successful_searches: int = 0
    failed_searches: int = 0
    avg_search_latency_ms: float = 0.0
    p95_search_latency_ms: float = 0.0
    p99_search_latency_ms: float = 0.0
    avg_results_per_search: float = 0.0
    avg_similarity_score: float = 0.0
    searches_with_no_results: int = 0
    searches_with_low_quality: int = 0  # similarity < 0.6

    # Embedding metrics
    total_embedding_operations: int = 0
    successful_embeddings: int = 0
    failed_embeddings: int = 0
    avg_embedding_latency_ms: float = 0.0

    # Quality metrics
    embedding_coverage_pct: float = 0.0
    stale_embeddings_count: int = 0
    avg_embedding_age_days: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PgVectorMetricsService:
    """Service for collecting and analyzing pgvector metrics."""

    def __init__(self):
        """Initialize metrics service with in-memory storage."""
        self.search_metrics: List[SearchMetrics] = []
        self.embedding_metrics: List[EmbeddingMetrics] = []

        # Configuration
        self.max_stored_metrics = 10000  # Keep last 10k operations
        self.low_quality_threshold = 0.6  # Similarity scores below this are "low quality"
        self.stale_threshold_days = 7  # Embeddings older than this are "stale"

        logger.info("PgVectorMetricsService initialized")

    async def record_search(
        self,
        query: str,
        duration_ms: float,
        results: List[tuple],  # List of (product, similarity) tuples
        filters_applied: bool = False,
        error: Optional[str] = None,
    ):
        """
        Record a search operation.

        Args:
            query: Search query text
            duration_ms: Search duration in milliseconds
            results: List of (product, similarity) tuples
            filters_applied: Whether metadata filters were applied
            error: Error message if search failed
        """
        similarities = [sim for _, sim in results] if results else []

        metric = SearchMetrics(
            timestamp=datetime.now(UTC),
            query=query[:100],  # Truncate long queries
            duration_ms=duration_ms,
            results_count=len(results),
            avg_similarity=sum(similarities) / len(similarities) if similarities else 0.0,
            max_similarity=max(similarities) if similarities else 0.0,
            min_similarity=min(similarities) if similarities else None,
            filters_applied=filters_applied,
            error=error,
        )

        self.search_metrics.append(metric)

        # Trim old metrics if needed
        if len(self.search_metrics) > self.max_stored_metrics:
            self.search_metrics = self.search_metrics[-self.max_stored_metrics :]

        # Log warning for slow searches
        if duration_ms > 100:
            logger.warning(f"Slow pgvector search: {duration_ms:.2f}ms for query: {query[:50]}")

        # Log warning for low quality results
        if similarities and metric.avg_similarity < self.low_quality_threshold:
            logger.warning(
                f"Low quality search results (avg similarity: {metric.avg_similarity:.2f}) for query: {query[:50]}"
            )

    async def record_embedding_operation(
        self, product_id: str, operation: str, duration_ms: float, success: bool, error: Optional[str] = None
    ):
        """
        Record an embedding generation/update operation.

        Args:
            product_id: Product identifier
            operation: Type of operation ("generate", "update", "batch")
            duration_ms: Operation duration in milliseconds
            success: Whether operation succeeded
            error: Error message if operation failed
        """
        metric = EmbeddingMetrics(
            timestamp=datetime.now(UTC),
            product_id=product_id,
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )

        self.embedding_metrics.append(metric)

        # Trim old metrics if needed
        if len(self.embedding_metrics) > self.max_stored_metrics:
            self.embedding_metrics = self.embedding_metrics[-self.max_stored_metrics :]

        # Log warnings
        if not success:
            logger.error(f"Embedding operation failed for product {product_id}: {error}")
        elif duration_ms > 500:
            logger.warning(f"Slow embedding operation: {duration_ms:.2f}ms for product {product_id}")

    async def get_aggregated_metrics(
        self, time_range: str = "24h", db: Optional[AsyncSession] = None
    ) -> AggregatedMetrics:
        """
        Get aggregated metrics for a time range.

        Args:
            time_range: Time range ("1h", "24h", "7d", "30d")
            db: Optional database session for coverage stats

        Returns:
            AggregatedMetrics object
        """
        # Parse time range
        time_delta = self._parse_time_range(time_range)
        cutoff_time = datetime.now(UTC) - time_delta

        # Filter metrics by time range
        search_metrics = [m for m in self.search_metrics if m.timestamp >= cutoff_time]
        embedding_metrics = [m for m in self.embedding_metrics if m.timestamp >= cutoff_time]

        # Create aggregated metrics object
        metrics = AggregatedMetrics(time_range=time_range, start_time=cutoff_time, end_time=datetime.now(UTC))

        # Aggregate search metrics
        if search_metrics:
            metrics.total_searches = len(search_metrics)
            metrics.successful_searches = sum(1 for m in search_metrics if m.error is None)
            metrics.failed_searches = sum(1 for m in search_metrics if m.error is not None)

            # Latency metrics
            latencies = [m.duration_ms for m in search_metrics if m.error is None]
            if latencies:
                latencies_sorted = sorted(latencies)
                metrics.avg_search_latency_ms = sum(latencies) / len(latencies)
                metrics.p95_search_latency_ms = latencies_sorted[int(len(latencies) * 0.95)]
                metrics.p99_search_latency_ms = latencies_sorted[int(len(latencies) * 0.99)]

            # Result metrics
            successful = [m for m in search_metrics if m.error is None]
            if successful:
                metrics.avg_results_per_search = sum(m.results_count for m in successful) / len(successful)
                metrics.avg_similarity_score = sum(m.avg_similarity for m in successful) / len(successful)
                metrics.searches_with_no_results = sum(1 for m in successful if m.results_count == 0)
                metrics.searches_with_low_quality = sum(
                    1 for m in successful if m.avg_similarity > 0 and m.avg_similarity < self.low_quality_threshold
                )

        # Aggregate embedding metrics
        if embedding_metrics:
            metrics.total_embedding_operations = len(embedding_metrics)
            metrics.successful_embeddings = sum(1 for m in embedding_metrics if m.success)
            metrics.failed_embeddings = sum(1 for m in embedding_metrics if not m.success)

            successful_emb = [m for m in embedding_metrics if m.success]
            if successful_emb:
                metrics.avg_embedding_latency_ms = sum(m.duration_ms for m in successful_emb) / len(successful_emb)

        # Get database coverage stats if session provided
        if db:
            coverage_stats = await self._get_coverage_stats(db)
            metrics.embedding_coverage_pct = coverage_stats.get("coverage_pct", 0.0)
            metrics.stale_embeddings_count = coverage_stats.get("stale_count", 0)
            metrics.avg_embedding_age_days = coverage_stats.get("avg_age_days", 0.0)

        return metrics

    async def get_health_status(self, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Get health status of pgvector system.

        Args:
            db: Optional database session

        Returns:
            Health status dictionary
        """
        recent_metrics = await self.get_aggregated_metrics(time_range="1h", db=db)

        # Determine health status
        is_healthy = True
        issues = []
        warnings = []

        # Check search performance
        if recent_metrics.total_searches > 0:
            error_rate = recent_metrics.failed_searches / recent_metrics.total_searches
            if error_rate > 0.1:  # >10% error rate
                is_healthy = False
                issues.append(f"High search error rate: {error_rate:.1%}")
            elif error_rate > 0.05:  # >5% error rate
                warnings.append(f"Elevated search error rate: {error_rate:.1%}")

            if recent_metrics.avg_search_latency_ms > 100:
                warnings.append(f"High average search latency: {recent_metrics.avg_search_latency_ms:.1f}ms")

            if recent_metrics.p99_search_latency_ms > 500:
                is_healthy = False
                issues.append(f"Very high p99 search latency: {recent_metrics.p99_search_latency_ms:.1f}ms")

            no_results_rate = recent_metrics.searches_with_no_results / recent_metrics.total_searches
            if no_results_rate > 0.3:  # >30% searches with no results
                warnings.append(f"High no-results rate: {no_results_rate:.1%}")

            low_quality_rate = recent_metrics.searches_with_low_quality / recent_metrics.total_searches
            if low_quality_rate > 0.2:  # >20% low quality searches
                warnings.append(f"High low-quality results rate: {low_quality_rate:.1%}")

        # Check embedding coverage
        if recent_metrics.embedding_coverage_pct < 80:
            warnings.append(f"Low embedding coverage: {recent_metrics.embedding_coverage_pct:.1f}%")

        if recent_metrics.stale_embeddings_count > 100:
            warnings.append(f"Many stale embeddings: {recent_metrics.stale_embeddings_count}")

        return {
            "healthy": is_healthy,
            "status": "healthy" if is_healthy else "degraded",
            "issues": issues,
            "warnings": warnings,
            "metrics": recent_metrics.to_dict(),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def get_search_quality_report(self, time_range: str = "24h") -> Dict[str, Any]:
        """
        Generate a search quality report.

        Args:
            time_range: Time range for analysis

        Returns:
            Quality report dictionary
        """
        time_delta = self._parse_time_range(time_range)
        cutoff_time = datetime.now(UTC) - time_delta

        recent_searches = [m for m in self.search_metrics if m.timestamp >= cutoff_time and m.error is None]

        if not recent_searches:
            return {
                "time_range": time_range,
                "total_searches": 0,
                "message": "No search data available for this time range",
            }

        # Categorize searches by quality
        high_quality = [m for m in recent_searches if m.avg_similarity >= 0.8]
        medium_quality = [m for m in recent_searches if 0.6 <= m.avg_similarity < 0.8]
        low_quality = [m for m in recent_searches if 0 < m.avg_similarity < 0.6]
        no_results = [m for m in recent_searches if m.results_count == 0]

        # Find slowest queries
        slowest_queries = sorted(recent_searches, key=lambda m: m.duration_ms, reverse=True)[:10]

        # Find queries with lowest quality
        lowest_quality = sorted([m for m in recent_searches if m.avg_similarity > 0], key=lambda m: m.avg_similarity)[
            :10
        ]

        return {
            "time_range": time_range,
            "total_searches": len(recent_searches),
            "quality_distribution": {
                "high_quality": {
                    "count": len(high_quality),
                    "percentage": len(high_quality) / len(recent_searches) * 100,
                    "avg_similarity": sum(m.avg_similarity for m in high_quality) / len(high_quality)
                    if high_quality
                    else 0,
                },
                "medium_quality": {
                    "count": len(medium_quality),
                    "percentage": len(medium_quality) / len(recent_searches) * 100,
                    "avg_similarity": sum(m.avg_similarity for m in medium_quality) / len(medium_quality)
                    if medium_quality
                    else 0,
                },
                "low_quality": {
                    "count": len(low_quality),
                    "percentage": len(low_quality) / len(recent_searches) * 100,
                    "avg_similarity": sum(m.avg_similarity for m in low_quality) / len(low_quality)
                    if low_quality
                    else 0,
                },
                "no_results": {"count": len(no_results), "percentage": len(no_results) / len(recent_searches) * 100},
            },
            "slowest_queries": [
                {
                    "query": m.query,
                    "duration_ms": m.duration_ms,
                    "results_count": m.results_count,
                    "avg_similarity": m.avg_similarity,
                }
                for m in slowest_queries
            ],
            "lowest_quality_queries": [
                {
                    "query": m.query,
                    "avg_similarity": m.avg_similarity,
                    "results_count": m.results_count,
                    "duration_ms": m.duration_ms,
                }
                for m in lowest_quality
            ],
        }

    async def _get_coverage_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get embedding coverage statistics from database."""
        try:
            # Total products
            total_result = await db.execute(select(func.count(Product.id)).where(Product.active.is_(True)))
            total_products = total_result.scalar() or 0

            # Products with embeddings
            with_embeddings_result = await db.execute(
                select(func.count(Product.id)).where(Product.active.is_(True)).where(Product.embedding.isnot(None))
            )
            with_embeddings = with_embeddings_result.scalar() or 0

            # Coverage percentage
            coverage_pct = (with_embeddings / total_products * 100) if total_products > 0 else 0

            # Stale embeddings (>7 days old)
            cutoff_date = datetime.now(UTC) - timedelta(days=self.stale_threshold_days)
            stale_result = await db.execute(
                select(func.count(Product.id))
                .where(Product.active.is_(True))
                .where(Product.embedding.isnot(None))
                .where(Product.last_embedding_update < cutoff_date)
            )
            stale_count = stale_result.scalar() or 0

            # Average embedding age
            age_result = await db.execute(
                select(func.avg(func.extract("epoch", datetime.now(UTC) - Product.last_embedding_update) / 86400))
                .where(Product.active.is_(True))
                .where(Product.embedding.isnot(None))
                .where(Product.last_embedding_update.isnot(None))
            )
            avg_age_days = age_result.scalar() or 0.0

            return {
                "total_products": total_products,
                "with_embeddings": with_embeddings,
                "coverage_pct": coverage_pct,
                "stale_count": stale_count,
                "avg_age_days": float(avg_age_days),
            }

        except Exception as e:
            logger.error(f"Error getting coverage stats: {str(e)}")
            return {
                "total_products": 0,
                "with_embeddings": 0,
                "coverage_pct": 0.0,
                "stale_count": 0,
                "avg_age_days": 0.0,
            }

    def _parse_time_range(self, time_range: str) -> timedelta:
        """Parse time range string into timedelta."""
        mapping = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }

        return mapping.get(time_range, timedelta(hours=24))

    def clear_metrics(self):
        """Clear all stored metrics (for testing)."""
        self.search_metrics.clear()
        self.embedding_metrics.clear()
        logger.info("All metrics cleared")


# Global instance
_metrics_service: Optional[PgVectorMetricsService] = None


def get_metrics_service() -> PgVectorMetricsService:
    """Get or create global metrics service instance."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = PgVectorMetricsService()
    return _metrics_service

