"""
Classification Statistics Tracker - Seguimiento de métricas de clasificación.

Sigue el Single Responsibility Principle: solo se encarga de rastrear
y reportar estadísticas de clasificación.
"""

import threading
from datetime import datetime
from typing import Any


class ClassificationStatisticsTracker:
    """
    Rastreador de estadísticas de clasificación de dominios.

    Aplica SRP: Solo se encarga de rastrear estadísticas.
    No hace clasificación, no almacena patrones, no procesa mensajes.

    Thread-safe para uso en aplicaciones concurrentes.
    """

    def __init__(self):
        """Initialize statistics tracker."""
        self._lock = threading.Lock()
        self._stats: dict[str, Any] = {
            "total_classifications": 0,
            "successful_classifications": 0,
            "fallback_classifications": 0,
            "avg_classification_time_ms": 0.0,
            "total_classification_time_ms": 0.0,
            "domain_distribution": {},
            "method_distribution": {},
            "confidence_distribution": {
                "high": 0,  # >= 0.8
                "medium": 0,  # 0.5-0.8
                "low": 0,  # < 0.5
            },
            "started_at": datetime.now().isoformat(),
            "last_classification_at": None,
        }

    def record_classification(
        self,
        domain: str,
        confidence: float,
        method: str,
        classification_time_ms: float,
        successful: bool = True,
    ) -> None:
        """
        Record a classification event.

        Args:
            domain: Classified domain
            confidence: Classification confidence (0.0-1.0)
            method: Classification method (keyword, ai, hybrid)
            classification_time_ms: Time taken in milliseconds
            successful: Whether classification was successful
        """
        with self._lock:
            # Update counters
            self._stats["total_classifications"] += 1

            if successful:
                self._stats["successful_classifications"] += 1
            else:
                self._stats["fallback_classifications"] += 1

            # Update domain distribution
            if domain not in self._stats["domain_distribution"]:
                self._stats["domain_distribution"][domain] = 0
            self._stats["domain_distribution"][domain] += 1

            # Update method distribution
            if method not in self._stats["method_distribution"]:
                self._stats["method_distribution"][method] = 0
            self._stats["method_distribution"][method] += 1

            # Update confidence distribution
            if confidence >= 0.8:
                self._stats["confidence_distribution"]["high"] += 1
            elif confidence >= 0.5:
                self._stats["confidence_distribution"]["medium"] += 1
            else:
                self._stats["confidence_distribution"]["low"] += 1

            # Update timing statistics
            self._stats["total_classification_time_ms"] += classification_time_ms
            self._stats["avg_classification_time_ms"] = (
                self._stats["total_classification_time_ms"] / self._stats["total_classifications"]
            )

            # Update timestamp
            self._stats["last_classification_at"] = datetime.now().isoformat()

    def get_stats(self) -> dict[str, Any]:
        """
        Get current statistics.

        Returns:
            Dictionary with classification statistics
        """
        with self._lock:
            # Create a copy to avoid modification during iteration
            stats_copy: dict[str, Any] = {
                **self._stats,
                "domain_distribution": dict(self._stats["domain_distribution"]),
                "method_distribution": dict(self._stats["method_distribution"]),
                "confidence_distribution": dict(self._stats["confidence_distribution"]),
            }

            # Add computed metrics
            total: int = stats_copy["total_classifications"]
            if total > 0:
                stats_copy["success_rate"] = stats_copy["successful_classifications"] / total
                stats_copy["fallback_rate"] = stats_copy["fallback_classifications"] / total

                # Calculate confidence percentages
                conf_dist: dict[str, int] = stats_copy["confidence_distribution"]
                stats_copy["confidence_percentages"] = {
                    "high": conf_dist["high"] / total if total > 0 else 0,
                    "medium": conf_dist["medium"] / total if total > 0 else 0,
                    "low": conf_dist["low"] / total if total > 0 else 0,
                }

            return stats_copy

    def reset(self) -> None:
        """Reset all statistics to initial state."""
        with self._lock:
            started_at = self._stats["started_at"]
            self._stats = {
                "total_classifications": 0,
                "successful_classifications": 0,
                "fallback_classifications": 0,
                "avg_classification_time_ms": 0.0,
                "total_classification_time_ms": 0.0,
                "domain_distribution": {},
                "method_distribution": {},
                "confidence_distribution": {
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                },
                "started_at": started_at,
                "last_classification_at": None,
                "reset_at": datetime.now().isoformat(),
            }

    def get_domain_stats(self, domain: str) -> dict[str, Any]:
        """
        Get statistics for a specific domain.

        Args:
            domain: Domain name

        Returns:
            Statistics for the specified domain
        """
        with self._lock:
            total = self._stats["total_classifications"]
            domain_count = self._stats["domain_distribution"].get(domain, 0)

            return {
                "domain": domain,
                "count": domain_count,
                "percentage": (domain_count / total * 100) if total > 0 else 0,
                "total_classifications": total,
            }

    def get_method_stats(self, method: str) -> dict[str, Any]:
        """
        Get statistics for a specific classification method.

        Args:
            method: Method name (keyword, ai, hybrid)

        Returns:
            Statistics for the specified method
        """
        with self._lock:
            total = self._stats["total_classifications"]
            method_count = self._stats["method_distribution"].get(method, 0)

            return {
                "method": method,
                "count": method_count,
                "percentage": (method_count / total * 100) if total > 0 else 0,
                "total_classifications": total,
            }

    def export_metrics(self) -> dict[str, Any]:
        """
        Export metrics in Prometheus-compatible format.

        Returns:
            Metrics suitable for monitoring systems
        """
        stats = self.get_stats()

        return {
            "classification_total": stats["total_classifications"],
            "classification_successful_total": stats["successful_classifications"],
            "classification_fallback_total": stats["fallback_classifications"],
            "classification_duration_ms_avg": stats["avg_classification_time_ms"],
            "classification_confidence_high_total": stats["confidence_distribution"]["high"],
            "classification_confidence_medium_total": stats["confidence_distribution"]["medium"],
            "classification_confidence_low_total": stats["confidence_distribution"]["low"],
            "classification_by_domain": stats["domain_distribution"],
            "classification_by_method": stats["method_distribution"],
        }
