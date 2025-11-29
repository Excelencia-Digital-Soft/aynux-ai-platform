"""
SQL Executor.

Single Responsibility: Execute SQL queries safely against the database.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.database.async_db import get_async_db_context

logger = logging.getLogger(__name__)


class SQLExecutor:
    """
    Executes SQL queries against the database.

    Single Responsibility: Safe execution of validated SQL queries.
    """

    async def execute(self, sql_query: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Execute the SQL query safely against the database.

        Args:
            sql_query: Validated SQL query to execute
            user_id: Optional user ID for logging purposes

        Returns:
            List of result dictionaries

        Raises:
            Exception: If query execution fails
        """
        try:
            # Log the query for monitoring
            logger.info(f"Executing dynamic SQL for user {user_id}: {sql_query[:200]}...")

            # Execute query using the async database context
            async with get_async_db_context() as session:
                result = await session.execute(text(sql_query))
                rows = result.fetchall()

                # Convert to list of dictionaries
                if rows:
                    columns = result.keys()
                    return [dict(zip(columns, row, strict=True)) for row in rows]
                else:
                    return []

        except Exception as e:
            logger.error(f"Error executing SQL query: {e}")
            raise Exception(f"Database query failed: {str(e)}") from e
