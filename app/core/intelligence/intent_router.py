"""Intent router orchestrator with three-tier fallback.

Optimized for speed with intelligent fallback chain:
- Primary: LLM (VllmLLM) for accurate analysis
- Fallback 1: SpaCy NLP for local processing
- Fallback 2: Keyword patterns for last resort

Follows Single Responsibility Principle:
- This class only orchestrates the fallback chain
- Analysis logic delegated to specialized analyzers
- Cache, metrics, validation in separate components
"""

import logging
import time
from typing import Any

from app.core.intelligence.analyzers.keyword_intent_analyzer import (
    KeywordIntentAnalyzer,
)
from app.core.intelligence.analyzers.llm_intent_analyzer import LLMIntentAnalyzer
from app.core.intelligence.cache.intent_cache import IntentCache
from app.core.intelligence.metrics.router_metrics import RouterMetrics
from app.core.intelligence.spacy_intent_analyzer import SpacyIntentAnalyzer
from app.core.intelligence.validators.intent_validator import IntentValidator

logger = logging.getLogger(__name__)


class IntentRouter:
    """Orchestrator for intent routing with three-tier fallback.

    Fallback Chain: LLM → SpaCy → Keywords

    This class follows SRP by only handling orchestration.
    All analysis logic is delegated to specialized components.

    Usage:
        router = IntentRouter(llm=llm_instance)
        result = await router.determine_intent(message)
    """

    def __init__(self, llm: Any = None, config: dict[str, Any] | None = None):
        """Initialize router with components.

        Args:
            llm: Optional VllmLLM instance for LLM analysis
            config: Configuration dict with options:
                - cache_size: Max cache entries (default: 1000)
                - cache_ttl: Cache TTL in seconds (default: 60)
                - confidence_threshold: Min confidence (default: 0.75)
                - use_spacy_fallback: Enable SpaCy fallback (default: True)
        """
        self.llm = llm
        self.config = config or {}

        # Configuration
        self.confidence_threshold = self.config.get("confidence_threshold", 0.75)
        self.use_spacy_fallback = self.config.get("use_spacy_fallback", True)

        # Initialize components (composition over inheritance)
        self._cache = IntentCache(
            max_size=self.config.get("cache_size", 1000),
            ttl_seconds=self.config.get("cache_ttl", 60),
        )
        self._metrics = RouterMetrics()
        self._validator = IntentValidator()

        # Initialize analyzers
        self._llm_analyzer: LLMIntentAnalyzer | None = None
        if llm:
            self._llm_analyzer = LLMIntentAnalyzer(
                llm=llm,
                cache=self._cache,
                validator=self._validator,
                metrics=self._metrics,
            )

        self._spacy_analyzer = SpacyIntentAnalyzer()
        self._keyword_analyzer = KeywordIntentAnalyzer(self._validator)

        logger.info(
            f"IntentRouter initialized - "
            f"cache_size={self._cache._max_size}, "
            f"spacy_available={self._spacy_analyzer.is_available()}"
        )

    async def determine_intent(
        self,
        message: str,
        customer_data: dict[str, Any] | None = None,
        conversation_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Determine user intent using three-tier fallback.

        Fallback chain:
        1. Check for active multi-turn flows
        2. Try LLM analysis (if available)
        3. Try SpaCy analysis (if enabled and available)
        4. Use keyword fallback (always available)

        Args:
            message: User message to analyze
            customer_data: Optional customer context
            conversation_data: Optional conversation context

        Returns:
            Intent result dict with keys:
            - primary_intent: Intent name
            - confidence: Confidence score (0-1)
            - target_agent: Agent to route to
            - method: Analysis method used
            - entities: Extracted entities
        """
        start_time = time.time()
        self._metrics.increment_total_requests()

        context = {
            "customer_data": customer_data,
            "conversation_data": conversation_data,
        }

        # 0. Check for active multi-turn flows
        if flow_result := self._validator.check_active_flow(conversation_data):
            self._update_response_time(start_time)
            return flow_result

        # 1. Try LLM analysis (primary)
        if self._llm_analyzer:
            try:
                logger.debug("Trying LLM analysis...")
                result = await self._llm_analyzer.analyze(message, context)
                if result["confidence"] >= 0.6:
                    self._update_response_time(start_time)
                    return result
                logger.debug(f"LLM confidence too low ({result['confidence']:.2f})")
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}")

        # 2. Try SpaCy analysis (fallback 1)
        if self.use_spacy_fallback and self._spacy_analyzer.is_available():
            try:
                logger.debug("Trying SpaCy analysis...")
                self._metrics.increment_spacy_calls()
                spacy_result = self._spacy_analyzer.analyze_intent(message)

                if spacy_result["confidence"] >= 0.4:
                    result = self._format_spacy_result(spacy_result)
                    self._update_response_time(start_time)
                    return result
                logger.debug(f"SpaCy confidence too low ({spacy_result['confidence']:.2f})")
            except Exception as e:
                logger.warning(f"SpaCy analysis failed: {e}")

        # 3. Keyword fallback (last resort)
        logger.debug("Using keyword fallback...")
        self._metrics.increment_keyword_calls()
        result = await self._keyword_analyzer.analyze(message, context)
        self._update_response_time(start_time)
        return result

    def _format_spacy_result(self, spacy_result: dict[str, Any]) -> dict[str, Any]:
        """Convert SpaCy result to standard format.

        Args:
            spacy_result: Raw result from SpacyIntentAnalyzer

        Returns:
            Standardized intent result dict
        """
        intent = spacy_result.get("intent", "fallback")
        confidence = spacy_result.get("confidence", 0.4)

        return {
            "primary_intent": intent,
            "intent": intent,
            "confidence": confidence,
            "entities": spacy_result.get("analysis", {}).get("entities", []),
            "requires_handoff": False,
            "target_agent": self._validator.map_intent_to_agent(intent),
            "method": spacy_result.get("method", "spacy_nlp"),
            "analysis": spacy_result.get("analysis", {}),
            "reasoning": spacy_result.get("analysis", {}).get("reason", "SpaCy NLP analysis"),
        }

    def _update_response_time(self, start_time: float) -> None:
        """Update response time metrics.

        Args:
            start_time: Request start timestamp
        """
        elapsed = time.time() - start_time
        self._metrics.update_response_time(elapsed)

    # =========================================================================
    # Public API - Backward Compatibility
    # =========================================================================

    @property
    def spacy_analyzer(self) -> SpacyIntentAnalyzer:
        """SpaCy analyzer instance (for OrchestratorAgent compatibility)."""
        return self._spacy_analyzer

    @property
    def _stats(self) -> dict[str, Any]:
        """Raw stats dict (for OrchestratorAgent compatibility)."""
        return self._metrics._stats

    def get_cache_stats(self) -> dict[str, Any]:
        """Get combined cache and router statistics.

        Returns:
            Dict with cache hit rates and router metrics
        """
        return {
            **self._cache.get_stats(),
            **self._metrics.get_stats(),
        }

    def clear_cache(self) -> None:
        """Clear intent cache."""
        self._cache.clear()

    def clear_cache_for_message(self, message: str) -> None:
        """Clear cache for a specific message."""
        self._cache.clear_for_message(message)

    # =========================================================================
    # Legacy method for backward compatibility
    # =========================================================================

    async def analyze_intent_with_llm(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Legacy method - delegates to LLM analyzer.

        Args:
            message: User message
            state_dict: State dictionary with context

        Returns:
            Intent result dict
        """
        if self._llm_analyzer:
            return await self._llm_analyzer.analyze(message, state_dict)
        return await self._keyword_analyzer.analyze(message, state_dict)
