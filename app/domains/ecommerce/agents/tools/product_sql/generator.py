"""
Product SQL Generator.

Single Responsibility: Orchestrate SQL generation workflow using composition.
"""

import logging
from datetime import datetime
from typing import Any

from app.integrations.llm import VllmLLM

from .analyzer import QueryComplexityAnalyzer
from .builder import ProductSQLBuilder
from .executor import SQLExecutor
from .schemas import ProductSQLResult
from .validator import SQLValidator

logger = logging.getLogger(__name__)


class ProductSQLGenerator:
    """
    Generador de SQL dinámico especializado para consultas de productos.

    Uses composition:
    - QueryComplexityAnalyzer for query analysis
    - ProductSQLBuilder for SQL generation
    - SQLValidator for security validation
    - SQLExecutor for query execution
    """

    def __init__(self, llm: VllmLLM, postgres=None):
        self.llm = llm
        self.postgres = postgres

        # Compose dependencies
        self._analyzer = QueryComplexityAnalyzer(llm)
        self._builder = ProductSQLBuilder(llm)
        self._validator = SQLValidator()
        self._executor = SQLExecutor()

    async def generate_and_execute(
        self, user_query: str, intent: dict[str, Any], max_results: int = 50
    ) -> ProductSQLResult:
        """
        Genera y ejecuta SQL dinámico para consultas de productos.
        """
        generated_sql = ""
        try:
            start_time = datetime.now()

            # 1. Analizar la complejidad de la consulta
            complexity_analysis = await self._analyzer.analyze(user_query, intent)

            # 2. Generar SQL usando AI
            generated_sql = await self._builder.build(
                user_query, intent, complexity_analysis, max_results
            )

            # 3. Validar y sanitizar el SQL
            validated_sql = self._validator.validate(generated_sql)

            # 4. Ejecutar la consulta
            results = await self._executor.execute(validated_sql)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return ProductSQLResult(
                success=True,
                data=results,
                row_count=len(results),
                generated_sql=validated_sql,
                execution_time_ms=execution_time,
                metadata={
                    "complexity": complexity_analysis,
                    "intent_type": intent.get("intent_type", "unknown"),
                    "tables_used": self._validator.extract_tables(validated_sql),
                },
            )

        except Exception as e:
            logger.error(f"Error in product SQL generation: {e}")
            return ProductSQLResult(
                success=False,
                error_message=str(e),
                generated_sql=generated_sql,
            )

    async def generate_aggregation_sql(
        self,
        user_query: str,
        intent: dict[str, Any],
        aggregation_type: str = "count",
    ) -> ProductSQLResult:
        """
        Genera SQL específico para agregaciones (conteos, sumas, promedios).
        """
        try:
            sql = await self._builder.build_aggregation(
                user_query, intent, aggregation_type
            )
            validated_sql = self._validator.validate(sql)
            results = await self._executor.execute(validated_sql)

            return ProductSQLResult(
                success=True,
                data=results,
                row_count=len(results),
                generated_sql=validated_sql,
                metadata={
                    "query_type": "aggregation",
                    "aggregation_type": aggregation_type,
                },
            )

        except Exception as e:
            logger.error(f"Error in aggregation SQL: {e}")
            return ProductSQLResult(success=False, error_message=str(e))
