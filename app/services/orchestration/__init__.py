"""
Orchestration Components - SOLID-compliant components for domain orchestration.

This module contains specialized components that follow Single Responsibility Principle:
- DomainClassifier: Classifies messages into business domains
- DomainPatternRepository: Stores and provides domain patterns
- ClassificationStatisticsTracker: Tracks classification metrics

These components replace the monolithic SuperOrchestratorService pattern violations.
"""

from .classification_statistics_tracker import ClassificationStatisticsTracker
from .domain_classifier import ClassificationResult, DomainClassifier
from .domain_pattern_repository import DomainPatternRepository

__all__ = [
    "DomainClassifier",
    "ClassificationResult",
    "DomainPatternRepository",
    "ClassificationStatisticsTracker",
]
