"""
Tests for ClassificationStatisticsTracker.

Tests statistics tracking, thread safety, and metric calculations.
"""

import pytest
from concurrent.futures import ThreadPoolExecutor

from app.services.orchestration import ClassificationStatisticsTracker


class TestClassificationStatisticsTracker:
    """Test ClassificationStatisticsTracker."""

    @pytest.fixture
    def tracker(self):
        """Create tracker fixture."""
        return ClassificationStatisticsTracker()

    def test_tracker_initialization(self, tracker):
        """Test tracker initializes with zero stats."""
        stats = tracker.get_stats()

        assert stats["total_classifications"] == 0
        assert stats["successful_classifications"] == 0
        assert stats["fallback_classifications"] == 0
        assert "started_at" in stats

    def test_record_classification(self, tracker):
        """Test recording a classification."""
        tracker.record_classification(
            domain="ecommerce",
            confidence=0.9,
            method="keyword",
            classification_time_ms=150.5,
            successful=True,
        )

        stats = tracker.get_stats()

        assert stats["total_classifications"] == 1
        assert stats["successful_classifications"] == 1
        assert stats["domain_distribution"]["ecommerce"] == 1
        assert stats["method_distribution"]["keyword"] == 1
        assert stats["confidence_distribution"]["high"] == 1

    def test_record_multiple_classifications(self, tracker):
        """Test recording multiple classifications."""
        tracker.record_classification("ecommerce", 0.9, "keyword", 100, True)
        tracker.record_classification("hospital", 0.6, "ai", 200, True)
        tracker.record_classification("credit", 0.3, "keyword", 150, False)

        stats = tracker.get_stats()

        assert stats["total_classifications"] == 3
        assert stats["successful_classifications"] == 2
        assert stats["fallback_classifications"] == 1
        assert stats["domain_distribution"]["ecommerce"] == 1
        assert stats["domain_distribution"]["hospital"] == 1
        assert stats["domain_distribution"]["credit"] == 1

    def test_confidence_distribution(self, tracker):
        """Test confidence distribution tracking."""
        tracker.record_classification("test", 0.9, "test", 100, True)   # high
        tracker.record_classification("test", 0.7, "test", 100, True)   # medium
        tracker.record_classification("test", 0.3, "test", 100, True)   # low

        stats = tracker.get_stats()

        assert stats["confidence_distribution"]["high"] == 1
        assert stats["confidence_distribution"]["medium"] == 1
        assert stats["confidence_distribution"]["low"] == 1

    def test_average_classification_time(self, tracker):
        """Test average classification time calculation."""
        tracker.record_classification("test", 0.8, "test", 100.0, True)
        tracker.record_classification("test", 0.8, "test", 200.0, True)
        tracker.record_classification("test", 0.8, "test", 300.0, True)

        stats = tracker.get_stats()

        assert stats["avg_classification_time_ms"] == 200.0

    def test_success_rate_calculation(self, tracker):
        """Test success rate calculation."""
        tracker.record_classification("test", 0.8, "test", 100, True)
        tracker.record_classification("test", 0.4, "test", 100, False)
        tracker.record_classification("test", 0.9, "test", 100, True)
        tracker.record_classification("test", 0.3, "test", 100, False)

        stats = tracker.get_stats()

        assert stats["success_rate"] == 0.5
        assert stats["fallback_rate"] == 0.5

    def test_reset(self, tracker):
        """Test resetting statistics."""
        # Record some data
        tracker.record_classification("test", 0.8, "test", 100, True)
        tracker.record_classification("test", 0.9, "test", 150, True)

        # Reset
        tracker.reset()

        stats = tracker.get_stats()

        assert stats["total_classifications"] == 0
        assert stats["successful_classifications"] == 0
        assert "reset_at" in stats

    def test_get_domain_stats(self, tracker):
        """Test getting stats for specific domain."""
        tracker.record_classification("ecommerce", 0.8, "test", 100, True)
        tracker.record_classification("ecommerce", 0.9, "test", 100, True)
        tracker.record_classification("hospital", 0.7, "test", 100, True)

        ecommerce_stats = tracker.get_domain_stats("ecommerce")

        assert ecommerce_stats["domain"] == "ecommerce"
        assert ecommerce_stats["count"] == 2
        assert ecommerce_stats["percentage"] > 0

    def test_get_method_stats(self, tracker):
        """Test getting stats for specific method."""
        tracker.record_classification("test", 0.8, "keyword", 100, True)
        tracker.record_classification("test", 0.8, "keyword", 100, True)
        tracker.record_classification("test", 0.8, "ai", 100, True)

        keyword_stats = tracker.get_method_stats("keyword")

        assert keyword_stats["method"] == "keyword"
        assert keyword_stats["count"] == 2

    def test_export_metrics(self, tracker):
        """Test exporting metrics in Prometheus format."""
        tracker.record_classification("ecommerce", 0.9, "keyword", 150, True)

        metrics = tracker.export_metrics()

        assert "classification_total" in metrics
        assert "classification_successful_total" in metrics
        assert "classification_duration_ms_avg" in metrics
        assert "classification_by_domain" in metrics
        assert "classification_by_method" in metrics


class TestThreadSafety:
    """Test thread safety of ClassificationStatisticsTracker."""

    def test_concurrent_recording(self):
        """Test that concurrent recordings are thread-safe."""
        tracker = ClassificationStatisticsTracker()

        def record_classification(i):
            tracker.record_classification(
                domain=f"domain_{i % 3}",
                confidence=0.8,
                method="test",
                classification_time_ms=100,
                successful=True,
            )

        # Record 100 classifications concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(record_classification, range(100))

        stats = tracker.get_stats()

        # All 100 should be recorded
        assert stats["total_classifications"] == 100
        assert stats["successful_classifications"] == 100
