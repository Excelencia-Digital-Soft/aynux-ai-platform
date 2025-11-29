"""
SQL Query Generator.

Single Responsibility: Generate SQL queries from context using AI.
"""

import logging
import re
from typing import Any, Dict

from app.core.tools.dynamic_sql.models import SQLGenerationContext
from app.core.tools.dynamic_sql.schema_inspector import SchemaInspector
from app.integrations.llm import OllamaLLM

logger = logging.getLogger(__name__)


class SQLQueryGenerator:
    """
    Generates SQL queries using AI.

    Single Responsibility: Transform natural language queries into SQL.
    """

    def __init__(self, ollama: OllamaLLM | None = None):
        """
        Initialize SQL query generator.

        Args:
            ollama: OllamaLLM instance for AI-powered generation
        """
        self.ollama = ollama or OllamaLLM()
        self._schema_inspector = SchemaInspector()

    async def generate(self, context: SQLGenerationContext) -> str:
        """
        Generate SQL query using AI based on context.

        Args:
            context: SQL generation context with query, schemas, constraints

        Returns:
            Generated SQL query string

        Raises:
            Exception: If generation fails
        """
        # Build comprehensive prompt with schemas and examples
        schema_info = self._schema_inspector.format_schema_for_prompt(context.table_schemas)

        sql_prompt = f"""# GENERACION DE CONSULTA SQL DINAMICA

## CONSULTA DEL USUARIO:
"{context.user_query}"

## ESQUEMAS DE TABLAS DISPONIBLES:
{schema_info}

## RESTRICCIONES DE SEGURIDAD:
{chr(10).join(f"- {constraint}" for constraint in context.safety_constraints)}

## INSTRUCCIONES:
1. Genera UNA consulta SQL valida que responda exactamente a la pregunta del usuario
2. USA SOLO operaciones SELECT
3. Incluye las clausulas WHERE apropiadas para filtros especificos del usuario
4. Usa JOINs cuando sea necesario para relacionar tablas
5. Incluye LIMIT {context.max_results} para evitar resultados masivos
6. Maneja fechas y rangos de tiempo correctamente
7. Usa nombres de columnas exactos del esquema

## EJEMPLOS DE CONSULTAS VALIDAS:

Pregunta: "Cuantos pedidos se hicieron la semana pasada?"
SQL: SELECT COUNT(*) as total_orders FROM orders WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY);

Pregunta: "Muestra mis ultimos 5 pedidos"
SQL: SELECT o.*, p.name as product_name FROM orders o
    LEFT JOIN products p ON o.product_id = p.id ORDER BY o.created_at DESC LIMIT 5;

Pregunta: "Cuantos productos tenemos en total?"
SQL: SELECT COUNT(*) as total_products FROM products;

Pregunta: "Cuales son los productos mas vendidos en Brasil?"
SQL: SELECT p.name, COUNT(o.id) as sales_count FROM products p
    JOIN orders o ON p.id = o.product_id WHERE o.country = 'Brasil'
    GROUP BY p.id, p.name ORDER BY sales_count DESC LIMIT 10;

## RESPUESTA:
Genera SOLO la consulta SQL valida. NO incluyas explicaciones, comentarios o notas.
FORMATO: SELECT ... FROM ... WHERE ... LIMIT N;

SQL:"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un experto en SQL que genera consultas precisas y seguras "
                "basadas en esquemas de base de datos.",
                user_prompt=sql_prompt,
                temperature=0.1,
            )

            # Extract SQL from response
            sql_query = self._extract_sql_from_response(response)
            return sql_query

        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            raise Exception(f"Failed to generate SQL query: {str(e)}") from e

    async def build_context(
        self,
        user_query: str,
        intent_analysis: Dict[str, Any],
        table_constraints: list[str] | None,
        user_id: str | None,
        max_results: int,
    ) -> SQLGenerationContext:
        """
        Build comprehensive context for SQL generation.

        Args:
            user_query: Original user query
            intent_analysis: Results from intent analysis
            table_constraints: Optional table restrictions
            user_id: Optional user ID for filtering
            max_results: Maximum results to return

        Returns:
            SQLGenerationContext with all necessary data
        """
        # Get available tables
        available_tables = await self._schema_inspector.get_available_tables(intent_analysis, table_constraints)

        # Get table schemas
        table_schemas = await self._schema_inspector.get_table_schemas(available_tables)

        # Build safety constraints
        safety_constraints = [
            "ONLY SELECT operations allowed",
            f"LIMIT results to maximum {max_results} rows",
            "Use proper WHERE clauses for user data isolation",
            "Include proper JOIN conditions",
            "Use appropriate indexes for performance",
        ]

        if user_id:
            safety_constraints.append(f"Filter results for user_id = '{user_id}' when applicable")

        return SQLGenerationContext(
            user_query=user_query,
            available_tables=available_tables,
            table_schemas=table_schemas,
            user_id=user_id,
            max_results=max_results,
            safety_constraints=safety_constraints,
        )

    def _extract_sql_from_response(self, response: str) -> str:
        """Extract SQL query from AI response."""
        # Remove markdown formatting
        response = re.sub(r"```sql\s*", "", response)
        response = re.sub(r"```\s*", "", response)

        # Remove any text after SQL statement ends
        lines = response.split("\n")
        sql_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Stop at comments or explanatory text
            if line.startswith("--") or line.startswith("Nota:") or line.startswith("#"):
                break
            # Include SQL lines
            if any(
                keyword in line.upper()
                for keyword in ["SELECT", "FROM", "WHERE", "GROUP", "ORDER", "LIMIT", "JOIN"]
            ):
                sql_lines.append(line)
            elif sql_lines:  # Continue collecting if we've started
                sql_lines.append(line)

        sql_query = " ".join(sql_lines).strip()

        # Find SQL statement with better pattern
        sql_pattern = r"(SELECT\s+.*?)(?:;|\s*$)"
        match = re.search(sql_pattern, sql_query, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        # If no match, return cleaned response
        return sql_query.strip().rstrip(";")
