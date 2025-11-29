"""
Database Schema Inspector.

Single Responsibility: Inspect and retrieve database table schemas.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.database.async_db import get_async_db_context

logger = logging.getLogger(__name__)


class SchemaInspector:
    """
    Inspects database schemas for SQL generation.

    Single Responsibility: Retrieve and format table schema information.
    """

    # Fallback schemas when database inspection fails
    FALLBACK_SCHEMAS = {
        "orders": {
            "columns": [
                {"name": "id", "type": "int", "nullable": False},
                {"name": "user_id", "type": "varchar", "nullable": False},
                {"name": "product_id", "type": "int", "nullable": True},
                {"name": "quantity", "type": "int", "nullable": False},
                {"name": "total_amount", "type": "decimal", "nullable": False},
                {"name": "status", "type": "varchar", "nullable": False},
                {"name": "created_at", "type": "datetime", "nullable": False},
                {"name": "country", "type": "varchar", "nullable": True},
            ]
        },
        "products": {
            "columns": [
                {"name": "id", "type": "int", "nullable": False},
                {"name": "name", "type": "varchar", "nullable": False},
                {"name": "description", "type": "text", "nullable": True},
                {"name": "price", "type": "decimal", "nullable": False},
                {"name": "category_id", "type": "int", "nullable": True},
                {"name": "brand_id", "type": "int", "nullable": True},
                {"name": "stock", "type": "int", "nullable": False},
                {"name": "created_at", "type": "datetime", "nullable": False},
            ]
        },
        "customers": {
            "columns": [
                {"name": "id", "type": "int", "nullable": False},
                {"name": "phone_number", "type": "varchar", "nullable": False},
                {"name": "name", "type": "varchar", "nullable": True},
                {"name": "email", "type": "varchar", "nullable": True},
                {"name": "country", "type": "varchar", "nullable": True},
                {"name": "created_at", "type": "datetime", "nullable": False},
            ]
        },
    }

    async def get_available_tables(
        self, intent_analysis: Dict[str, Any], table_constraints: Optional[List[str]]
    ) -> List[str]:
        """
        Get list of available tables based on intent and constraints.

        Args:
            intent_analysis: Intent analysis results
            table_constraints: Optional list of allowed tables

        Returns:
            List of table names to query
        """
        # If specific constraints provided, use them
        if table_constraints:
            return table_constraints

        # Otherwise, infer from intent analysis
        target_entities = intent_analysis.get("target_entities", [])
        if target_entities:
            return target_entities

        # Default to common e-commerce tables
        return ["orders", "products", "customers", "categories"]

    async def get_table_schemas(self, table_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get schema information for specified tables.

        Args:
            table_names: List of table names to inspect

        Returns:
            Dictionary mapping table names to their schemas
        """
        schemas = {}

        try:
            async with get_async_db_context() as session:
                for table_name in table_names:
                    # Query information schema for table structure (PostgreSQL compatible)
                    schema_query = f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    AND table_schema = 'public'
                    ORDER BY ordinal_position
                    """

                    result = await session.execute(text(schema_query))
                    columns = result.fetchall()

                    if columns:
                        schemas[table_name] = {
                            "columns": [
                                {
                                    "name": col[0],
                                    "type": col[1],
                                    "nullable": col[2] == "YES",
                                    "default": col[3],
                                }
                                for col in columns
                            ]
                        }

        except Exception as e:
            logger.warning(f"Error getting table schemas: {e}")
            # Provide basic fallback schemas
            schemas = self._get_fallback_schemas(table_names)

        return schemas

    def _get_fallback_schemas(self, table_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """Provide fallback schemas when database inspection fails."""
        return {table: schema for table, schema in self.FALLBACK_SCHEMAS.items() if table in table_names}

    def format_schema_for_prompt(self, schemas: Dict[str, Dict[str, Any]]) -> str:
        """
        Format schema information for AI prompt.

        Args:
            schemas: Dictionary of table schemas

        Returns:
            Formatted string for use in prompts
        """
        formatted_schemas = []

        for table_name, schema in schemas.items():
            columns_info = []
            for col in schema.get("columns", []):
                col_info = f"  {col['name']} ({col['type']})"
                if not col.get("nullable", True):
                    col_info += " NOT NULL"
                columns_info.append(col_info)

            table_info = f"Tabla: {table_name}\n" + "\n".join(columns_info)
            formatted_schemas.append(table_info)

        return "\n\n".join(formatted_schemas)
