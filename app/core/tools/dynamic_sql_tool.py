"""
Dynamic SQL Generation and Execution Tool.

This tool provides AI-powered SQL generation and execution capabilities
for LangGraph agents to interact with data dynamically.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.integrations.llm import OllamaLLM
from app.database.async_db import get_async_db_context

logger = logging.getLogger(__name__)


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


class DynamicSQLTool:
    """
    Advanced SQL generation and execution tool using AI.

    This tool can:
    1. Understand user intent from natural language
    2. Generate safe, optimized SQL queries
    3. Execute queries against the database
    4. Convert results to embedding-ready context
    5. Provide rich context for agent responses
    """

    def __init__(self, ollama: OllamaLLM | None = None):
        self.ollama = ollama or OllamaLLM()

        # Safety constraints
        self.forbidden_operations = {
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

        # Table mappings and common schema patterns
        self.table_mappings = {
            "orders": ["orders", "pedidos", "compras"],
            "products": ["products", "productos", "items"],
            "customers": ["customers", "usuarios", "users", "clientes"],
            "categories": ["categories", "categorias"],
            "brands": ["brands", "marcas"],
            "inventory": ["inventory", "stock", "inventario"],
            "conversations": ["conversations", "conversaciones", "messages"],
            "payments": ["payments", "pagos", "transactions"],
        }

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
        try:
            start_time = datetime.now()

            # 1. Analyze intent and extract query components
            intent_analysis = await self._analyze_query_intent(user_query)

            # 2. Get available tables and schemas
            context = await self._build_sql_context(
                user_query, intent_analysis, table_constraints, user_id, max_results
            )

            # 3. Generate SQL query using AI
            generated_sql = await self._generate_sql_query(context)

            # 4. Validate and sanitize the SQL
            validated_sql = await self._validate_and_sanitize_sql(generated_sql, context)

            # 5. Execute the query
            results = await self._execute_sql_query(validated_sql, user_id)

            # 6. Generate embedding-ready context
            embedding_context = await self._generate_embedding_context(user_query, results, intent_analysis)

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
                success=False, error_message=str(e), generated_sql=locals().get("generated_sql", "")
            )

    async def _analyze_query_intent(self, user_query: str) -> Dict[str, Any]:
        """Analyze user query to understand intent and extract components."""

        intent_prompt = f"""# ANÁLISIS DE INTENCIÓN PARA CONSULTA SQL

CONSULTA DEL USUARIO: "{user_query}"

Analiza la consulta y extrae los siguientes componentes en formato JSON:

{{
  "intent_type": "search|count|aggregate|list|comparison|trend",
  "target_entities": ["tabla1", "tabla2"],
  "filters": {{
    "time_range": "last_week|last_month|yesterday|today|specific_date",
    "locations": ["Brasil", "Argentina"],
    "status": ["completed", "pending"],
    "amounts": {{"min": 100, "max": 1000}},
    "user_specific": true
  }},
  "aggregations": ["COUNT", "SUM", "AVG", "MAX", "MIN"],
  "time_columns": ["created_at", "order_date", "updated_at"],
  "grouping": ["country", "category", "month"],
  "sorting": {{"column": "created_at", "direction": "DESC"}},
  "limit": 100,
  "keywords": ["órdenes", "Brasil", "semana pasada"],
  "confidence": 0.9
}}

