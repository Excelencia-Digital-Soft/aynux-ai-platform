"""
E-commerce API Routes

FastAPI router for e-commerce endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.domains.ecommerce.api.dependencies import (
    get_featured_products_use_case,
    get_product_by_id_use_case,
    get_products_by_category_use_case,
    get_search_products_use_case,
)
from app.domains.ecommerce.api.schemas import (
    ProductResponse,
    ProductSearchRequest,
    ProductSearchResponse,
)
from app.domains.ecommerce.application.use_cases import (
    GetFeaturedProductsUseCase,
    GetProductByIdUseCase,
    GetProductsByCategoryUseCase,
    SearchProductsUseCase,
)

router = APIRouter(prefix="/ecommerce", tags=["E-commerce"])


@router.post("/products/search", response_model=ProductSearchResponse)
async def search_products(
    request: ProductSearchRequest,
    use_case: SearchProductsUseCase = Depends(get_search_products_use_case),
):
    """Search products by query."""
    result = await use_case.execute(
        query=request.query,
        limit=request.limit,
    )
    return ProductSearchResponse(
        products=[ProductResponse.model_validate(p) for p in result.products],
        total=result.total_found,
        query=result.query,
    )


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    use_case: GetProductByIdUseCase = Depends(get_product_by_id_use_case),
):
    """Get product by ID."""
    result = await use_case.execute(product_id=product_id)
    if result.product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(result.product)


@router.get("/products/category/{category_id}", response_model=list[ProductResponse])
async def get_products_by_category(
    category_id: int,
    limit: int = 20,
    use_case: GetProductsByCategoryUseCase = Depends(get_products_by_category_use_case),
):
    """Get products by category."""
    result = await use_case.execute(category_id=category_id, limit=limit)
    return [ProductResponse.model_validate(p) for p in result.products]


@router.get("/products/featured", response_model=list[ProductResponse])
async def get_featured_products(
    limit: int = 10,
    use_case: GetFeaturedProductsUseCase = Depends(get_featured_products_use_case),
):
    """Get featured products."""
    result = await use_case.execute(limit=limit)
    return [ProductResponse.model_validate(p) for p in result.products]


__all__ = ["router"]
