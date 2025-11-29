"""
SQL Executor.

Single Responsibility: Execute validated SQL queries and return results.
"""

import logging
from typing import Any

from sqlalchemy import text

from app.database.async_db import get_async_db_context

logger = logging.getLogger(__name__)


class SQLExecutor:
    """Executes validated SQL queries."""

    async def execute(self, sql: str) -> list[dict[str, Any]]:
        """
        Ejecuta el SQL validado y retorna resultados.
        """
        try:
            async with get_async_db_context() as db:
                result = await db.execute(text(sql))
                rows = result.fetchall()

                if rows:
                    columns = result.keys()
                    results = []
                    for row in rows:
                        row_dict = {}
                        for i, column in enumerate(columns):
                            value = row[i]
                            # Convertir tipos especiales
                            if hasattr(value, "isoformat"):  # datetime
                                value = value.isoformat()
                            elif hasattr(value, "__float__"):  # Decimal
                                value = float(value)
                            row_dict[column] = value
                        results.append(row_dict)

                    return results
                else:
                    return []

        except Exception as e:
            logger.error(f"Error executing product SQL: {e}")
            raise ValueError(f"Error en ejecución SQL: {str(e)}") from e
