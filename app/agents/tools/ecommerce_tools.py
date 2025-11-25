"""
Tools especializadas para operaciones de e-commerce
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CategoryInput(BaseModel):
    """Input para obtener categorías"""

    parent_category: Optional[str] = Field(default=None, description="Categoría padre (opcional)")


class PromotionsInput(BaseModel):
    """Input para obtener promociones"""

    category: Optional[str] = Field(default=None, description="Filtrar por categoría")
    active_only: bool = Field(default=True, description="Solo promociones activas")


class ShippingInput(BaseModel):
    """Input para calcular envío"""

    product_id: str = Field(description="ID del producto")
    quantity: int = Field(default=1, description="Cantidad")
    postal_code: str = Field(description="Código postal de destino")
    shipping_method: str = Field(default="standard", description="Método de envío")


class PaymentMethodsInput(BaseModel):
    """Input para métodos de pago"""

    order_amount: Optional[float] = Field(default=None, description="Monto del pedido")


# Base de datos simulada de categorías
CATEGORIES_DB = [
    {
        "id": "laptops",
        "name": "Laptops y Computadoras",
        "parent": None,
        "description": "Equipos de cómputo portátiles y de escritorio",
        "product_count": 15,
        "subcategories": ["gaming", "business", "ultrabooks"],
    },
    {
        "id": "smartphones",
        "name": "Smartphones y Móviles",
        "parent": None,
        "description": "Teléfonos inteligentes y accesorios",
        "product_count": 8,
        "subcategories": ["android", "iphone", "accessories"],
    },
    {
        "id": "gaming",
        "name": "Laptops Gaming",
        "parent": "laptops",
        "description": "Laptops especializadas para gaming",
        "product_count": 5,
        "subcategories": [],
    },
    {
        "id": "business",
        "name": "Laptops Empresariales",
        "parent": "laptops",
        "description": "Equipos para uso profesional",
        "product_count": 6,
        "subcategories": [],
    },
]

# Base de datos simulada de promociones
PROMOTIONS_DB = [
    {
        "id": "promo_001",
        "name": "Black Friday Tech",
        "description": "Descuentos especiales en tecnología",
        "discount_percentage": 25,
        "category": "laptops",
        "active": True,
        "start_date": "2024-11-25",
        "end_date": "2024-11-30",
        "conditions": "Compras mayores a $500",
    },
    {
        "id": "promo_002",
        "name": "Cyber Monday Móviles",
        "description": "Ofertas exclusivas en smartphones",
        "discount_percentage": 15,
        "category": "smartphones",
        "active": True,
        "start_date": "2024-12-02",
        "end_date": "2024-12-05",
        "conditions": "Válido solo online",
    },
    {
        "id": "promo_003",
        "name": "Envío Gratis",
        "description": "Envío gratuito en compras mayores",
        "discount_percentage": 0,
        "category": None,
        "active": True,
        "start_date": "2024-12-01",
        "end_date": "2024-12-31",
        "conditions": "Compras mayores a $300",
    },
]

# Tarifas de envío simuladas
SHIPPING_RATES = {
    "standard": {"price": 10.99, "days": "5-7", "description": "Envío estándar"},
    "express": {"price": 19.99, "days": "2-3", "description": "Envío express"},
    "overnight": {"price": 39.99, "days": "1", "description": "Entrega al día siguiente"},
}

# Métodos de pago disponibles
PAYMENT_METHODS = [
    {
        "id": "credit_card",
        "name": "Tarjeta de Crédito",
        "description": "Visa, MasterCard, American Express",
        "fees": 0,
        "min_amount": 1,
        "max_amount": 10000,
        "installments": [1, 3, 6, 12],
    },
    {
        "id": "debit_card",
        "name": "Tarjeta de Débito",
        "description": "Débito directo de cuenta bancaria",
        "fees": 0,
        "min_amount": 1,
        "max_amount": 5000,
        "installments": [1],
    },
    {
        "id": "paypal",
        "name": "PayPal",
        "description": "Pago seguro con PayPal",
        "fees": 2.9,
        "min_amount": 1,
        "max_amount": 8000,
        "installments": [1],
    },
    {
        "id": "bank_transfer",
        "name": "Transferencia Bancaria",
        "description": "Transferencia directa a cuenta bancaria",
        "fees": 0,
        "min_amount": 100,
        "max_amount": 50000,
        "installments": [1],
    },
]


@tool(args_schema=CategoryInput)
async def get_categories_tool(parent_category: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene las categorías de productos disponibles, opcionalmente filtradas por categoría padre.

    Útil para mostrar al cliente la estructura del catálogo y ayudar en la navegación.
    """
    logger.info(f"Getting categories, parent: {parent_category}")

    # Simular latencia de base de datos
    await asyncio.sleep(0.05)

    # Filtrar categorías
    if parent_category:
        categories = [cat for cat in CATEGORIES_DB if cat.get("parent") == parent_category]
    else:
        categories = [cat for cat in CATEGORIES_DB if cat.get("parent") is None]  # Solo categorías raíz

    # Calcular estadísticas
    total_products = sum(cat["product_count"] for cat in categories)

    return {
        "success": True,
        "categories": categories,
        "total_categories": len(categories),
        "total_products": total_products,
        "parent_category": parent_category,
    }