Responde SOLO el JSON válido:"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un experto en análisis de consultas SQL. \
                    Extrae información estructurada de consultas en lenguaje natural.",
                user_prompt=intent_prompt,
                temperature=0.1,
            )

            # Clean and parse JSON response
            clean_response = self._clean_json_response(response)
            intent_data = json.loads(clean_response)

            # Validate and provide defaults
            return self._validate_intent_analysis(intent_data)

        except Exception as e:
            logger.warning(f"Error analyzing intent: {e}. Using fallback.")
            return self._get_fallback_intent_analysis(user_query)

    async def _build_sql_context(
        self,
        user_query: str,
        intent_analysis: Dict[str, Any],
        table_constraints: Optional[List[str]],
        user_id: Optional[str],
        max_results: int,
    ) -> SQLGenerationContext:
        """Build comprehensive context for SQL generation."""

        # Get available tables
        available_tables = await self._get_available_tables(intent_analysis, table_constraints)

        # Get table schemas
        table_schemas = await self._get_table_schemas(available_tables)

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

    async def _generate_sql_query(self, context: SQLGenerationContext) -> str:
        """Generate SQL query using AI based on context."""

        # Build comprehensive prompt with schemas and examples
        schema_info = self._format_schema_for_prompt(context.table_schemas)

        sql_prompt = f"""# GENERACIÓN DE CONSULTA SQL DINÁMICA

## CONSULTA DEL USUARIO:
"{context.user_query}"

## ESQUEMAS DE TABLAS DISPONIBLES:
{schema_info}

## RESTRICCIONES DE SEGURIDAD:
{chr(10).join(f"- {constraint}" for constraint in context.safety_constraints)}

## INSTRUCCIONES:
1. Genera UNA consulta SQL válida que responda exactamente a la pregunta del usuario
2. USA SOLO operaciones SELECT
3. Incluye las claúsulas WHERE apropiadas para filtros específicos del usuario
4. Usa JOINs cuando sea necesario para relacionar tablas
5. Incluye LIMIT {context.max_results} para evitar resultados masivos
6. Maneja fechas y rangos de tiempo correctamente
7. Usa nombres de columnas exactos del esquema

## EJEMPLOS DE CONSULTAS VÁLIDAS:

Pregunta: "¿Cuántos pedidos se hicieron la semana pasada?"
SQL: SELECT COUNT(*) as total_orders FROM orders WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY);

Pregunta: "Muestra mis últimos 5 pedidos"
SQL: SELECT o.*, p.name as product_name FROM orders o LEFT JOIN products p ON 
    o.product_id = p.id ORDER BY o.created_at DESC LIMIT 5;

Pregunta: "¿Cuántos productos tenemos en total?"
SQL: SELECT COUNT(*) as total_products FROM products;

Pregunta: "¿Cuáles son los productos más vendidos en Brasil?"
SQL: SELECT p.name, COUNT(o.id) as sales_count FROM products p JOIN orders o ON p.id = o.product_id 
    WHERE o.country = 'Brasil' GROUP BY p.id, p.name ORDER BY sales_count DESC LIMIT 10;

## RESPUESTA:
Genera SOLO la consulta SQL válida. NO incluyas explicaciones, comentarios o notas.
FORMATO: SELECT ... FROM ... WHERE ... LIMIT N;

SQL:"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un experto en SQL que genera consultas precisas y seguras \
                    basadas en esquemas de base de datos.",
                user_prompt=sql_prompt,
                temperature=0.1,
            )

            # Extract SQL from response
            sql_query = self._extract_sql_from_response(response)
            return sql_query

        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            raise Exception(f"Failed to generate SQL query: {str(e)}") from e

    async def _validate_and_sanitize_sql(self, sql_query: str, context: SQLGenerationContext) -> str:
        """Validate and sanitize the generated SQL query."""

        # Remove comments and extra whitespace
        sql_query = re.sub(r"--.*$", "", sql_query, flags=re.MULTILINE)
        sql_query = re.sub(r"/\*.*?\*/", "", sql_query, flags=re.DOTALL)
        sql_query = sql_query.strip()

        # Check for forbidden operations
        sql_upper = sql_query.upper()
        for forbidden in self.forbidden_operations:
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

    async def _execute_sql_query(self, sql_query: str, user_id: Optional[str]) -> List[Dict[str, Any]]:
        """Execute the SQL query safely against the database."""

        try:
            # Log the query for monitoring
            logger.info(f"Executing dynamic SQL for user {user_id}: {sql_query[:200]}...")

            # Execute query using the async database context
            async with get_async_db_context() as session:
                # Import text from sqlalchemy for raw SQL execution
                from sqlalchemy import text

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

    async def _generate_embedding_context(
        self, user_query: str, results: List[Dict[str, Any]], _: Dict[str, Any]
    ) -> str:
        """Generate embedding-ready context from query results."""

        if not results:
            return f"No se encontraron resultados para la consulta: {user_query}"

        # Summarize results for embedding
        context_prompt = f"""# CONTEXTO DE DATOS PARA AGENTE AI

CONSULTA ORIGINAL: "{user_query}"

RESULTADOS ENCONTRADOS: {len(results)} registros

DATOS RELEVANTES:
{json.dumps(results[:10], indent=2, default=str)}

RESUMEN EJECUTIVO:
Genera un resumen conciso y estructurado de estos datos que permita a un agente AI responder de manera 
    informativa y útil. Incluye:
- Números clave y estadísticas
- Patrones o tendencias importantes
- Respuesta directa a la pregunta original
- Contexto adicional relevante

