"""
Data models for Dynamic SQL Tool.

Single Responsibility: Define data structures for SQL generation and execution.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SQLGenerationContext(BaseModel):
    """Context for SQL generation."""

    user_query: str
    available_tables: List[str] = Field(default_factory=list)
    table_schemas: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    user_id: Optional[str] = None
    max_results: int = 100
    safety_constraints: List[str] = Field(default_factory=list)


class SQLExecutionResult(BaseModel):
    """Result of SQL execution."""

    success: bool
    data: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    generated_sql: str = ""
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    embedding_context: Optional[str] = None
