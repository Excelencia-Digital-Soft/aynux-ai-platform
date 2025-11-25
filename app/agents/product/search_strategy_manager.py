"""
Search strategy manager with fallback chain.

Orchestrates multiple search strategies with intelligent fallback and result validation.
"""

import logging
from typing import Dict, List, Optional

from .models import SearchResult, SearchStrategyType, UserIntent
from .strategies.base_strategy import BaseSearchStrategy


class SearchStrategyManager:
    """
    Manages multiple search strategies with fallback chain.

    Applies SOLID principles:
    - SRP: Manages strategy selection and fallback logic only
    - OCP: New strategies can be added without modifying manager
    - LSP: All strategies are substitutable via BaseSearchStrategy
    - ISP: Uses minimal BaseSearchStrategy interface
    - DIP: Depends on BaseSearchStrategy abstraction, not concrete strategies
    """

    def __init__(
        self,
        strategies: Dict[SearchStrategyType, BaseSearchStrategy],
        primary_strategy: SearchStrategyType = SearchStrategyType.PGVECTOR,
        min_results_threshold: int = 2,
    ):
        """
        Initialize search strategy manager.

        Args:
            strategies: Dict mapping strategy types to strategy instances
            primary_strategy: Primary strategy to try first
            min_results_threshold: Minimum results to consider search successful
        """
        self.strategies = strategies
        self.primary_strategy = primary_strategy
        self.min_results_threshold = min_results_threshold
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Validate strategies
        self._validate_strategies()

    def _validate_strategies(self) -> None:
        """Validate that all strategies are properly configured."""
        if not self.strategies:
            raise ValueError("At least one search strategy must be provided")

        if self.primary_strategy not in self.strategies:
            available = list(self.strategies.keys())
            raise ValueError(f"Primary strategy '{self.primary_strategy}' not in available strategies: {available}")

    async def search(
        self,
        query: str,
        intent: UserIntent,
        max_results: int = 10,
        strategy_override: Optional[SearchStrategyType] = None,
    ) -> SearchResult:
        """
        Execute search with automatic fallback chain.

        Args:
            query: User's natural language query
            intent: Analyzed user intent
            max_results: Maximum number of products to return
            strategy_override: Optional strategy to use instead of default chain

        Returns:
            SearchResult from successful strategy or final fallback
        """
        self.logger.info(f"Starting search: query='{query[:50]}', intent={intent.intent}, max_results={max_results}")

        # Use override strategy if specified
        if strategy_override and strategy_override in self.strategies:
            self.logger.info(f"Using override strategy: {strategy_override.value}")
            return await self._execute_strategy(strategy_override, query, intent, max_results)

        # Execute primary strategy first
        result = await self._execute_strategy(self.primary_strategy, query, intent, max_results)

        if self._is_result_sufficient(result):
            self.logger.info(f"Primary strategy '{self.primary_strategy.value}' successful")
            return result

        # Try fallback strategies
        self.logger.info(f"Primary strategy insufficient (results={len(result.products)}), trying fallbacks")
        result = await self._execute_fallback_chain(query, intent, max_results)

        return result

    async def _execute_strategy(
        self,
        strategy_type: SearchStrategyType,
        query: str,
        intent: UserIntent,
        max_results: int,
    ) -> SearchResult:
        """
        Execute single search strategy.

        Args:
            strategy_type: Type of strategy to execute
            query: Search query
            intent: User intent
            max_results: Maximum results

        Returns:
            SearchResult from strategy
        """
        strategy = self.strategies.get(strategy_type)

        if not strategy:
            self.logger.warning(f"Strategy '{strategy_type.value}' not available")
            return SearchResult(
                success=False,
                products=[],
                source=strategy_type.value,
                error="Strategy not available",
            )

        try:
            self.logger.debug(f"Executing strategy: {strategy_type.value}")
            result = await strategy.search(query, intent, max_results)
            return result

        except Exception as e:
            self.logger.error(f"Strategy '{strategy_type.value}' failed: {str(e)}")
            return SearchResult(
                success=False,
                products=[],
                source=strategy_type.value,
                error=str(e),
            )

    async def _execute_fallback_chain(
        self,
        query: str,
        intent: UserIntent,
        max_results: int,
    ) -> SearchResult:
        """
        Execute fallback strategy chain.

        Tries strategies in order: primary → chroma → database

        Args:
            query: Search query
            intent: User intent
            max_results: Maximum results

        Returns:
            SearchResult from first successful strategy or final fallback
        """
        # Define fallback order (excluding primary which already failed)
        fallback_order = [
            SearchStrategyType.CHROMA,
            SearchStrategyType.DATABASE,
        ]

        # Remove primary strategy from fallbacks
        fallback_order = [s for s in fallback_order if s != self.primary_strategy and s in self.strategies]

        # Try each fallback
        for strategy_type in fallback_order:
            self.logger.info(f"Trying fallback strategy: {strategy_type.value}")
            result = await self._execute_strategy(strategy_type, query, intent, max_results)

            if self._is_result_sufficient(result):
                self.logger.info(f"Fallback strategy '{strategy_type.value}' successful")
                return result

        # All strategies failed - return last result with fallback flag
        self.logger.warning("All search strategies exhausted")
        return SearchResult(
            success=False,
            products=[],
            source="fallback_exhausted",
            error="All search strategies failed to find sufficient results",
        )

    def _is_result_sufficient(self, result: SearchResult) -> bool:
        """
        Check if search result meets minimum threshold.

        Args:
            result: Search result to evaluate

        Returns:
            True if result has sufficient products
        """
        if not result.success:
            return False

        return len(result.products) >= self.min_results_threshold

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health of all registered strategies.

        Returns:
            Dict mapping strategy names to health status
        """
        health_status = {}

        for strategy_type, strategy in self.strategies.items():
            try:
                is_healthy = await strategy.health_check()
                health_status[strategy_type.value] = is_healthy
            except Exception as e:
                self.logger.error(f"Health check failed for {strategy_type.value}: {str(e)}")
                health_status[strategy_type.value] = False

        return health_status

    def get_available_strategies(self) -> List[SearchStrategyType]:
        """
        Get list of available strategy types.

        Returns:
            List of registered strategy types
        """
        return list(self.strategies.keys())

    def get_strategy(self, strategy_type: SearchStrategyType) -> Optional[BaseSearchStrategy]:
        """
        Get strategy instance by type.

        Args:
            strategy_type: Type of strategy to retrieve

        Returns:
            Strategy instance or None if not found
        """
        return self.strategies.get(strategy_type)

    def update_primary_strategy(self, strategy_type: SearchStrategyType) -> None:
        """
        Update primary search strategy.

        Args:
            strategy_type: New primary strategy type

        Raises:
            ValueError: If strategy type not available
        """
        if strategy_type not in self.strategies:
            available = list(self.strategies.keys())
            raise ValueError(
                f"Strategy '{strategy_type.value}' not available. Available: {[s.value for s in available]}"
            )

        self.primary_strategy = strategy_type
        self.logger.info(f"Primary strategy updated to: {strategy_type.value}")

    def update_min_results_threshold(self, threshold: int) -> None:
        """
        Update minimum results threshold for successful search.

        Args:
            threshold: New minimum threshold (must be >= 0)

        Raises:
            ValueError: If threshold is negative
        """
        if threshold < 0:
            raise ValueError(f"Threshold must be >= 0, got {threshold}")

        self.min_results_threshold = threshold
        self.logger.info(f"Minimum results threshold updated to: {threshold}")
