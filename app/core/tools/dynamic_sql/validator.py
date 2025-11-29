"""
SQL Validator.

Single Responsibility: Validate and sanitize SQL queries for safety.
"""

import logging
import re

from app.core.tools.dynamic_sql.models import SQLGenerationContext

logger = logging.getLogger(__name__)


class SQLValidator:
    """
    Validates and sanitizes SQL queries.

    Single Responsibility: Ensure SQL queries are safe and properly formatted.
    """

    # Forbidden SQL operations for security
    FORBIDDEN_OPERATIONS = {
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "REPLACE",
        "MERGE",
        "CALL",
        "EXEC",
    }

    # Tables that require user-specific filtering
    USER_SPECIFIC_TABLES = ["orders", "conversations", "messages", "user_preferences"]

    def validate_and_sanitize(self, sql_query: str, context: SQLGenerationContext) -> str:
        """
        Validate and sanitize the generated SQL query.

        Args:
            sql_query: Raw SQL query to validate
            context: Generation context with constraints

        Returns:
            Sanitized SQL query

        Raises:
            Exception: If query contains forbidden operations
        """
        # Remove comments and extra whitespace
        sql_query = re.sub(r"--.*$", "", sql_query, flags=re.MULTILINE)
        sql_query = re.sub(r"/\*.*?\*/", "", sql_query, flags=re.DOTALL)
        sql_query = sql_query.strip()

        # Check for forbidden operations
        sql_upper = sql_query.upper()
        for forbidden in self.FORBIDDEN_OPERATIONS:
            if f" {forbidden} " in f" {sql_upper} ":
                raise Exception(f"Forbidden SQL operation detected: {forbidden}")

        # Ensure it starts with SELECT
        if not sql_upper.startswith("SELECT"):
            raise Exception("Only SELECT queries are allowed")

        # Add LIMIT if not present
        if "LIMIT" not in sql_upper:
            sql_query = f"{sql_query.rstrip(';')} LIMIT {context.max_results}"

        # Add user filtering if user_id provided and query involves user-specific tables
        if context.user_id and self._requires_user_filtering(sql_query):
            sql_query = self._add_user_filtering(sql_query, context.user_id)

        return sql_query

    def _requires_user_filtering(self, sql_query: str) -> bool:
        """
        Check if query requires user-specific filtering.

        Args:
            sql_query: SQL query to check

        Returns:
            True if user filtering should be applied
        """
        sql_lower = sql_query.lower()
        return any(table in sql_lower for table in self.USER_SPECIFIC_TABLES)

    def _add_user_filtering(self, sql_query: str, user_id: str) -> str:
        """
        Add user filtering to SQL query when needed.

        Args:
            sql_query: SQL query to modify
            user_id: User ID to filter by

        Returns:
            SQL query with user filtering added
        """
        if "WHERE" in sql_query.upper():
            # Add to existing WHERE clause
            user_filter = f" AND user_id = '{user_id}'"
            where_pos = sql_query.upper().find("WHERE") + 5
            return sql_query[:where_pos] + user_filter + sql_query[where_pos:]
        else:
            # Add new WHERE clause
            return f"{sql_query} WHERE user_id = '{user_id}'"
