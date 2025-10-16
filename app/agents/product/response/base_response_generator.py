"""
Base Response Generator - Abstract Interface

Defines the contract for all response generators following the Strategy Pattern.
Enables different response generation strategies without coupling (Open/Closed Principle).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ResponseContext:
    """
    Value object containing context for response generation.

    Encapsulates all information needed to generate a response.
    """

    def __init__(
        self,
        products: List[Dict[str, Any]],
        user_query: str,
        intent_analysis: Dict[str, Any],
        search_metadata: Optional[Dict[str, Any]] = None,
        conversation_state: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize response context.

        Args:
            products: List of product dictionaries
            user_query: Original user query
            intent_analysis: Analyzed user intent
            search_metadata: Metadata from search operation
            conversation_state: Current conversation state
        """
        self.products = products
        self.user_query = user_query
        self.intent_analysis = intent_analysis
        self.search_metadata = search_metadata or {}
        self.conversation_state = conversation_state or {}

    @property
    def product_count(self) -> int:
        """Get number of products."""
        return len(self.products)

    @property
    def has_products(self) -> bool:
        """Check if there are any products."""
        return len(self.products) > 0


class GeneratedResponse:
    """
    Value object representing a generated response.

    Encapsulates response text and metadata.
    """

    def __init__(
        self,
        text: str,
        response_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        requires_followup: bool = False,
    ):
        """
        Initialize generated response.

        Args:
            text: Response text to send to user
            response_type: Type identifier (e.g., "ai_generated", "catalog", "fallback")
            metadata: Additional response metadata
            requires_followup: Whether response requires user follow-up action
        """
        self.text = text
        self.response_type = response_type
        self.metadata = metadata or {}
        self.requires_followup = requires_followup

    def __repr__(self) -> str:
        return (
            f"GeneratedResponse(type={self.response_type}, "
            f"length={len(self.text)}, "
            f"followup={self.requires_followup})"
        )


class BaseResponseGenerator(ABC):
    """
    Abstract base class for response generators.

    Defines the interface for generating user-facing responses.
    Follows Interface Segregation Principle - focused interface.
    """

    @abstractmethod
    async def generate(self, context: ResponseContext) -> GeneratedResponse:
        """
        Generate response text from context.

        Args:
            context: Response context with products and metadata

        Returns:
            GeneratedResponse with text and metadata

        Raises:
            NotImplementedError: Must be implemented by concrete generators
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get generator name identifier.

        Returns:
            Generator name (e.g., "ai", "fallback", "catalog")
        """
        pass

    @property
    def priority(self) -> int:
        """
        Get generator priority for fallback ordering.

        Lower numbers = higher priority (tried first).
        Default priority is 50 (medium).

        Returns:
            Priority value (0-100)
        """
        return 50

    async def can_generate(self, context: ResponseContext) -> bool:
        """
        Check if this generator can handle the given context.

        Default implementation returns True (generator can handle any context).
        Override for generators with specific requirements.

        Args:
            context: Response context

        Returns:
            True if generator can handle this context
        """
        return True

    async def health_check(self) -> bool:
        """
        Check if generator is healthy and available.

        Default implementation returns True.
        Override for generators with external dependencies.

        Returns:
            True if generator is operational
        """
        return True
