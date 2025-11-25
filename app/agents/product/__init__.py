"""
Product agent components - SOLID refactored architecture.

This package contains specialized components for product search and response generation:
- intent_analyzer: AI-powered user intent analysis
- search_strategy_manager: Search strategy orchestration with fallback
- response_generator_manager: AI response generation coordination
- catalog_manager: WhatsApp catalog integration
- product_formatter: Fallback response formatting
- strategies: Search strategy implementations
- generators: Response generator implementations
"""

from .intent_analyzer import IntentAnalyzer
from .models import SearchResult, SearchStrategyType, UserIntent
from .search_strategy_manager import SearchStrategyManager
from .strategies import (
    DatabaseSearchStrategy,
    PgVectorSearchStrategy,
)

__all__ = [
    "UserIntent",
    "SearchResult",
    "SearchStrategyType",
    "IntentAnalyzer",
    "SearchStrategyManager",
    "PgVectorSearchStrategy",
    "DatabaseSearchStrategy",
]
