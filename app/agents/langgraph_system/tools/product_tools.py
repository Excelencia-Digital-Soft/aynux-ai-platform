"""
Tools especializadas para el Product Agent
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProductSearchInput(BaseModel):
    """Input para búsqueda de productos"""
    query: str = Field(description="Consulta de búsqueda de productos")
    category: Optional[str] = Field(default=None, description="Categoría específica (opcional)")
    max_results: int = Field(default=5, description="Número máximo de resultados")
    price_min: Optional[float] = Field(default=None, description="Precio mínimo")
    price_max: Optional[float] = Field(default=None, description="Precio máximo")


class ProductDetailsInput(BaseModel):
    """Input para detalles de producto"""
    product_id: str = Field(description="ID del producto")


class StockCheckInput(BaseModel):
    """Input para verificación de stock"""
    product_id: str = Field(description="ID del producto")
    quantity: int = Field(default=1, description="Cantidad deseada")


class ProductCompareInput(BaseModel):
    """Input para comparación de productos"""
    product_ids: List[str] = Field(description="Lista de IDs de productos a comparar")


# Base de datos simulada de productos
PRODUCTS_DB = [
    {
        "id": "laptop_001",
        "name": "Laptop Gaming ASUS ROG",
        "category": "laptops", 
        "price": 1299.99,
        "stock": 5,
        "brand": "ASUS",
        "specs": {
            "processor": "Intel Core i7-12700H",
            "ram": "16GB DDR4",
            "storage": "512GB SSD",
            "graphics": "RTX 3060",
            "screen": "15.6\" Full HD 144Hz"
        },
        "description": "Laptop gaming de alto rendimiento para programación y gaming"
    },
    {
        "id": "laptop_002", 
        "name": "MacBook Pro 14",
        "category": "laptops",
        "price": 1999.99,
        "stock": 3,
        "brand": "Apple",
        "specs": {
            "processor": "Apple M2 Pro",
            "ram": "16GB Unified Memory", 
            "storage": "512GB SSD",
            "graphics": "M2 Pro GPU",
            "screen": "14.2\" Liquid Retina XDR"
        },
        "description": "MacBook Pro profesional para desarrollo y creatividad"
    },
    {
        "id": "laptop_003",
        "name": "Laptop HP Pavilion",
        "category": "laptops",
        "price": 699.99,
        "stock": 8,
        "brand": "HP",
        "specs": {
            "processor": "AMD Ryzen 5 5500U",
            "ram": "8GB DDR4",
            "storage": "256GB SSD",
            "graphics": "AMD Radeon Graphics",
            "screen": "15.6\" Full HD"
        },
        "description": "Laptop económica para uso general y trabajo"
    },
    {
        "id": "phone_001",
        "name": "iPhone 15 Pro",
        "category": "smartphones",
        "price": 999.99,
        "stock": 12,
        "brand": "Apple",
        "specs": {
            "processor": "A17 Pro",
            "ram": "8GB",
            "storage": "128GB",
            "camera": "48MP Triple",
            "screen": "6.1\" Super Retina XDR"
        },
        "description": "Smartphone premium con cámara profesional"
    },
    {
        "id": "phone_002",
        "name": "Samsung Galaxy S24",
        "category": "smartphones", 
        "price": 849.99,
        "stock": 8,
        "brand": "Samsung",
        "specs": {
            "processor": "Snapdragon 8 Gen 3",
            "ram": "8GB",
            "storage": "256GB",
            "camera": "50MP Triple",
            "screen": "6.2\" Dynamic AMOLED"
        },
        "description": "Smartphone Android de alta gama"
    }
]


@tool(args_schema=ProductSearchInput)
async def search_products_tool(
    query: str,
    category: Optional[str] = None,
    max_results: int = 5,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None
) -> Dict[str, Any]:
    """
    Busca productos en el catálogo basado en consulta de texto y filtros.
    
    Útil para encontrar productos específicos que coincidan con las necesidades del cliente.
    """
    logger.info(f"Searching products: query='{query}', category={category}")
    
    # Simular pequeña latencia de búsqueda
    await asyncio.sleep(0.1)
    
    results = []
    query_lower = query.lower()
    
    for product in PRODUCTS_DB:
        # Filtrar por categoría si se especifica
        if category and product["category"] != category.lower():
            continue
            
        # Filtrar por rango de precios
        if price_min and product["price"] < price_min:
            continue
        if price_max and product["price"] > price_max:
            continue
            
        # Buscar en nombre, descripción y especificaciones
        searchable_text = f"{product['name']} {product['description']} {product['brand']}".lower()
        
        # Agregar specs al texto de búsqueda
        for spec_value in product["specs"].values():
            searchable_text += f" {str(spec_value).lower()}"
        
        # Verificar si la consulta coincide
        if any(term in searchable_text for term in query_lower.split()):
            results.append({
                "id": product["id"],
                "name": product["name"],
                "price": product["price"],
                "brand": product["brand"],
                "stock": product["stock"],
                "description": product["description"]
            })
    
    # Limitar resultados
    results = results[:max_results]
    
    return {
        "success": True,
        "results": results,
        "total_found": len(results),
        "query": query,
        "filters_applied": {
            "category": category,
            "price_range": f"${price_min or 0} - ${price_max or 'unlimited'}"
        }
    }


@tool(args_schema=ProductDetailsInput)
async def get_product_details_tool(product_id: str) -> Dict[str, Any]:
    """
    Obtiene detalles completos de un producto específico por su ID.
    
    Útil para proporcionar información detallada sobre especificaciones, precio y disponibilidad.
    """
    logger.info(f"Getting product details for: {product_id}")
    
    # Simular latencia de base de datos
    await asyncio.sleep(0.05)
    
    # Buscar producto
    product = next((p for p in PRODUCTS_DB if p["id"] == product_id), None)
    
    if not product:
        return {
            "success": False,
            "error": f"Producto con ID '{product_id}' no encontrado",
            "product_id": product_id
        }
    
    return {
        "success": True,
        "product": product,
        "availability": "En stock" if product["stock"] > 0 else "Agotado",
        "estimated_delivery": "2-3 días hábiles" if product["stock"] > 0 else "No disponible"
    }


@tool(args_schema=StockCheckInput)
async def check_stock_tool(product_id: str, quantity: int = 1) -> Dict[str, Any]:
    """
    Verifica la disponibilidad de stock para una cantidad específica de un producto.
    
    Útil para confirmar si hay suficiente inventario antes de proceder con una compra.
    """
    logger.info(f"Checking stock for product {product_id}, quantity: {quantity}")
    
    # Simular latencia de verificación de inventario
    await asyncio.sleep(0.03)
    
    product = next((p for p in PRODUCTS_DB if p["id"] == product_id), None)
    
    if not product:
        return {
            "success": False,
            "error": f"Producto con ID '{product_id}' no encontrado"
        }
    
    available_stock = product["stock"]
    is_available = available_stock >= quantity
    
    return {
        "success": True,
        "product_id": product_id,
        "product_name": product["name"],
        "requested_quantity": quantity,
        "available_stock": available_stock,
        "is_available": is_available,
        "status": "Disponible" if is_available else "Stock insuficiente",
        "max_quantity_available": available_stock
    }


@tool(args_schema=ProductCompareInput)
async def compare_products_tool(product_ids: List[str]) -> Dict[str, Any]:
    """
    Compara múltiples productos mostrando sus especificaciones lado a lado.
    
    Útil para ayudar a los clientes a tomar decisiones informadas entre diferentes opciones.
    """
    logger.info(f"Comparing products: {product_ids}")
    
    if len(product_ids) < 2:
        return {
            "success": False,
            "error": "Se necesitan al menos 2 productos para comparar"
        }
    
    if len(product_ids) > 5:
        return {
            "success": False,
            "error": "Máximo 5 productos pueden ser comparados a la vez"
        }
    
    # Simular latencia de comparación
    await asyncio.sleep(0.1)
    
    products_to_compare = []
    not_found = []
    
    for product_id in product_ids:
        product = next((p for p in PRODUCTS_DB if p["id"] == product_id), None)
        if product:
            products_to_compare.append(product)
        else:
            not_found.append(product_id)
    
    if not products_to_compare:
        return {
            "success": False,
            "error": "Ninguno de los productos especificados fue encontrado",
            "not_found": not_found
        }
    
    # Crear tabla de comparación
    comparison = {
        "products": [],
        "comparison_matrix": {},
        "recommendations": []
    }
    
    # Extraer todos los campos de specs únicos
    all_spec_keys = set()
    for product in products_to_compare:
        all_spec_keys.update(product["specs"].keys())
    
    # Organizar datos para comparación
    for product in products_to_compare:
        comparison["products"].append({
            "id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "brand": product["brand"],
            "stock": product["stock"]
        })
    
    # Crear matriz de comparación de specs
    for spec_key in all_spec_keys:
        comparison["comparison_matrix"][spec_key] = []
        for product in products_to_compare:
            spec_value = product["specs"].get(spec_key, "N/A")
            comparison["comparison_matrix"][spec_key].append(spec_value)
    
    # Generar recomendaciones básicas
    if len(products_to_compare) >= 2:
        cheapest = min(products_to_compare, key=lambda p: p["price"])
        most_expensive = max(products_to_compare, key=lambda p: p["price"])
        
        comparison["recommendations"] = [
            f"Opción más económica: {cheapest['name']} (${cheapest['price']})",
            f"Opción premium: {most_expensive['name']} (${most_expensive['price']})"
        ]
    
    return {
        "success": True,
        "comparison": comparison,
        "total_products_compared": len(products_to_compare),
        "not_found": not_found if not_found else None
    }