"""
Dynamic SQL Tool - DEPRECATED.

This module has been refactored to follow Single Responsibility Principle (SRP).
Please use the new module: app.core.tools.dynamic_sql

Migration Guide:
    # Before (deprecated):
    from app.core.tools.dynamic_sql_tool import DynamicSQLTool, SQLExecutionResult

    # After (new):
    from app.core.tools.dynamic_sql import DynamicSQLTool, SQLExecutionResult

The new module structure:
    app/core/tools/dynamic_sql/
    ├── __init__.py           # DynamicSQLTool (facade) + re-exports
    ├── models.py             # SQLGenerationContext, SQLExecutionResult
    ├── intent_analyzer.py    # SQLIntentAnalyzer
    ├── schema_inspector.py   # SchemaInspector
    ├── query_generator.py    # SQLQueryGenerator
    ├── validator.py          # SQLValidator
    ├── executor.py           # SQLExecutor
    └── context_generator.py  # SQLContextGenerator
"""

import warnings

# Re-export from new location for backwards compatibility
from app.core.tools.dynamic_sql import (
    DynamicSQLTool,
    SQLContextGenerator,
    SQLExecutionResult,
    SQLExecutor,
    SQLGenerationContext,
    SQLIntentAnalyzer,
    SQLQueryGenerator,
    SQLValidator,
    SchemaInspector,
)

# Issue deprecation warning on import
warnings.warn(
    "app.core.tools.dynamic_sql_tool is deprecated. "
    "Use app.core.tools.dynamic_sql instead.",
    DeprecationWarning,
    stacklevel=2,
)

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
