"""
Product SQL Builder.

Single Responsibility: Build SQL queries using AI and fallback patterns.
"""

import json
import logging
import re
from typing import Any

from app.integrations.llm import OllamaLLM

from .schemas import PRODUCT_SCHEMA

logger = logging.getLogger(__name__)


class ProductSQLBuilder:
    """Builds SQL queries for product searches."""

    def __init__(self, ollama: OllamaLLM):
        self.ollama = ollama
        self.product_schema = PRODUCT_SCHEMA

    async def build(
        self,
        user_query: str,
        intent: dict[str, Any],
        complexity: dict[str, Any],
        max_results: int,
    ) -> str:
        """
        Genera SQL usando AI con contexto específico de productos.
        """
        schema_context = self._build_schema_context()
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
            system_prompt = (
                "Eres un experto desarrollador SQL especializado "
                "en e-commerce y bases de datos de productos."
            )
            response = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=sql_prompt,
                temperature=0.1,
            )

            return self._clean_sql_response(response)

        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return self._generate_fallback_sql(user_query, intent, max_results)

    async def build_aggregation(
        self,
        user_query: str,
        intent: dict[str, Any],
        aggregation_type: str = "count",
    ) -> str:
        """
        Genera SQL específico para agregaciones.
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

            return self._clean_sql_response(response)

        except Exception as e:
            logger.error(f"Error generating aggregation SQL: {e}")
            raise

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

    def _build_intent_context(self, intent: dict[str, Any]) -> str:
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

    def _generate_fallback_sql(
        self, user_query: str, intent: dict[str, Any], max_results: int
    ) -> str:
        """
        Genera SQL básico como fallback.
        """
        search_params = intent.get("search_params", {})
        keywords = search_params.get("keywords", [])

        if not keywords:
            keywords = [word for word in user_query.split() if len(word) > 2]

        base_sql = """
        SELECT p.*, c.display_name as category_name, b.name as brand_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN brands b ON p.brand_id = b.id
        WHERE p.active = true
        """

        conditions = []

        if keywords:
            keyword_conditions = []
            for keyword in keywords[:3]:
                keyword_conditions.append(f"p.name ILIKE '%{keyword}%'")
                keyword_conditions.append(f"p.description ILIKE '%{keyword}%'")

            if keyword_conditions:
                conditions.append(f"({' OR '.join(keyword_conditions)})")

        filters = intent.get("filters", {})

        price_range = filters.get("price_range", {})
        if price_range.get("min"):
            conditions.append(f"p.price >= {price_range['min']}")
        if price_range.get("max"):
            conditions.append(f"p.price <= {price_range['max']}")

        if filters.get("availability_required", True):
            conditions.append("p.stock > 0")

        if conditions:
            base_sql += " AND " + " AND ".join(conditions)

        base_sql += f" ORDER BY p.created_at DESC LIMIT {max_results};"

        return base_sql