@tool(args_schema=PromotionsInput)
async def get_promotions_tool(category: Optional[str] = None, active_only: bool = True) -> Dict[str, Any]:
    """
    Obtiene promociones y ofertas especiales disponibles, opcionalmente filtradas por categoría.

    Útil para informar al cliente sobre descuentos actuales y ofertas especiales.
    """
    logger.info(f"Getting promotions for category: {category}, active_only: {active_only}")

    # Simular latencia
    await asyncio.sleep(0.08)

    promotions = PROMOTIONS_DB.copy()

    # Filtrar por estado activo
    if active_only:
        promotions = [promo for promo in promotions if promo["active"]]

    # Filtrar por categoría
    if category:
        promotions = [
            promo for promo in promotions if promo.get("category") == category or promo.get("category") is None
        ]

    # Calcular ahorros totales disponibles
    total_savings = 0.0
    for promo in promotions:
        discount = promo.get("discount_percentage")
        if isinstance(discount, (int, float)) and discount > 0:
            total_savings += float(discount)

    return {
        "success": True,
        "promotions": promotions,
        "total_promotions": len(promotions),
        "category_filter": category,
        "active_only": active_only,
        "max_savings_available": max([p["discount_percentage"] for p in promotions] + [0]),
        "total_savings": total_savings,
    }


@tool(args_schema=ShippingInput)
async def calculate_shipping_tool(
    product_id: str, quantity: int = 1, postal_code: str = "", shipping_method: str = "standard"
) -> Dict[str, Any]:
    """
    Calcula el costo y tiempo de envío para un producto específico.

    Útil para proporcionar información precisa de costos de entrega antes de la compra.
    """
    logger.info(f"Calculating shipping for product {product_id}, qty: {quantity}, method: {shipping_method}")

    # Simular latencia de cálculo
    await asyncio.sleep(0.1)

    # Validar método de envío
    if shipping_method not in SHIPPING_RATES:
        return {
            "success": False,
            "error": f"Método de envío '{shipping_method}' no válido",
            "available_methods": list(SHIPPING_RATES.keys()),
        }

    # Obtener información del método de envío
    shipping_info = SHIPPING_RATES[shipping_method]
    base_cost = float(shipping_info["price"])

    # Calcular costo ajustado por cantidad (descuento por volumen)
    if quantity > 1:
        volume_discount = min(0.15, (quantity - 1) * 0.05)  # Máximo 15% descuento
        final_cost = base_cost * (1 - volume_discount)
    else:
        final_cost = base_cost

    # Simular verificación de código postal (básica)
    postal_code_valid = len(postal_code) >= 5 if postal_code else True
    if postal_code and not postal_code_valid:
        return {"success": False, "error": "Código postal inválido", "postal_code": postal_code}

    # Verificar si aplica envío gratis
    free_shipping_promo = next((p for p in PROMOTIONS_DB if p["id"] == "promo_003"), None)
    estimated_order_value = quantity * 150  # Valor estimado por producto
    free_shipping_applies = free_shipping_promo and free_shipping_promo["active"] and estimated_order_value >= 300

    if free_shipping_applies:
        final_cost = 0

    return {
        "success": True,
        "shipping_cost": round(final_cost, 2),
        "estimated_delivery": shipping_info["days"],
        "shipping_method": shipping_method,
        "method_description": shipping_info["description"],
        "quantity": quantity,
        "postal_code": postal_code,
        "free_shipping": free_shipping_applies,
        "volume_discount_applied": quantity > 1,
        "all_shipping_options": [
            {
                "method": method,
                "cost": info["price"] if not free_shipping_applies else 0,
                "delivery_time": info["days"],
                "description": info["description"],
            }
            for method, info in SHIPPING_RATES.items()
        ],
    }


