from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.config.products_config import (
    BRANDS_INFO,
    CURRENT_PROMOTIONS,
    PRODUCTS_CATALOG,
    get_product_recommendations,
    get_products_by_price_range,
)

router = APIRouter(prefix="/products", tags=["products"])


# Modelos Pydantic para las respuestas
class ProductResponse(BaseModel):
    name: str
    specs: str
    price: int
    category: str
    stock: int


class PromotionResponse(BaseModel):
    name: str
    description: str
    discount: int
    valid_until: str
    items: List[str]


class PriceRangeRequest(BaseModel):
    min_price: int
    max_price: int


class UserProfile(BaseModel):
    interests: List[str]
    budget: int


@router.get("/catalog", response_model=Dict[str, Any])
async def get_full_catalog():
    """
    Obtiene el catálogo completo de productos
    """
    return {"status": "success", "data": PRODUCTS_CATALOG, "total_categories": len(PRODUCTS_CATALOG)}


@router.get("/laptops", response_model=List[ProductResponse])
async def get_laptops(
    category: Optional[str] = Query(None, description="gaming, work, budget"),
    min_price: Optional[int] = Query(None, description="Precio mínimo"),
    max_price: Optional[int] = Query(None, description="Precio máximo"),
):
    """
    Obtiene laptops filtradas por categoría y precio
    """
    try:
        laptops = []

        if category and category in PRODUCTS_CATALOG["laptops"]:
            laptops = PRODUCTS_CATALOG["laptops"][category]
        else:
            # Si no especifica categoría, devolver todas
            for cat in PRODUCTS_CATALOG["laptops"].values():
                laptops.extend(cat)

        # Filtrar por precio si se especifica
        if min_price is not None or max_price is not None:
            filtered_laptops = []
            for laptop in laptops:
                price = laptop["price"]
                if min_price is not None and price < min_price:
                    continue
                if max_price is not None and price > max_price:
                    continue
                filtered_laptops.append(laptop)
            laptops = filtered_laptops

        return [ProductResponse(**laptop) for laptop in laptops]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo laptops: {str(e)}") from e


@router.get("/desktops", response_model=List[ProductResponse])
async def get_desktops(category: Optional[str] = Query(None, description="gaming, work")):
    """
    Obtiene PCs de escritorio por categoría
    """
    try:
        if category and category in PRODUCTS_CATALOG["desktops"]:
            desktops = PRODUCTS_CATALOG["desktops"][category]
        else:
            desktops = []
            for cat in PRODUCTS_CATALOG["desktops"].values():
                desktops.extend(cat)

        return [ProductResponse(**desktop) for desktop in desktops]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo desktops: {str(e)}") from e


@router.get("/components", response_model=Dict[str, List[ProductResponse]])
async def get_components():
    """
    Obtiene todos los componentes disponibles
    """
    try:
        result = {}
        for component_type, items in PRODUCTS_CATALOG["components"].items():
            result[component_type] = [ProductResponse(**item) for item in items]

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo componentes: {str(e)}") from e


@router.get("/peripherals", response_model=List[ProductResponse])
async def get_peripherals():
    """
    Obtiene todos los periféricos disponibles
    """
    try:
        return [ProductResponse(**item) for item in PRODUCTS_CATALOG["peripherals"]]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo periféricos: {str(e)}") from e


@router.get("/promotions", response_model=Dict[str, PromotionResponse])
async def get_current_promotions():
    """
    Obtiene las promociones vigentes
    """
    try:
        result = {}
        for promo_id, promo_data in CURRENT_PROMOTIONS.items():
            result[promo_id] = PromotionResponse(**promo_data)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo promociones: {str(e)}") from e


@router.post("/search-by-price", response_model=List[ProductResponse])
async def search_products_by_price(price_range: PriceRangeRequest):
    """
    Busca productos dentro de un rango de precios
    """
    try:
        products = get_products_by_price_range(price_range.min_price, price_range.max_price)
        return [ProductResponse(**product) for product in products]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error buscando por precio: {str(e)}") from e


@router.post("/recommendations", response_model=List[ProductResponse])
async def get_recommendations(user_profile: UserProfile):
    """
    Obtiene recomendaciones basadas en el perfil del usuario
    """
    try:
        profile_dict = {"interests": user_profile.interests, "budget": user_profile.budget}

        recommendations = get_product_recommendations(profile_dict)
        return [ProductResponse(**product) for product in recommendations]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando recomendaciones: {str(e)}") from e


