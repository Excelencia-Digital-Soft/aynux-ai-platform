"""
Evaluation module for ConversaShop LangSmith integration.

This module provides comprehensive evaluation capabilities including:
- Custom evaluators for agent performance
- Dataset management for testing
- Metrics collection and analysis
"""

from .langsmith_evaluators import (
    ConversaShopEvaluators,
    EvaluationResult,
    create_langsmith_evaluators,
    get_evaluators_instance
)

from .datasets import (
    ConversationExample,
    DatasetManager,
    get_dataset_manager
)

from .metrics import (
    ConversaShopMetrics,
    MetricsSummary,
    MetricType,
    MetricTrend,
    get_metrics_collector
)

__all__ = [
    # Evaluators
    "ConversaShopEvaluators",
    "EvaluationResult", 
    "create_langsmith_evaluators",
    "get_evaluators_instance",
    
    # Datasets
    "ConversationExample",
    "DatasetManager",
    "get_dataset_manager",
    
    # Metrics
    "ConversaShopMetrics",
    "MetricsSummary", 
    "MetricType",
    "MetricTrend",
    "get_metrics_collector"
]