@tool(args_schema=PaymentMethodsInput)
async def get_payment_methods_tool(order_amount: Optional[float] = None) -> Dict[str, Any]:
    """
    Obtiene los métodos de pago disponibles, opcionalmente filtrados por monto del pedido.

    Útil para mostrar opciones de pago válidas según el valor de la compra.
    """
    logger.info(f"Getting payment methods for amount: {order_amount}")

    # Simular latencia
    await asyncio.sleep(0.03)

    available_methods = []

    for method in PAYMENT_METHODS:
        # Verificar si el método es válido para el monto
        if order_amount:
            min_amt = float(method["min_amount"]) if isinstance(method.get("min_amount"), (int, float, list)) else 0
            max_amt = (
                float(method["max_amount"])
                if isinstance(method.get("max_amount"), (int, float, list))
                else float("inf")
            )
            if order_amount < min_amt or order_amount > max_amt:
                continue

        # Calcular comisión si aplica
        fee_amount = 0
        method_fees = float(method.get("fees", 0)) if isinstance(method.get("fees"), (int, float, list)) else 0
        if method_fees > 0 and order_amount:
            fee_amount = round(order_amount * (method_fees / 100), 2)

        method_info = method.copy()
        method_info["calculated_fee"] = fee_amount

        # Calcular cuotas disponibles según el monto
        if order_amount and order_amount >= 100:
            available_installments = method["installments"]
        else:
            available_installments = [1]  # Solo una cuota para montos pequeños

        method_info["available_installments"] = available_installments

        # Calcular valor de cuotas
        if order_amount:
            installment_values = {}
            for installments in available_installments:
                monthly_amount = (order_amount + fee_amount) / installments
                installment_values[str(installments)] = round(monthly_amount, 2)
            method_info["installment_values"] = installment_values

        available_methods.append(method_info)

    # Recomendar método óptimo
    recommended_method = None
    if available_methods:
        if order_amount and order_amount >= 1000:
            # Para montos altos, recomendar transferencia (sin comisión)
            recommended_method = next((m for m in available_methods if m["id"] == "bank_transfer"), None)
        else:
            # Para montos normales, recomendar tarjeta de crédito
            recommended_method = next((m for m in available_methods if m["id"] == "credit_card"), None)

        if not recommended_method:
            recommended_method = available_methods[0]

    return {
        "success": True,
        "payment_methods": available_methods,
        "total_methods": len(available_methods),
        "order_amount": order_amount,
        "recommended_method": recommended_method["id"] if recommended_method else None,
        "security_features": [
            "Encriptación SSL/TLS",
            "Tokenización de tarjetas",
            "Verificación 3D Secure",
            "Monitoreo antifraude",
        ],
    }