Respuesta en español, máximo 300 palabras:"""

        try:
            context_summary = await self.ollama.generate_response(
                system_prompt="Eres un analista de datos experto que resume información de manera \
                    clara y útil para agentes AI.",
                user_prompt=context_prompt,
                temperature=0.3,
            )

            return context_summary

        except Exception as e:
            logger.warning(f"Error generating embedding context: {e}")
            # Fallback to simple formatting
            return self._generate_fallback_context(user_query, results)

    # Helper methods
    def _clean_json_response(self, response: str) -> str:
        """Clean AI response to extract valid JSON."""
        # Remove markdown code blocks
        response = re.sub(r"```json\s*", "", response)
        response = re.sub(r"```\s*", "", response)

        # Find JSON object
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            return json_match.group(0)

        return response.strip()

    def _validate_intent_analysis(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and provide defaults for intent analysis."""
        defaults = {
            "intent_type": "search",
            "target_entities": [],
            "filters": {},
            "aggregations": [],
            "time_columns": ["created_at"],
            "grouping": [],
            "sorting": {"column": "created_at", "direction": "DESC"},
            "limit": 100,
            "keywords": [],
            "confidence": 0.5,
        }

        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in intent_data:
                intent_data[key] = default_value

        return intent_data

    def _get_fallback_intent_analysis(self, user_query: str) -> Dict[str, Any]:
        """Provide fallback intent analysis when AI fails."""
        # Simple keyword-based analysis
        keywords = user_query.lower().split()

        target_entities = []
        for table, aliases in self.table_mappings.items():
            if any(alias in keywords for alias in aliases):
                target_entities.append(table)

        return {
            "intent_type": "search",
            "target_entities": target_entities or ["orders"],
            "filters": {"user_specific": True},
            "aggregations": [],
            "time_columns": ["created_at"],
            "grouping": [],
            "sorting": {"column": "created_at", "direction": "DESC"},
            "limit": 100,
            "keywords": keywords,
            "confidence": 0.3,
        }

    async def _get_available_tables(
        self, intent_analysis: Dict[str, Any], table_constraints: Optional[List[str]]
    ) -> List[str]:
        """Get list of available tables based on intent and constraints."""

        # If specific constraints provided, use them
        if table_constraints:
            return table_constraints

        # Otherwise, infer from intent analysis
        target_entities = intent_analysis.get("target_entities", [])
        if target_entities:
            return target_entities

        # Default to common e-commerce tables
        return ["orders", "products", "customers", "categories"]

    async def _get_table_schemas(self, table_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get schema information for specified tables."""
        schemas = {}

        try:
            async with get_async_db_context() as session:
                from sqlalchemy import text

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
                                {"name": col[0], "type": col[1], "nullable": col[2] == "YES", "default": col[3]}
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
        fallback_schemas = {
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

        return {table: schema for table, schema in fallback_schemas.items() if table in table_names}

    def _format_schema_for_prompt(self, schemas: Dict[str, Dict[str, Any]]) -> str:
        """Format schema information for AI prompt."""
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
                keyword in line.upper() for keyword in ["SELECT", "FROM", "WHERE", "GROUP", "ORDER", "LIMIT", "JOIN"]
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

    def _requires_user_filtering(self, sql_query: str) -> bool:
        """Check if query requires user-specific filtering."""
        user_tables = ["orders", "conversations", "messages", "user_preferences"]
        sql_lower = sql_query.lower()

        return any(table in sql_lower for table in user_tables)

    def _add_user_filtering(self, sql_query: str, user_id: str) -> str:
        """Add user filtering to SQL query when needed."""
        # This is a simplified implementation
        # In production, you'd want more sophisticated filtering logic

        if "WHERE" in sql_query.upper():
            # Add to existing WHERE clause
            user_filter = f" AND user_id = '{user_id}'"
            where_pos = sql_query.upper().find("WHERE") + 5
            return sql_query[:where_pos] + user_filter + sql_query[where_pos:]
        else:
            # Add new WHERE clause
            return f"{sql_query} WHERE user_id = '{user_id}'"

    def _generate_fallback_context(self, user_query: str, results: List[Dict[str, Any]]) -> str:
        """Generate simple fallback context when AI summary fails."""
        if not results:
            return f"No se encontraron datos para: {user_query}"

        summary = f"Encontrados {len(results)} registros para la consulta: {user_query}\\n\\n"

        # Add first few results
        for i, record in enumerate(results[:3]):
            summary += f"Registro {i + 1}: {json.dumps(record, default=str)}\\n"

        if len(results) > 3:
            summary += f"... y {len(results) - 3} registros más."

        return summary
