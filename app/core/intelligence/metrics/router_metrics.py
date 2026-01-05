"""Intent router metrics tracking.

Extracted from IntentRouter to follow Single Responsibility Principle.
Handles all performance metrics for intent routing operations.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RouterMetrics:
    """Track intent routing performance metrics.

    Tracks:
    - Total requests
    - LLM/SpaCy/Keyword call counts
    - Response times
    - Fallback usage
    """

    def __init__(self):
        """Initialize metrics with zero values."""
        self._stats: dict[str, Any] = {
            "total_requests": 0,
            "llm_calls": 0,
            "spacy_calls": 0,
            "keyword_calls": 0,
            "fallback_calls": 0,
            "avg_response_time": 0.0,
            "total_response_time": 0.0,
        }

    def increment(self, metric: str, value: int = 1) -> None:
        """Increment a metric counter.

        Args:
            metric: Metric name (e.g., 'llm_calls', 'spacy_calls')
            value: Amount to increment by (default: 1)
        """
        if metric in self._stats:
            self._stats[metric] += value
        else:
            logger.warning(f"Unknown metric: {metric}")

    def increment_total_requests(self) -> None:
        """Increment total requests counter."""
        self._stats["total_requests"] += 1

    def increment_llm_calls(self) -> None:
        """Increment LLM calls counter."""
        self._stats["llm_calls"] += 1

    def increment_spacy_calls(self) -> None:
        """Increment SpaCy calls counter."""
        self._stats["spacy_calls"] += 1

    def increment_keyword_calls(self) -> None:
        """Increment keyword fallback calls counter."""
        self._stats["keyword_calls"] += 1

    def increment_fallback_calls(self) -> None:
        """Increment general fallback calls counter."""
        self._stats["fallback_calls"] += 1

    def update_response_time(self, elapsed: float) -> None:
        """Update response time statistics.

        Args:
            elapsed: Response time in seconds
        """
        self._stats["total_response_time"] += elapsed
        total_requests = self._stats["total_requests"]
        if total_requests > 0:
            self._stats["avg_response_time"] = self._stats["total_response_time"] / total_requests

    def get_stats(self) -> dict[str, Any]:
        """Get all metrics.

        Returns:
            Dict with all tracked metrics
        """
        return {
            "total_requests": self._stats["total_requests"],
            "llm_calls": self._stats["llm_calls"],
            "spacy_calls": self._stats["spacy_calls"],
            "keyword_calls": self._stats["keyword_calls"],
            "fallback_calls": self._stats["fallback_calls"],
            "avg_response_time": f"{self._stats['avg_response_time']:.3f}s",
        }

    @property
    def total_requests(self) -> int:
        """Total number of requests processed."""
        return self._stats["total_requests"]

    @property
    def llm_calls(self) -> int:
        """Number of LLM analysis calls."""
        return self._stats["llm_calls"]

    @property
    def spacy_calls(self) -> int:
        """Number of SpaCy analysis calls."""
        return self._stats["spacy_calls"]

    @property
    def keyword_calls(self) -> int:
        """Number of keyword fallback calls."""
        return self._stats["keyword_calls"]

    def reset(self) -> None:
        """Reset all metrics to zero."""
        for key in self._stats:
            self._stats[key] = 0 if isinstance(self._stats[key], int) else 0.0
        logger.info("Router metrics reset")
