"""
Data models and protocols for product agent SOLID refactoring.

This module defines:
- Data classes for structured data (UserIntent, SearchResult)
- Protocols (interfaces) for strategy implementations
- Enums for type-safe strategy selection
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class UserIntent:
    """Structured intent analysis result from AI."""

    intent: str
    search_terms: List[str]
    category: Optional[str] = None
    brand: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    specific_product: Optional[str] = None
    wants_stock_info: bool = False
    wants_featured: bool = False
    wants_sale: bool = False
    action_needed: str = "search_products"
    confidence: float = 0.8  # Default confidence score (0.0-1.0)
    user_emotion: str = "neutral"  # User emotion: neutral, excited, frustrated, urgent, curious

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state management."""
        return {
            "intent": self.intent,
            "search_terms": self.search_terms,
            "category": self.category,
            "brand": self.brand,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "specific_product": self.specific_product,
            "wants_stock_info": self.wants_stock_info,
            "wants_featured": self.wants_featured,
            "wants_sale": self.wants_sale,
            "action_needed": self.action_needed,
            "confidence": self.confidence,
            "user_emotion": self.user_emotion,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserIntent":
        """Create from dictionary."""
        return cls(
            intent=data.get("intent", "search_general"),
            search_terms=data.get("search_terms", []),
            category=data.get("category"),
            brand=data.get("brand"),
            price_min=data.get("price_min"),
            price_max=data.get("price_max"),
            specific_product=data.get("specific_product"),
            wants_stock_info=data.get("wants_stock_info", False),
            wants_featured=data.get("wants_featured", False),
            wants_sale=data.get("wants_sale", False),
            action_needed=data.get("action_needed", "search_products"),
            confidence=data.get("confidence", 0.8),
            user_emotion=data.get("user_emotion", "neutral"),
        )


@dataclass
class SearchResult:
    """Standardized search result across all strategies."""

    success: bool
    products: List[Dict[str, Any]]
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def __post_init__(self):
        """Validate search result."""
        if not isinstance(self.products, list):
            raise ValueError("products must be a list")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")


# ============================================================================
# Enums
# ============================================================================


class SearchStrategyType(str, Enum):
    """Available search strategy types."""

    PGVECTOR = "pgvector"
    DATABASE = "database"

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Protocols (Interfaces)
# ============================================================================


class Searchable(Protocol):
    """Protocol for entities that can perform product searches."""

    async def search(self, query: str, intent: UserIntent, max_results: int) -> SearchResult:
        """
        Execute product search.

        Args:
            query: User's search query
            intent: Analyzed user intent
            max_results: Maximum number of results

        Returns:
            SearchResult with found products
        """
        ...

    @property
    def strategy_name(self) -> str:
        """Unique identifier for this strategy."""
        ...


class ResponseGenerator(Protocol):
    """Protocol for AI response generation."""

    async def generate_response(
        self, products: List[Dict[str, Any]], user_message: str, intent: UserIntent, search_metadata: Dict[str, Any]
    ) -> str:
        """
        Generate AI-powered response for products.

        Args:
            products: List of product dictionaries
            user_message: Original user message
            intent: Analyzed user intent
            search_metadata: Additional search metadata

        Returns:
            Generated response text
        """
        ...

    def get_fallback_response(self, products: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
        """
        Generate fallback response when AI fails.

        Args:
            products: List of product dictionaries
            metadata: Search metadata

        Returns:
            Formatted fallback response
        """
        ...


class HealthCheckable(Protocol):
    """Protocol for components that support health monitoring."""

    async def health_check(self) -> bool:
        """
        Check if component is operational.

        Returns:
            True if healthy, False otherwise
        """
        ...


class Configurable(Protocol):
    """Protocol for configurable components."""

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        ...

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update configuration."""
        ...


class Traceable(Protocol):
    """Protocol for LangSmith tracing integration."""

    def get_trace_metadata(self) -> Dict[str, Any]:
        """
        Get metadata for LangSmith tracing.

        Returns:
            Dictionary with trace metadata
        """
        ...
