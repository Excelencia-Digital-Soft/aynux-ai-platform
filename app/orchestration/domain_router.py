# ============================================================================
# SCOPE: GLOBAL
# Description: Router de dominios basado en análisis de intención.
#              Estrategias: keyword, AI-based, hybrid.
# Tenant-Aware: No - ruteo global. Los dominios habilitados por tenant
#              se filtran en TenantAgentFactory.
# ============================================================================
"""
Domain Router

Routes incoming messages to appropriate domain services based on intent analysis.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict

from app.orchestration.strategies import (
    AIBasedRoutingStrategy,
    HybridRoutingStrategy,
    KeywordRoutingStrategy,
)

logger = logging.getLogger(__name__)


class RouterStats(TypedDict):
    """Type definition for router statistics."""

    total_requests: int
    by_domain: dict[str, int]
    by_strategy: dict[str, int]


@dataclass
class RoutingDecision:
    """Result of domain routing decision."""

    domain: str
    confidence: float
    strategy_used: str
    intent_type: str | None
    metadata: dict[str, Any]
    timestamp: datetime


class DomainRouter:
    """
    Routes messages to appropriate domain services.

    Supports multiple routing strategies:
    - Keyword-based: Fast, rule-based routing
    - AI-based: LLM-powered intent classification
    - Hybrid: Combines both for accuracy and speed

    Example:
        ```python
        router = DomainRouter(
            llm=ollama_llm,
            strategy="hybrid",
            default_domain="ecommerce",
        )

        decision = await router.route(
            message="Quiero saber el precio de un producto",
            context={"customer_id": 123}
        )
        print(decision.domain)  # "ecommerce"
        ```
    """

    SUPPORTED_DOMAINS = ["healthcare", "credit", "excelencia"]

    def __init__(
        self,
        llm: Any = None,
        strategy: str = "hybrid",
        default_domain: str = "excelencia",
        enabled_domains: list[str] | None = None,
    ):
        """
        Initialize domain router.

        Args:
            llm: Language model for AI-based routing
            strategy: Routing strategy ("keyword", "ai", "hybrid")
            default_domain: Default domain when routing fails
            enabled_domains: List of enabled domains
        """
        self.llm = llm
        self.strategy_type = strategy
        self.default_domain = default_domain
        self.enabled_domains = enabled_domains or self.SUPPORTED_DOMAINS

        # Initialize routing strategy
        self._init_strategy()

        # Statistics
        self._stats: RouterStats = {
            "total_requests": 0,
            "by_domain": {d: 0 for d in self.SUPPORTED_DOMAINS},
            "by_strategy": {"keyword": 0, "ai": 0, "hybrid": 0},
        }

        logger.info(f"DomainRouter initialized with strategy={strategy}, domains={self.enabled_domains}")

    def _init_strategy(self) -> None:
        """Initialize routing strategy based on configuration."""
        if self.strategy_type == "keyword":
            self.strategy = KeywordRoutingStrategy(default_domain=self.default_domain)
        elif self.strategy_type == "ai" and self.llm:
            self.strategy = AIBasedRoutingStrategy(
                llm=self.llm,
                default_domain=self.default_domain,
            )
        elif self.strategy_type == "hybrid" and self.llm:
            self.strategy = HybridRoutingStrategy(
                llm=self.llm,
                default_domain=self.default_domain,
            )
        else:
            # Fallback to keyword if AI not available
            logger.warning("LLM not provided, falling back to keyword strategy")
            self.strategy = KeywordRoutingStrategy(default_domain=self.default_domain)

    async def route(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """
        Route message to appropriate domain.

        Args:
            message: User message to route
            context: Additional context (customer info, conversation history)

        Returns:
            RoutingDecision with domain and metadata
        """
        self._stats["total_requests"] += 1

        try:
            # Use configured strategy
            result = await self.strategy.route(message, context)

            # Validate domain is enabled
            domain = result.domain if result.domain in self.enabled_domains else self.default_domain

            # Update statistics
            self._stats["by_domain"][domain] = self._stats["by_domain"].get(domain, 0) + 1
            strategy_used = getattr(result, "strategy_used", "keyword")
            self._stats["by_strategy"][strategy_used] = self._stats["by_strategy"].get(strategy_used, 0) + 1

            decision = RoutingDecision(
                domain=domain,
                confidence=result.confidence,
                strategy_used=getattr(result, "strategy_used", "keyword"),
                intent_type=getattr(result, "intent_type", None),
                metadata={
                    "matched_keywords": getattr(result, "matched_keywords", []),
                    "processing_time_ms": getattr(result, "processing_time_ms", 0),
                    "context_used": bool(context),
                },
                timestamp=datetime.now(UTC),
            )

            logger.debug(
                f"Routed message to {domain} (confidence={result.confidence:.2f}, strategy={decision.strategy_used})"
            )

            return decision

        except Exception as e:
            logger.error(f"Error routing message: {e}")

            # Return default on error
            return RoutingDecision(
                domain=self.default_domain,
                confidence=0.0,
                strategy_used="fallback",
                intent_type=None,
                metadata={"error": str(e)},
                timestamp=datetime.now(UTC),
            )

    def add_domain_keywords(
        self,
        domain: str,
        primary_keywords: list[str],
        secondary_keywords: list[str] | None = None,
        patterns: list[str] | None = None,
    ) -> None:
        """
        Add or update keywords for a domain.

        Args:
            domain: Domain name
            primary_keywords: High-confidence keywords
            secondary_keywords: Supporting keywords
            patterns: Regex patterns
        """
        if hasattr(self.strategy, "add_domain_keywords"):
            from app.orchestration.strategies.keyword_routing import DomainKeywords

            config = DomainKeywords(
                domain=domain,
                primary_keywords=primary_keywords,
                secondary_keywords=secondary_keywords or [],
                patterns=patterns or [],
            )
            self.strategy.add_domain_keywords(config)

    def get_available_domains(self) -> list[str]:
        """Get list of enabled domains."""
        return self.enabled_domains

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            **self._stats,
            "strategy_type": self.strategy_type,
            "default_domain": self.default_domain,
        }

    def reset_stats(self) -> None:
        """Reset routing statistics."""
        self._stats = {
            "total_requests": 0,
            "by_domain": {d: 0 for d in self.SUPPORTED_DOMAINS},
            "by_strategy": {"keyword": 0, "ai": 0, "hybrid": 0},
        }
