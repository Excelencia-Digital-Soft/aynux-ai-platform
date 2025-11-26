"""
Hybrid Routing Strategy

Combines keyword-based and AI-based routing for optimal accuracy and performance.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.interfaces.llm import ILLM

from .ai_based_routing import AIBasedRoutingStrategy, AIRoutingResult, DomainDescription
from .keyword_routing import DomainKeywords, KeywordRoutingStrategy, RoutingResult

logger = logging.getLogger(__name__)


@dataclass
class HybridRoutingResult:
    """Result of hybrid routing."""

    domain: str
    confidence: float
    strategy_used: str  # "keyword", "ai", "hybrid"
    keyword_result: RoutingResult | None = None
    ai_result: AIRoutingResult | None = None
    processing_time_ms: float = 0.0
    fallback_used: bool = False


class HybridRoutingStrategy:
    """
    Hybrid routing strategy combining keyword and AI approaches.

    Strategy:
    1. First, try fast keyword-based routing
    2. If keyword confidence is high enough, use that result
    3. If not confident, fall back to AI-based routing
    4. Optionally use AI to confirm keyword results

    Benefits:
    - Fast for clear messages (keyword only)
    - Accurate for ambiguous messages (AI fallback)
    - Cost-efficient (minimizes LLM calls)

    Example:
        ```python
        strategy = HybridRoutingStrategy(llm=ollama_llm)

        # Fast for clear messages
        result = await strategy.route("¿Cuánto cuesta el producto X?")
        # Uses keyword routing (fast)

        # Accurate for ambiguous
        result = await strategy.route("Necesito ayuda")
        # Falls back to AI (accurate)
        ```
    """

    def __init__(
        self,
        llm: ILLM,
        default_domain: str = "ecommerce",
        keyword_confidence_threshold: float = 0.5,
        use_ai_confirmation: bool = False,
        ai_confirmation_threshold: float = 0.3,
    ):
        """
        Initialize hybrid routing strategy.

        Args:
            llm: Language model interface
            default_domain: Default domain when all routing fails
            keyword_confidence_threshold: Minimum confidence to use keyword result
            use_ai_confirmation: Whether to confirm keyword results with AI
            ai_confirmation_threshold: Threshold below which to use AI confirmation
        """
        self.llm = llm
        self.default_domain = default_domain
        self.keyword_confidence_threshold = keyword_confidence_threshold
        self.use_ai_confirmation = use_ai_confirmation
        self.ai_confirmation_threshold = ai_confirmation_threshold

        # Initialize sub-strategies
        self.keyword_strategy = KeywordRoutingStrategy(default_domain=default_domain)
        self.ai_strategy = AIBasedRoutingStrategy(llm=llm, default_domain=default_domain)

        # Statistics
        self._stats = {
            "total_requests": 0,
            "keyword_only": 0,
            "ai_fallback": 0,
            "ai_confirmation": 0,
            "total_keyword_time_ms": 0.0,
            "total_ai_time_ms": 0.0,
        }

    async def route(self, message: str, context: dict[str, Any] | None = None) -> HybridRoutingResult:
        """
        Route message using hybrid strategy.

        Args:
            message: User message
            context: Optional additional context

        Returns:
            Hybrid routing result
        """
        start_time = time.perf_counter()
        self._stats["total_requests"] += 1

        # Step 1: Try keyword routing (fast)
        keyword_start = time.perf_counter()
        keyword_result = self.keyword_strategy.route(message, context)
        keyword_time = (time.perf_counter() - keyword_start) * 1000
        self._stats["total_keyword_time_ms"] += keyword_time

        # Step 2: Check if keyword result is confident enough
        if keyword_result.confidence >= self.keyword_confidence_threshold:
            # High confidence - use keyword result directly
            self._stats["keyword_only"] += 1
            total_time = (time.perf_counter() - start_time) * 1000

            logger.debug(
                f"Hybrid routing: keyword confident ({keyword_result.confidence:.2f}) "
                f"-> {keyword_result.domain} in {total_time:.1f}ms"
            )

            return HybridRoutingResult(
                domain=keyword_result.domain,
                confidence=keyword_result.confidence,
                strategy_used="keyword",
                keyword_result=keyword_result,
                processing_time_ms=total_time,
            )

        # Step 3: Check if we should use AI confirmation
        if (
            self.use_ai_confirmation
            and keyword_result.confidence >= self.ai_confirmation_threshold
            and keyword_result.confidence < self.keyword_confidence_threshold
        ):
            # Medium confidence - confirm with AI
            return await self._confirm_with_ai(message, keyword_result, context, start_time)

        # Step 4: Low confidence - use AI routing
        ai_start = time.perf_counter()
        ai_result = await self.ai_strategy.route(message, context)
        ai_time = (time.perf_counter() - ai_start) * 1000
        self._stats["total_ai_time_ms"] += ai_time
        self._stats["ai_fallback"] += 1

        total_time = (time.perf_counter() - start_time) * 1000

        logger.debug(
            f"Hybrid routing: AI fallback (keyword conf: {keyword_result.confidence:.2f}) "
            f"-> {ai_result.domain} in {total_time:.1f}ms"
        )

        return HybridRoutingResult(
            domain=ai_result.domain,
            confidence=ai_result.confidence,
            strategy_used="ai",
            keyword_result=keyword_result,
            ai_result=ai_result,
            processing_time_ms=total_time,
            fallback_used=True,
        )

    async def _confirm_with_ai(
        self,
        message: str,
        keyword_result: RoutingResult,
        context: dict[str, Any] | None,
        start_time: float,
    ) -> HybridRoutingResult:
        """
        Confirm keyword result with AI.

        Args:
            message: Original message
            keyword_result: Keyword routing result
            context: Additional context
            start_time: Time when routing started

        Returns:
            Confirmed hybrid result
        """
        ai_start = time.perf_counter()
        ai_result = await self.ai_strategy.route(message, context)
        ai_time = (time.perf_counter() - ai_start) * 1000
        self._stats["total_ai_time_ms"] += ai_time
        self._stats["ai_confirmation"] += 1

        total_time = (time.perf_counter() - start_time) * 1000

        # Check if AI confirms keyword result
        if ai_result.domain == keyword_result.domain:
            # AI confirms keyword - boost confidence
            combined_confidence = min(
                (keyword_result.confidence + ai_result.confidence) / 2 + 0.1, 1.0
            )

            logger.debug(
                f"Hybrid routing: AI confirmed keyword result "
                f"-> {keyword_result.domain} (combined conf: {combined_confidence:.2f})"
            )

            return HybridRoutingResult(
                domain=keyword_result.domain,
                confidence=combined_confidence,
                strategy_used="hybrid",
                keyword_result=keyword_result,
                ai_result=ai_result,
                processing_time_ms=total_time,
            )
        else:
            # AI disagrees - use AI result (it's usually more accurate)
            logger.debug(
                f"Hybrid routing: AI disagrees with keyword "
                f"(keyword: {keyword_result.domain}, AI: {ai_result.domain}) "
                f"-> using AI result"
            )

            return HybridRoutingResult(
                domain=ai_result.domain,
                confidence=ai_result.confidence,
                strategy_used="ai",
                keyword_result=keyword_result,
                ai_result=ai_result,
                processing_time_ms=total_time,
                fallback_used=True,
            )

    def add_domain_keywords(self, config: DomainKeywords) -> None:
        """Add domain keywords to keyword strategy."""
        self.keyword_strategy.add_domain(config)

    def add_domain_description(self, description: DomainDescription) -> None:
        """Add domain description to AI strategy."""
        self.ai_strategy.add_domain(description)

    def get_stats(self) -> dict[str, Any]:
        """
        Get routing statistics.

        Returns:
            Statistics dictionary
        """
        total = self._stats["total_requests"]
        return {
            **self._stats,
            "keyword_only_percentage": (self._stats["keyword_only"] / total * 100) if total > 0 else 0,
            "ai_fallback_percentage": (self._stats["ai_fallback"] / total * 100) if total > 0 else 0,
            "ai_confirmation_percentage": (self._stats["ai_confirmation"] / total * 100) if total > 0 else 0,
            "avg_keyword_time_ms": (self._stats["total_keyword_time_ms"] / total) if total > 0 else 0,
            "avg_ai_time_ms": (
                self._stats["total_ai_time_ms"] / (self._stats["ai_fallback"] + self._stats["ai_confirmation"])
                if (self._stats["ai_fallback"] + self._stats["ai_confirmation"]) > 0
                else 0
            ),
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_requests": 0,
            "keyword_only": 0,
            "ai_fallback": 0,
            "ai_confirmation": 0,
            "total_keyword_time_ms": 0.0,
            "total_ai_time_ms": 0.0,
        }

    def get_available_domains(self) -> list[str]:
        """Get list of all configured domains."""
        keyword_domains = set(self.keyword_strategy.domains.keys())
        ai_domains = set(self.ai_strategy.domains.keys())
        return list(keyword_domains | ai_domains)