@router.get("/brands", response_model=Dict[str, Any])
async def get_brands_info():
    """
    Obtiene información sobre las marcas disponibles
    """
    return {"status": "success", "brands": BRANDS_INFO, "total_brands": len(BRANDS_INFO)}


@router.get("/stock-report", response_model=Dict[str, Any])
async def get_stock_report():
    """
    Genera un reporte de stock por categorías
    """
    try:
        report = {"laptops": {}, "desktops": {}, "components": {}, "peripherals": {"total_stock": 0, "products": []}}

        # Stock de laptops
        for category, laptops in PRODUCTS_CATALOG["laptops"].items():
            total_stock = sum(laptop["stock"] for laptop in laptops)
            low_stock = [laptop for laptop in laptops if laptop["stock"] <= 5]
            report["laptops"][category] = {
                "total_stock": total_stock,
                "products_count": len(laptops),
                "low_stock_items": len(low_stock),
                "low_stock_products": [item["name"] for item in low_stock],
            }

        # Stock de desktops
        for category, desktops in PRODUCTS_CATALOG["desktops"].items():
            total_stock = sum(desktop["stock"] for desktop in desktops)
            low_stock = [desktop for desktop in desktops if desktop["stock"] <= 5]
            report["desktops"][category] = {
                "total_stock": total_stock,
                "products_count": len(desktops),
                "low_stock_items": len(low_stock),
                "low_stock_products": [item["name"] for item in low_stock],
            }

        # Stock de componentes
        for comp_type, components in PRODUCTS_CATALOG["components"].items():
            total_stock = sum(comp["stock"] for comp in components)
            low_stock = [comp for comp in components if comp["stock"] <= 5]
            report["components"][comp_type] = {
                "total_stock": total_stock,
                "products_count": len(components),
                "low_stock_items": len(low_stock),
                "low_stock_products": [item["name"] for item in low_stock],
            }

        # Stock de periféricos
        total_periph_stock = sum(item["stock"] for item in PRODUCTS_CATALOG["peripherals"])
        low_stock_periph = [item for item in PRODUCTS_CATALOG["peripherals"] if item["stock"] <= 5]
        report["peripherals"] = {
            "total_stock": total_periph_stock,
            "products_count": len(PRODUCTS_CATALOG["peripherals"]),
            "low_stock_items": len(low_stock_periph),
            "low_stock_products": [item["name"] for item in low_stock_periph],
        }

        return {"status": "success", "report": report, "generated_at": "2025-05-27"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando reporte: {str(e)}") from e


@router.get("/price-analysis", response_model=Dict[str, Any])
async def get_price_analysis():
    """
    Análisis de precios por categorías
    """
    try:
        analysis = {}

        # Análisis de laptops
        for category, laptops in PRODUCTS_CATALOG["laptops"].items():
            prices = [laptop["price"] for laptop in laptops]
            analysis[f"laptops_{category}"] = {
                "min_price": min(prices),
                "max_price": max(prices),
                "avg_price": sum(prices) // len(prices),
                "products_count": len(laptops),
            }

        # Análisis de desktops
        for category, desktops in PRODUCTS_CATALOG["desktops"].items():
            prices = [desktop["price"] for desktop in desktops]
            analysis[f"desktops_{category}"] = {
                "min_price": min(prices),
                "max_price": max(prices),
                "avg_price": sum(prices) // len(prices),
                "products_count": len(desktops),
            }

        return {"status": "success", "price_analysis": analysis}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en análisis de precios: {str(e)}") from e


# Endpoints protegidos para administración (requieren autenticación)
@router.put("/update-stock/{product_name}", dependencies=[Depends(get_current_user)])
async def update_product_stock(product_name: str, new_stock: int):
    """
    Actualiza el stock de un producto (requiere autenticación)
    """
    # Esta función requeriría persistencia real en base de datos
    # Por ahora solo simula la operación

    product_found = False

    # Buscar en todas las categorías
    for category in PRODUCTS_CATALOG.values():
        if isinstance(category, dict):
            for subcategory in category.values():
                if isinstance(subcategory, list):
                    for product in subcategory:
                        if product["name"].lower() == product_name.lower():
                            product["stock"] = new_stock
                            product_found = True
                            break
        elif isinstance(category, list):
            for product in category:
                if product["name"].lower() == product_name.lower():
                    product["stock"] = new_stock
                    product_found = True
                    break

    if not product_found:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return {"status": "success", "message": f"Stock actualizado para {product_name}", "new_stock": new_stock}
