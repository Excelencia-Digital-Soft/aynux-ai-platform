"""
Product SQL Schemas.

Single Responsibility: Data models for SQL generation results and configuration.
"""

from typing import Any

from pydantic import BaseModel


class ProductSQLResult(BaseModel):
    """Resultado de la ejecución de SQL de productos."""

    success: bool
    data: list[dict[str, Any]] = []
    row_count: int = 0
    generated_sql: str = ""
    execution_time_ms: float = 0.0
    error_message: str | None = None
    metadata: dict[str, Any] = {}


# Security Configuration
ALLOWED_TABLES = {
    "products",
    "categories",
    "brands",
    "product_images",
    "product_attributes",
    "product_reviews",
    "inventory",
}

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
    "GRANT",
    "REVOKE",
}

# Schema de productos para el contexto de AI
PRODUCT_SCHEMA = {
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
