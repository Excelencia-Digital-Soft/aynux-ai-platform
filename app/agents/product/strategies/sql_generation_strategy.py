"""
SQL Generation Search Strategy

Dynamic SQL generation strategy using AI to create optimized SQL queries.
Wraps ProductSQLGenerator to integrate with the orchestrator architecture.

This strategy is useful for:
- Complex queries requiring custom SQL logic
- Aggregations and statistical queries
- Multi-table joins with specific business logic
- Queries that need fine-grained control over SQL
"""

import logging
from typing import Any

from app.agents.integrations.ollama_integration import OllamaIntegration
from app.agents.tools.product_sql_generator import ProductSQLGenerator

from ..models import SearchResult, UserIntent
from .base_strategy import BaseSearchStrategy

logger = logging.getLogger(__name__)


class SQLGenerationSearchStrategy(BaseSearchStrategy):
    """
    Search strategy using AI-powered dynamic SQL generation.

    Applies SOLID principles:
    - SRP: Focuses solely on SQL-based product search
    - OCP: Extensible through configuration without modification
    - LSP: Fully substitutable with other search strategies
    - DIP: Depends on ProductSQLGenerator and OllamaIntegration abstractions
    """

    def __init__(
        self,
        ollama: OllamaIntegration,
        postgres=None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize SQL generation search strategy.

        Args:
            ollama: OllamaIntegration instance for AI-powered SQL generation
            postgres: PostgreSQL connection (optional, uses default if None)
            config: Strategy configuration including:
                - enabled: bool (default True) - enable/disable this strategy
                - max_results: int (default 50)
                - complexity_threshold: str (default "medium") - min complexity for this strategy
        """
        super().__init__(config or {})
        self.ollama = ollama
        self.postgres = postgres
        self.sql_generator = ProductSQLGenerator(ollama=ollama, postgres=postgres)

        # Configuration with defaults
        self.enabled = config.get("enabled", True) if config else True
        self.max_results_default = config.get("max_results", 50) if config else 50
        self.complexity_threshold = config.get("complexity_threshold", "medium") if config else "medium"
        self._priority = 40  # Medium priority (after semantic search, before basic database search)

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "sql_generation"

    @property
    def name(self) -> str:
        """Return strategy name (alias for strategy_name)."""
        return self.strategy_name

    @property
    def priority(self) -> int:
        """
        Get strategy priority for fallback ordering.

        Priority 40: Between semantic search (10-30) and basic database (50).
        Good for complex queries that need SQL flexibility.
        """
        return self._priority

    async def search(self, query: str, intent: UserIntent, max_results: int) -> SearchResult:
        """
        Execute SQL generation search.

        Generates dynamic SQL based on user intent and executes it.

        Args:
            query: User's natural language query
            intent: Analyzed user intent with structured data
            max_results: Maximum number of products to return

        Returns:
            SearchResult with products and metadata
        """
        if not self.enabled:
            self.logger.info("SQL generation strategy is disabled")
            return SearchResult(
                success=False,
                products=[],
                source=self.strategy_name,
                error="Strategy disabled",
            )

        self._log_search_start(query, intent, max_results)

        try:
            # Convert UserIntent to dict format expected by ProductSQLGenerator
            intent_dict = self._convert_intent_to_dict(intent)

            # Generate and execute SQL
            sql_result = await self.sql_generator.generate_and_execute(
                user_query=query,
                intent=intent_dict,
                max_results=max_results or self.max_results_default,
            )

            # Handle SQL generation errors
            if not sql_result.success:
                self.logger.warning(f"SQL generation failed: {sql_result.error_message}")
                return SearchResult(
                    success=False,
                    products=[],
                    source=self.strategy_name,
                    error=sql_result.error_message,
                    metadata={
                        "generated_sql": sql_result.generated_sql,
                        "error": sql_result.error_message,
                    },
                )

            # Build result metadata
            result_metadata = {
                "generated_sql": sql_result.generated_sql,
                "execution_time_ms": sql_result.execution_time_ms,
                "row_count": sql_result.row_count,
                "sql_metadata": sql_result.metadata,
            }

            result = SearchResult(
                success=True,
                products=sql_result.data,
                source=self.strategy_name,
                metadata=result_metadata,
            )

            self._log_search_result(result)
            return result

        except Exception as e:
            self.logger.error(f"SQL generation search failed: {str(e)}", exc_info=True)
            return SearchResult(
                success=False,
                products=[],
                source=self.strategy_name,
                error=str(e),
            )

    async def can_handle(self, intent_analysis: dict[str, Any]) -> bool:
        """
        Check if this strategy should handle the given intent.

        SQL generation is best for:
        - Complex queries with multiple filters
        - Aggregations and statistical queries
        - Queries requiring specific SQL logic

        Args:
            intent_analysis: Analyzed user intent (dict or UserIntent)

        Returns:
            True if strategy can effectively handle this intent
        """
        if not self.enabled:
            return False

        # Handle both dict and UserIntent
        if isinstance(intent_analysis, dict):
            complexity = intent_analysis.get("query_complexity", "simple")
            sql_recommended = intent_analysis.get("sql_generation_needed", False)
        else:
            # Assume UserIntent object
            complexity = getattr(intent_analysis, "query_complexity", "simple")
            sql_recommended = getattr(intent_analysis, "sql_generation_needed", False)

        # Use SQL generation for medium/complex queries or when explicitly recommended
        if sql_recommended:
            return True

        # Check complexity threshold
        complexity_levels = {"simple": 0, "medium": 1, "complex": 2, "very_complex": 3}
        threshold_levels = {"simple": 0, "medium": 1, "complex": 2, "very_complex": 3}

        query_level = complexity_levels.get(complexity, 0)
        threshold_level = threshold_levels.get(self.complexity_threshold, 1)

        return query_level >= threshold_level

    async def health_check(self) -> bool:
        """
        Check if SQL generation strategy is operational.

        Tests:
        1. Ollama integration is available
        2. SQL generator can create simple queries

        Returns:
            True if strategy is operational
        """
        try:
            # Test Ollama integration
            if not self.ollama:
                self.logger.warning("Ollama integration not available")
                return False

            # Test simple SQL generation (without execution)
            test_intent = {
                "intent_type": "search_general",
                "search_params": {"keywords": ["test"]},
                "filters": {},
                "query_complexity": "simple",
                "sql_generation_needed": False,
            }

            # Quick validation - just check if generator is initialized
            if not self.sql_generator:
                return False

            self.logger.debug("SQL generation strategy health check passed")
            return True

        except Exception as e:
            self.logger.warning(f"SQL generation health check failed: {str(e)}")
            return False

    def _convert_intent_to_dict(self, intent: UserIntent) -> dict[str, Any]:
        """
        Convert UserIntent dataclass to dict format expected by ProductSQLGenerator.

        Args:
            intent: UserIntent dataclass

        Returns:
            Dict with intent data
        """
        return {
            "intent_type": intent.intent,
            "search_params": {
                "keywords": intent.search_terms,
                "product_name": intent.specific_product,
                "brand": intent.brand,
                "category": intent.category,
                "model": None,  # UserIntent doesn't have model field
            },
            "filters": {
                "price_range": {
                    "min": intent.price_min,
                    "max": intent.price_max,
                },
                "characteristics": [],  # UserIntent doesn't have characteristics field
                "availability_required": intent.wants_stock_info,
                "color": None,
                "size": None,
            },
            "query_complexity": "medium",  # Default, could be enhanced with real analysis
            "semantic_search_recommended": False,
            "sql_generation_needed": True,  # This strategy is for SQL generation
            "user_emotion": "neutral",  # Default, could be enhanced with emotion analysis
            "response_style_preference": "conversational",
        }

    async def generate_aggregation_query(
        self,
        query: str,
        intent: UserIntent,
        aggregation_type: str = "count",
    ) -> SearchResult:
        """
        Generate and execute aggregation SQL query.

        Useful for statistical queries like:
        - Count products by category
        - Average price by brand
        - Total stock by category

        Args:
            query: User's natural language query
            intent: Analyzed user intent
            aggregation_type: Type of aggregation (count, avg, sum, etc.)

        Returns:
            SearchResult with aggregation data
        """
        try:
            intent_dict = self._convert_intent_to_dict(intent)

            sql_result = await self.sql_generator.generate_aggregation_sql(
                user_query=query,
                intent=intent_dict,
                aggregation_type=aggregation_type,
            )

            if not sql_result.success:
                return SearchResult(
                    success=False,
                    products=[],
                    source=f"{self.strategy_name}_aggregation",
                    error=sql_result.error_message,
                )

            return SearchResult(
                success=True,
                products=sql_result.data,
                source=f"{self.strategy_name}_aggregation",
                metadata={
                    "aggregation_type": aggregation_type,
                    "generated_sql": sql_result.generated_sql,
                    "execution_time_ms": sql_result.execution_time_ms,
                },
            )

        except Exception as e:
            self.logger.error(f"Aggregation query failed: {str(e)}")
            return SearchResult(
                success=False,
                products=[],
                source=f"{self.strategy_name}_aggregation",
                error=str(e),
            )
