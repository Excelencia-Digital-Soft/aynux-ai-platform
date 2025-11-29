"""
SQL Validator.

Single Responsibility: Validate and sanitize generated SQL for security.
"""

import logging
import re

from .schemas import ALLOWED_TABLES, FORBIDDEN_OPERATIONS

logger = logging.getLogger(__name__)


class SQLValidator:
    """Validates and sanitizes SQL queries for security."""

    def __init__(
        self,
        allowed_tables: set[str] | None = None,
        forbidden_operations: set[str] | None = None,
    ):
        self.allowed_tables = allowed_tables or ALLOWED_TABLES
        self.forbidden_operations = forbidden_operations or FORBIDDEN_OPERATIONS

    def validate(self, sql: str) -> str:
        """
        Valida y sanitiza el SQL generado.
        """
        if not sql or not sql.strip():
            raise ValueError("SQL vacío generado")

        sql_upper = sql.upper()

        # Verificar operaciones prohibidas
        for forbidden_op in self.forbidden_operations:
            if forbidden_op in sql_upper:
                raise ValueError(f"Operación prohibida detectada: {forbidden_op}")

        # Verificar que es una consulta SELECT
        if not sql_upper.strip().startswith("SELECT"):
            raise ValueError("Solo consultas SELECT están permitidas")

        # Verificar tablas permitidas
        used_tables = self.extract_tables(sql)
        for table in used_tables:
            if table.lower() not in self.allowed_tables:
                raise ValueError(f"Tabla no permitida: {table}")

        # Verificar límites básicos
        if "LIMIT" not in sql_upper:
            sql = sql.rstrip(";") + " LIMIT 100;"

        return sql

    def extract_tables(self, sql: str) -> list[str]:
        """
        Extrae nombres de tablas del SQL.
        """
        tables = []
        sql_upper = sql.upper()

        # Buscar patrones FROM y JOIN
        patterns = [
            r"FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            r"JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            r"INNER\s+JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            r"LEFT\s+JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            r"RIGHT\s+JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, sql_upper)
            tables.extend(matches)

        return list(set(tables))  # Remover duplicados
