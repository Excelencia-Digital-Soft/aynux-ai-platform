"""
Base abstract class for product search strategies.

All search strategies must extend this class and implement the required methods.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from ..models import SearchResult, UserIntent


class BaseSearchStrategy(ABC):
    """
    Abstract base class for all product search strategies.

    This class defines the interface that all search strategies must implement,
    ensuring they are substitutable (Liskov Substitution Principle).
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize search strategy with configuration.

        Args:
            config: Strategy-specific configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def search(self, query: str, intent: UserIntent, max_results: int) -> SearchResult:
        """
        Execute search strategy.

        This is the main method that performs the product search using
        the strategy's specific implementation.

        Args:
            query: User's search query (natural language)
            intent: Analyzed user intent with structured data
            max_results: Maximum number of products to return

        Returns:
            SearchResult with found products and metadata

        Raises:
            Exception: If search fails critically
        """
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """
        Unique identifier for this strategy.

        Returns:
            String name identifying this strategy (e.g., "pgvector", "chroma")
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if strategy is operational.

        This should verify that all required dependencies and services
        are available and working.

        Returns:
            True if healthy and ready to search, False otherwise
        """
        pass

    def get_config(self) -> Dict[str, Any]:
        """
        Get current strategy configuration.

        Returns:
            Configuration dictionary
        """
        return self.config.copy()

    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update strategy configuration.

        Args:
            config: New configuration values (merged with existing)
        """
        self.config.update(config)
        self.logger.info(f"Configuration updated for {self.strategy_name}")

    def get_trace_metadata(self) -> Dict[str, Any]:
        """
        Get metadata for LangSmith tracing.

        Returns:
            Dictionary with trace metadata
        """
        return {
            "strategy_name": self.strategy_name,
            "strategy_class": self.__class__.__name__,
            "config": self.get_config(),
        }

    def _log_search_start(self, query: str, intent: UserIntent, max_results: int) -> None:
        """
        Log search start (helper method for implementations).

        Args:
            query: Search query
            intent: User intent
            max_results: Maximum results requested
        """
        self.logger.info(
            f"{self.strategy_name} search started: query='{query[:50]}', "
            f"intent={intent.intent}, max_results={max_results}"
        )

    def _log_search_result(self, result: SearchResult) -> None:
        """
        Log search result (helper method for implementations).

        Args:
            result: Search result to log
        """
        status = "success" if result.success else "failed"
        product_count = len(result.products) if result.success else 0

        self.logger.info(
            f"{self.strategy_name} search {status}: "
            f"products={product_count}, "
            f"source={result.source}, "
            f"error={result.error or 'none'}"
        )

    async def can_handle(self, _intent_analysis: Dict[str, Any]) -> bool:
        """
        Check if this strategy can handle the given intent.

        Default implementation returns True (strategy can handle any intent).
        Override for strategies with specific capabilities.

        Args:
            _intent_analysis: Analyzed user intent (dict or UserIntent object)

        Returns:
            True if strategy can handle this intent
        """
        return True
