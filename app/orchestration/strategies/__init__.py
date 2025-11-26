"""
Orchestration Routing Strategies

Provides multiple routing strategies for domain classification:
- KeywordRoutingStrategy: Fast, rule-based routing using keywords
- AIBasedRoutingStrategy: LLM-powered intelligent routing
- HybridRoutingStrategy: Combines keyword and AI for optimal performance
"""

from app.orchestration.strategies.ai_based_routing import (
    AIBasedRoutingStrategy,
    AIRoutingResult,
    DomainDescription,
)
from app.orchestration.strategies.hybrid_routing import (
    HybridRoutingResult,
    HybridRoutingStrategy,
)
from app.orchestration.strategies.keyword_routing import (
    DomainKeywords,
    KeywordRoutingStrategy,
    RoutingResult,
)

__all__ = [
    # Keyword Routing
    "KeywordRoutingStrategy",
    "DomainKeywords",
    "RoutingResult",
    # AI Routing
    "AIBasedRoutingStrategy",
    "AIRoutingResult",
    "DomainDescription",
    # Hybrid Routing
    "HybridRoutingStrategy",
    "HybridRoutingResult",
]
