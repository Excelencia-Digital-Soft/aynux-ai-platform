"""
Dynamic SQL Tool Module.

Provides AI-powered SQL generation and execution capabilities.
Refactored following Single Responsibility Principle (SRP).

Components:
- DynamicSQLTool: Main facade for SQL operations
- SQLIntentAnalyzer: Analyzes user queries to understand intent
- SQLQueryGenerator: Generates SQL from natural language
- SQLValidator: Validates and sanitizes SQL queries
- SQLExecutor: Executes queries safely
- SQLContextGenerator: Generates AI-consumable context from results

Usage:
    ```python
    from app.core.tools.dynamic_sql import DynamicSQLTool

    tool = DynamicSQLTool()
    result = await tool(
        user_query="Show me the top 5 selling products",
        user_id="user123"
    )
    print(result.data)
    ```
"""

import logging
from datetime import datetime
from typing import List, Optional

from app.integrations.llm import OllamaLLM

from .context_generator import SQLContextGenerator
from .executor import SQLExecutor
from .intent_analyzer import SQLIntentAnalyzer
from .models import SQLExecutionResult, SQLGenerationContext
from .query_generator import SQLQueryGenerator
from .schema_inspector import SchemaInspector
from .validator import SQLValidator

logger = logging.getLogger(__name__)

# Re-export models for backwards compatibility
__all__ = [
    "DynamicSQLTool",
    "SQLGenerationContext",
    "SQLExecutionResult",
    "SQLIntentAnalyzer",
    "SQLQueryGenerator",
    "SQLValidator",
    "SQLExecutor",
    "SQLContextGenerator",
    "SchemaInspector",
]


class DynamicSQLTool:
    """
    Facade for Dynamic SQL Generation and Execution.

    This tool orchestrates all SQL components to:
    1. Understand user intent from natural language
    2. Generate safe, optimized SQL queries
    3. Execute queries against the database
    4. Convert results to embedding-ready context
    5. Provide rich context for agent responses

    Single Responsibility: Orchestrate SQL operations (facade pattern).

    Example:
        ```python
        tool = DynamicSQLTool()
        result = await tool(
            user_query="Show orders from last week",
            user_id="user123",
            max_results=50
        )
        if result.success:
            print(f"Found {result.row_count} records")
            print(result.embedding_context)
        ```
    """

    def __init__(self, ollama: OllamaLLM | None = None):
        """
        Initialize Dynamic SQL Tool with all components.

        Args:
            ollama: OllamaLLM instance (optional, creates default if not provided)
        """
        self._ollama = ollama or OllamaLLM()

        # Initialize all components
        self._intent_analyzer = SQLIntentAnalyzer(self._ollama)
        self._query_generator = SQLQueryGenerator(self._ollama)
        self._validator = SQLValidator()
        self._executor = SQLExecutor()
        self._context_generator = SQLContextGenerator(self._ollama)

        logger.info("DynamicSQLTool initialized with SRP components")

    async def __call__(
        self,
        user_query: str,
        user_id: Optional[str] = None,
        table_constraints: Optional[List[str]] = None,
        max_results: int = 100,
    ) -> SQLExecutionResult:
        """
        Main entry point for dynamic SQL generation and execution.

        Args:
            user_query: Natural language query from user
            user_id: User identifier for data filtering
            table_constraints: Limit search to specific tables
            max_results: Maximum number of rows to return

        Returns:
            Complete execution result with data and context
        """
        generated_sql = ""

        try:
            start_time = datetime.now()

            # 1. Analyze intent and extract query components
            intent_analysis = await self._intent_analyzer.analyze(user_query)

            # 2. Build context for SQL generation
            context = await self._query_generator.build_context(
                user_query, intent_analysis, table_constraints, user_id, max_results
            )

            # 3. Generate SQL query using AI
            generated_sql = await self._query_generator.generate(context)

            # 4. Validate and sanitize the SQL
            validated_sql = self._validator.validate_and_sanitize(generated_sql, context)

            # 5. Execute the query
            results = await self._executor.execute(validated_sql, user_id)

            # 6. Generate embedding-ready context
            embedding_context = await self._context_generator.generate(
                user_query, results, intent_analysis
            )

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return SQLExecutionResult(
                success=True,
                data=results,
                row_count=len(results),
                generated_sql=validated_sql,
                execution_time_ms=execution_time,
                embedding_context=embedding_context,
            )

        except Exception as e:
            logger.error(f"Error in dynamic SQL execution: {str(e)}")
            return SQLExecutionResult(
                success=False,
                error_message=str(e),
                generated_sql=generated_sql,
            )

    # Expose component access for advanced usage
    @property
    def intent_analyzer(self) -> SQLIntentAnalyzer:
        """Access the intent analyzer component."""
        return self._intent_analyzer

    @property
    def query_generator(self) -> SQLQueryGenerator:
        """Access the query generator component."""
        return self._query_generator

    @property
    def validator(self) -> SQLValidator:
        """Access the SQL validator component."""
        return self._validator

    @property
    def executor(self) -> SQLExecutor:
        """Access the SQL executor component."""
        return self._executor

    @property
    def context_generator(self) -> SQLContextGenerator:
        """Access the context generator component."""
        return self._context_generator
