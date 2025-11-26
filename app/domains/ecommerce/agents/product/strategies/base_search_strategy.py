"""
Base Search Strategy - Abstract Interface

Defines the contract for all product search strategies following the Strategy Pattern.
This enables adding new search methods without modifying existing code (Open/Closed Principle).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SearchResult:
    """
    Value object representing a search result.

    Encapsulates product data and search metadata for consistency across strategies.
    """

    def __init__(
        self,
        products: List[Dict[str, Any]],
        source: str,
        query: str,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """
        Initialize search result.

        Args:
            products: List of product dictionaries
            source: Search source identifier (e.g., "pgvector", "database")
            query: Original search query
            metadata: Additional search metadata (similarity scores, filters, etc.)
            success: Whether search was successful
            error: Error message if search failed
        """
        self.products = products
        self.source = source
        self.query = query
        self.metadata = metadata or {}
        self.success = success
        self.error = error

    def __repr__(self) -> str:
        return f"SearchResult(source={self.source}, products={len(self.products)}, success={self.success})"


class BaseSearchStrategy(ABC):
    """
    Abstract base class for product search strategies.

    Defines the interface that all search strategies must implement.
    Follows Interface Segregation Principle - small, focused interface.
    """

    @abstractmethod
    async def search(self, user_query: str, intent_analysis: Dict[str, Any], limit: int = 10) -> SearchResult:
        """
        Execute product search based on query and intent.

        Args:
            user_query: Raw user query text
            intent_analysis: Analyzed user intent with extracted parameters
            limit: Maximum number of results to return

        Returns:
            SearchResult object containing products and metadata

        Raises:
            NotImplementedError: Must be implemented by concrete strategies
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if search strategy is healthy and available.

        Returns:
            True if strategy is operational, False otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get strategy name identifier.

        Returns:
            Strategy name (e.g., "pgvector", "database")
        """
        pass

    @property
    def priority(self) -> int:
        """
        Get strategy priority for fallback ordering.

        Lower numbers = higher priority (executed first).
        Default priority is 50 (medium).

        Returns:
            Priority value (0-100)
        """
        return 50

    async def can_handle(self, _intent_analysis: Dict[str, Any]) -> bool:
        """
        Check if this strategy can handle the given intent.

        Default implementation returns True (strategy can handle any intent).
        Override for strategies with specific capabilities.

        Args:
            intent_analysis: Analyzed user intent

        Returns:
            True if strategy can handle this intent
        """
        return True
