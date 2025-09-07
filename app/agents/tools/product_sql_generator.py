"""
Product SQL Generator - Generador de SQL dinámico especializado en productos.

Esta herramienta genera consultas SQL inteligentes para búsquedas complejas de productos
usando AI para interpretar intenciones y crear queries optimizadas.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy import text

from app.database.async_db import get_async_db_context

from ..integrations.ollama_integration import OllamaIntegration

logger = logging.getLogger(__name__)


class ProductSQLResult(BaseModel):
    """Resultado de la ejecución de SQL de productos."""

    success: bool
    data: List[Dict[str, Any]] = []
    row_count: int = 0
    generated_sql: str = ""
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ProductSQLGenerator:
    """
    Generador de SQL dinámico especializado para consultas de productos.

    Capacidades:
    - Generación de SQL complejo usando AI
    - Validación de seguridad específica para productos
    - Optimización de queries para el dominio de e-commerce
    - Manejo de relaciones entre productos, categorías y marcas
    """

    def __init__(self, ollama: OllamaIntegration, postgres=None):
        self.ollama = ollama
        self.postgres = postgres

        # Configuración de seguridad
        self.allowed_tables = {
            "products",
            "categories",
            "brands",
            "product_images",
            "product_attributes",
            "product_reviews",
            "inventory",
        }

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
            "GRANT",
            "REVOKE",
        }

        # Schema de productos para el contexto de AI
        self.product_schema = {
            "products": {
                "id": "UUID PRIMARY KEY",
                "name": "VARCHAR - nombre del producto",
                "description": "TEXT - descripción detallada",
                "price": "DECIMAL - precio actual",
                "stock": "INTEGER - cantidad en inventario",
                "model": "VARCHAR - modelo/código del producto",
                "category_id": "UUID - referencia a categories",
                "brand_id": "UUID - referencia a brands",
                "active": "BOOLEAN - producto activo",
                "created_at": "TIMESTAMP",
                "updated_at": "TIMESTAMP",
            },
            "categories": {
                "id": "UUID PRIMARY KEY",
                "name": "VARCHAR - nombre interno",
                "display_name": "VARCHAR - nombre para mostrar",
                "description": "TEXT - descripción de la categoría",
                "parent_id": "UUID - categoría padre (para jerarquía)",
            },
            "brands": {
                "id": "UUID PRIMARY KEY",
                "name": "VARCHAR - nombre de la marca",
                "description": "TEXT - descripción de la marca",
            },
        }

    async def generate_and_execute(
        self, user_query: str, intent: Dict[str, Any], max_results: int = 50
    ) -> ProductSQLResult:
        """
        Genera y ejecuta SQL dinámico para consultas de productos.
        """
        try:
            start_time = datetime.now()

            # 1. Analizar la complejidad de la consulta
            complexity_analysis = await self._analyze_query_complexity(user_query, intent)

            # 2. Generar SQL usando AI
            generated_sql = await self._generate_product_sql(user_query, intent, complexity_analysis, max_results)

            # 3. Validar y sanitizar el SQL
            validated_sql = await self._validate_product_sql(generated_sql)

            # 4. Ejecutar la consulta
            results = await self._execute_product_sql(validated_sql)

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
                    "tables_used": self._extract_tables_from_sql(validated_sql),
                },
            )

        except Exception as e:
            logger.error(f"Error in product SQL generation: {e}")
            return ProductSQLResult(
                success=False, error_message=str(e), generated_sql=locals().get("generated_sql", "")
            )

    async def _analyze_query_complexity(self, user_query: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analiza la complejidad de la consulta para optimizar la generación de SQL.
        """

        complexity_prompt = f"""# ANÁLISIS DE COMPLEJIDAD DE CONSULTA

CONSULTA: "{user_query}"

INTENCIÓN DETECTADA:
{json.dumps(intent, indent=2)}

Analiza la complejidad y responde en JSON:

{{
  "complexity_level": "simple|medium|complex|very_complex",
  "requires_joins": bool,
  "requires_aggregation": bool,
  "requires_subqueries": bool,
  "requires_full_text_search": bool,
  "tables_needed": ["products", "categories", "brands"],
  "estimated_query_type": "simple_select|filtered_search|aggregated_report|complex_analysis",
  "optimization_hints": ["índice_sugerido", "join_order"]
}}

CRITERIOS:
- simple: búsqueda básica por nombre/categoría
- medium: filtros múltiples, joins básicos
- complex: agregaciones, subqueries, full-text search
- very_complex: múltiples joins, queries anidadas, análisis estadístico"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un experto en optimización de consultas SQL para e-commerce.",
                user_prompt=complexity_prompt,
                temperature=0.2,
            )

            return json.loads(response)

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Could not parse complexity analysis: {e}")
            return self._create_fallback_complexity_analysis(user_query, intent)

    def _create_fallback_complexity_analysis(self, user_query: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea análisis de complejidad básico como fallback.
        """
        query_lower = user_query.lower()

        # Detectar patrones básicos
        requires_joins = any(word in query_lower for word in ["marca", "categoría", "brand", "category"])
        requires_aggregation = any(word in query_lower for word in ["total", "promedio", "suma", "count", "cuántos"])

        if requires_aggregation:
            complexity = "complex"
        elif requires_joins and len(intent.get("filters", {})) > 2:
            complexity = "medium"
        else:
            complexity = "simple"

        return {
            "complexity_level": complexity,
            "requires_joins": requires_joins,
            "requires_aggregation": requires_aggregation,
            "requires_subqueries": False,
            "requires_full_text_search": True,
            "tables_needed": ["products", "categories", "brands"],
            "estimated_query_type": "filtered_search",
            "optimization_hints": ["index_on_name", "join_categories_brands"],
        }

    async def _generate_product_sql(
        self, user_query: str, intent: Dict[str, Any], complexity: Dict[str, Any], max_results: int
    ) -> str:
        """
        Genera SQL usando AI con contexto específico de productos.
        """

        # Construir contexto del schema
        schema_context = self._build_schema_context()

        # Construir contexto de la intención
        intent_context = self._build_intent_context(intent)

        sql_prompt = f"""# GENERACIÓN DE SQL PARA PRODUCTOS

## CONSULTA DEL USUARIO:
"{user_query}"

## CONTEXTO DE INTENCIÓN:
{intent_context}

## ANÁLISIS DE COMPLEJIDAD:
{json.dumps(complexity, indent=2)}

## SCHEMA DE BASE DE DATOS:
{schema_context}

## REGLAS IMPORTANTES:
1. SOLO consultas SELECT permitidas
2. Usar JOINS apropiados para relaciones
3. Incluir filtros de productos activos (active = true)
4. Optimizar para performance
5. Limitar resultados a {max_results}
6. Usar ILIKE para búsquedas de texto case-insensitive
7. Manejar NULLs apropiadamente

## EJEMPLOS DE CONSULTAS TÍPICAS:

Búsqueda simple:
```sql
SELECT p.*, c.display_name as category_name, b.name as brand_name
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN brands b ON p.brand_id = b.id
WHERE p.active = true AND p.name ILIKE '%keyword%'
ORDER BY p.created_at DESC
LIMIT {max_results};
```

Búsqueda con filtros:
```sql
SELECT p.*, c.display_name as category_name, b.name as brand_name
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN brands b ON p.brand_id = b.id
WHERE p.active = true 
  AND (p.name ILIKE '%keyword%' OR p.description ILIKE '%keyword%')
  AND c.name = 'categoria'
  AND p.price BETWEEN min_price AND max_price
  AND p.stock > 0
ORDER BY p.price ASC
LIMIT {max_results};
```

## INSTRUCCIONES:
Genera UNA consulta SQL optimizada que responda exactamente a la consulta del usuario.
Responde SOLO con el SQL, sin explicaciones.
"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un experto desarrollador SQL especializado en e-commerce y bases de \
                    datos de productos.",
                user_prompt=sql_prompt,
                temperature=0.1,  # Baja temperatura para consistencia
            )

            # Limpiar la respuesta
            sql = self._clean_sql_response(response)

            return sql

        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return self._generate_fallback_sql(user_query, intent, max_results)

    def _build_schema_context(self) -> str:
        """
        Construye contexto del schema para la AI.
        """
        schema_lines = []
        for table, columns in self.product_schema.items():
            schema_lines.append(f"\n{table.upper()}:")
            for column, description in columns.items():
                schema_lines.append(f"  - {column}: {description}")

        return "\n".join(schema_lines)

    def _build_intent_context(self, intent: Dict[str, Any]) -> str:
        """
        Construye contexto de la intención para la AI.
        """
        context_lines = []

        # Parámetros de búsqueda
        search_params = intent.get("search_params", {})
        if search_params:
            context_lines.append("PARÁMETROS DE BÚSQUEDA:")
            for key, value in search_params.items():
                if value:
                    context_lines.append(f"  - {key}: {value}")

        # Filtros
        filters = intent.get("filters", {})
        if filters:
            context_lines.append("\nFILTROS:")
            for key, value in filters.items():
                if value:
                    context_lines.append(f"  - {key}: {value}")

        # Tipo de intención
        intent_type = intent.get("intent_type", "search_general")
        context_lines.append(f"\nTIPO DE INTENCIÓN: {intent_type}")

        return "\n".join(context_lines) if context_lines else "Sin contexto específico"

    def _clean_sql_response(self, response: str) -> str:
        """
        Limpia la respuesta SQL de la AI.
        """
        # Remover markdown si existe
        response = re.sub(r"```sql\n?", "", response)
        response = re.sub(r"```\n?", "", response)

        # Remover comentarios excesivos
        lines = response.split("\n")
        sql_lines = []

        for line in lines:
            line = line.strip()
            # Mantener líneas SQL válidas
            if line and not line.startswith("#") and not line.startswith("--"):
                sql_lines.append(line)

        sql = " ".join(sql_lines)

        # Asegurar que termina con ;
        if not sql.strip().endswith(";"):
            sql += ";"

        return sql

    def _generate_fallback_sql(self, user_query: str, intent: Dict[str, Any], max_results: int) -> str:
        """
        Genera SQL básico como fallback.
        """
        # Extraer palabras clave básicas
        search_params = intent.get("search_params", {})
        keywords = search_params.get("keywords", [])

        if not keywords:
            # Fallback a palabras de la query original
            keywords = [word for word in user_query.split() if len(word) > 2]

        # Construir SQL básico
        base_sql = """
        SELECT p.*, c.display_name as category_name, b.name as brand_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN brands b ON p.brand_id = b.id
        WHERE p.active = true
        """

        conditions = []

        # Agregar condiciones de búsqueda
        if keywords:
            keyword_conditions = []
            for keyword in keywords[:3]:  # Máximo 3 keywords
                keyword_conditions.append(f"p.name ILIKE '%{keyword}%'")
                keyword_conditions.append(f"p.description ILIKE '%{keyword}%'")

            if keyword_conditions:
                conditions.append(f"({' OR '.join(keyword_conditions)})")

        # Agregar filtros específicos
        filters = intent.get("filters", {})

        # Filtro de precio
        price_range = filters.get("price_range", {})
        if price_range.get("min"):
            conditions.append(f"p.price >= {price_range['min']}")
        if price_range.get("max"):
            conditions.append(f"p.price <= {price_range['max']}")

        # Filtro de disponibilidad
        if filters.get("availability_required", True):
            conditions.append("p.stock > 0")

        # Combinar condiciones
        if conditions:
            base_sql += " AND " + " AND ".join(conditions)

        # Agregar ordenamiento y límite
        base_sql += f" ORDER BY p.created_at DESC LIMIT {max_results};"

        return base_sql

    async def _validate_product_sql(self, sql: str) -> str:
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
        used_tables = self._extract_tables_from_sql(sql)
        for table in used_tables:
            if table.lower() not in self.allowed_tables:
                raise ValueError(f"Tabla no permitida: {table}")

        # Verificar límites básicos
        if "LIMIT" not in sql_upper:
            sql = sql.rstrip(";") + " LIMIT 100;"

        return sql

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
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

    async def _execute_product_sql(self, sql: str) -> List[Dict[str, Any]]:
        """
        Ejecuta el SQL validado y retorna resultados.
        """
        try:
            async with get_async_db_context() as db:
                # Ejecutar la consulta
                result = await db.execute(text(sql))
                rows = result.fetchall()

                # Convertir a diccionarios
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

    async def generate_aggregation_sql(
        self, user_query: str, intent: Dict[str, Any], aggregation_type: str = "count"
    ) -> ProductSQLResult:
        """
        Genera SQL específico para agregaciones (conteos, sumas, promedios).
        """

        aggregation_prompt = f"""# GENERACIÓN DE SQL DE AGREGACIÓN

CONSULTA: "{user_query}"
TIPO DE AGREGACIÓN: {aggregation_type}

INTENCIÓN:
{json.dumps(intent, indent=2)}

Genera una consulta SQL que calcule agregaciones de productos.

EJEMPLOS:
- COUNT: SELECT COUNT(*) as total_products FROM products WHERE...
- AVG: SELECT AVG(price) as average_price FROM products WHERE...
- SUM: SELECT SUM(stock) as total_stock FROM products WHERE...
- GROUP BY: SELECT category_name, COUNT(*) FROM products p JOIN categories c...

Incluye JOINs necesarios y responde SOLO con el SQL:"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un experto en SQL de agregación para e-commerce.",
                user_prompt=aggregation_prompt,
                temperature=0.1,
            )

            sql = self._clean_sql_response(response)
            validated_sql = await self._validate_product_sql(sql)
            results = await self._execute_product_sql(validated_sql)

            return ProductSQLResult(
                success=True,
                data=results,
                row_count=len(results),
                generated_sql=validated_sql,
                metadata={"query_type": "aggregation", "aggregation_type": aggregation_type},
            )

        except Exception as e:
            logger.error(f"Error in aggregation SQL: {e}")
            return ProductSQLResult(success=False, error_message=str(e))
