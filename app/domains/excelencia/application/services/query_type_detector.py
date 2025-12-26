"""Query type detection service following SOLID principles.

This module provides a flexible, extensible query type detection system:
- SRP: Each detector has a single responsibility
- OCP: New detection strategies can be added without modifying existing code
- DIP: Components depend on abstractions (Protocol) not concretions

Architecture:
    QueryTypeDetector (Protocol)
         │
         ├── KeywordQueryTypeDetector (Exact matching)
         │
         └── FuzzyQueryTypeDetector (Fuzzy matching for typos)
                    │
         QueryTypeRegistry (Stores types and keywords from YAML)
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Protocol


@dataclass
class QueryTypeMatch:
    """Result of query type detection.

    Attributes:
        query_type: Detected query type (e.g., 'incident', 'feedback', 'general')
        confidence: Confidence score from 0.0 to 1.0
        matched_keyword: The keyword that triggered the match (for debugging)
    """

    query_type: str
    confidence: float
    matched_keyword: str | None = None


class QueryTypeDetector(Protocol):
    """Protocol for query type detection strategies (DIP).

    Implement this protocol to create custom detection strategies.
    """

    def detect(self, message: str) -> QueryTypeMatch:
        """Detect query type from message.

        Args:
            message: User message to analyze

        Returns:
            QueryTypeMatch with detected type and confidence
        """
        ...


@dataclass
class QueryTypeRegistry:
    """Registry for query types and their keywords (OCP - extensible via config).

    This registry stores query types and their associated keywords,
    loaded from YAML configuration. New types can be added by editing
    the YAML file without code changes.

    Attributes:
        types: Dict mapping type names to lists of keywords
        priority_order: List of type names in priority order for matching
    """

    types: dict[str, list[str]] = field(default_factory=dict)
    priority_order: list[str] = field(default_factory=list)

    def add_type(
        self,
        type_name: str,
        keywords: list[str],
        priority: int | None = None,
    ) -> None:
        """Add or update a query type with its keywords.

        Args:
            type_name: Name of the query type
            keywords: List of keywords that trigger this type
            priority: Optional priority position (lower = higher priority)
        """
        self.types[type_name] = keywords
        if type_name not in self.priority_order:
            if priority is not None:
                self.priority_order.insert(priority, type_name)
            else:
                self.priority_order.append(type_name)

    def get_keywords(self, type_name: str) -> list[str]:
        """Get keywords for a specific type.

        Args:
            type_name: Name of the query type

        Returns:
            List of keywords, empty list if type not found
        """
        return self.types.get(type_name, [])

    def get_all_types(self) -> list[str]:
        """Get all registered types in priority order.

        Returns:
            List of type names ordered by matching priority
        """
        return self.priority_order


class KeywordQueryTypeDetector:
    """Detects query type using exact keyword matching (SRP).

    This detector performs simple substring matching, checking if any
    registered keyword appears in the message. It's fast but doesn't
    handle typos.
    """

    def __init__(self, registry: QueryTypeRegistry):
        """Initialize with a query type registry.

        Args:
            registry: Registry containing query types and keywords
        """
        self.registry = registry

    def detect(self, message: str) -> QueryTypeMatch:
        """Detect query type using exact keyword matching.

        Args:
            message: User message to analyze

        Returns:
            QueryTypeMatch with confidence 1.0 for exact matches,
            or 'general' with confidence 0.5 if no match found
        """
        message_lower = message.lower()

        for query_type in self.registry.get_all_types():
            keywords = self.registry.get_keywords(query_type)
            for keyword in keywords:
                if keyword in message_lower:
                    return QueryTypeMatch(
                        query_type=query_type,
                        confidence=1.0,
                        matched_keyword=keyword,
                    )

        return QueryTypeMatch(query_type="general", confidence=0.5)


class FuzzyQueryTypeDetector:
    """Detects query type with fuzzy matching for typos (OCP - extends functionality).

    This detector uses SequenceMatcher to find similar words, allowing it to
    handle common typos like 'incendencia' -> 'incidencia'. It first checks
    for exact matches (confidence 1.0), then falls back to fuzzy matching.

    Attributes:
        similarity_threshold: Minimum similarity ratio to consider a match (0.0-1.0)
        min_word_length: Minimum word length to consider for fuzzy matching
    """

    def __init__(
        self,
        registry: QueryTypeRegistry,
        similarity_threshold: float = 0.8,
        min_word_length: int = 4,
    ):
        """Initialize with registry and matching parameters.

        Args:
            registry: Registry containing query types and keywords
            similarity_threshold: Minimum similarity for fuzzy match (default 0.8)
            min_word_length: Minimum word length to check (default 4)
        """
        self.registry = registry
        self.similarity_threshold = similarity_threshold
        self.min_word_length = min_word_length

    def detect(self, message: str) -> QueryTypeMatch:
        """Detect query type with fuzzy matching.

        First checks for exact keyword matches (confidence 1.0).
        If none found, performs fuzzy matching on individual words.

        Args:
            message: User message to analyze

        Returns:
            QueryTypeMatch with confidence based on similarity,
            or 'general' with confidence 0.5 if no match found
        """
        message_lower = message.lower()
        words = message_lower.split()

        best_match: QueryTypeMatch | None = None
        best_confidence = 0.0

        for query_type in self.registry.get_all_types():
            keywords = self.registry.get_keywords(query_type)

            for keyword in keywords:
                # Exact match first (higher priority)
                if keyword in message_lower:
                    return QueryTypeMatch(
                        query_type=query_type,
                        confidence=1.0,
                        matched_keyword=keyword,
                    )

                # Fuzzy match for individual words
                for word in words:
                    if len(word) < self.min_word_length:
                        continue

                    similarity = SequenceMatcher(None, word, keyword).ratio()

                    if (
                        similarity >= self.similarity_threshold
                        and similarity > best_confidence
                    ):
                        best_confidence = similarity
                        best_match = QueryTypeMatch(
                            query_type=query_type,
                            confidence=similarity,
                            matched_keyword=f"{word}~{keyword}",  # Shows typo~correct
                        )

        return best_match or QueryTypeMatch(query_type="general", confidence=0.5)


class CompositeQueryTypeDetector:
    """Combines multiple detection strategies (Strategy Pattern).

    This composite detector runs multiple strategies and returns the match
    with the highest confidence. It enables combining exact and fuzzy
    matching in a single detection call.

    Example:
        registry = load_query_types_from_yaml()
        detector = CompositeQueryTypeDetector([
            KeywordQueryTypeDetector(registry),
            FuzzyQueryTypeDetector(registry, similarity_threshold=0.8),
        ])
        match = detector.detect("tengo una incendencia")  # Typo handled
    """

    def __init__(self, detectors: list[QueryTypeDetector]):
        """Initialize with list of detection strategies.

        Args:
            detectors: List of QueryTypeDetector implementations to use
        """
        self.detectors = detectors

    def detect(self, message: str) -> QueryTypeMatch:
        """Detect query type using all strategies, return best match.

        Strategies are tried in order. Returns immediately on exact match
        (confidence 1.0), otherwise returns the highest confidence match.

        Args:
            message: User message to analyze

        Returns:
            QueryTypeMatch from the strategy with highest confidence
        """
        best_match: QueryTypeMatch | None = None

        for detector in self.detectors:
            match = detector.detect(message)

            if best_match is None or match.confidence > best_match.confidence:
                best_match = match

            # Early exit on exact match
            if match.confidence == 1.0:
                return match

        return best_match or QueryTypeMatch(query_type="general", confidence=0.5)
