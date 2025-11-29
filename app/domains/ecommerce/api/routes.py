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
from app.domains.ecommerce.application.use_cases.get_featured_products import (
    GetFeaturedProductsRequest,
)
from app.domains.ecommerce.application.use_cases.get_products_by_category import (
    GetProductsByCategoryRequest,
)
from app.domains.ecommerce.application.use_cases.search_products import (
    SearchProductsRequest,
)

router = APIRouter(prefix="/ecommerce", tags=["E-commerce"])


@router.post("/products/search", response_model=ProductSearchResponse)
async def search_products(
    request: ProductSearchRequest,
    use_case: SearchProductsUseCase = Depends(get_search_products_use_case),
):
    """Search products by query."""
    use_case_request = SearchProductsRequest(
        query=request.query,
        limit=request.limit,
    )
    result = await use_case.execute(use_case_request)
    return ProductSearchResponse(
        products=[ProductResponse.model_validate(prod) for prod in result.products],
        total=result.total_count,
        query=request.query,
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


@router.get("/products/category/{category_name}", response_model=list[ProductResponse])
async def get_products_by_category(
    category_name: str,
    limit: int = 20,
    use_case: GetProductsByCategoryUseCase = Depends(get_products_by_category_use_case),
):
    """Get products by category name."""
    use_case_request = GetProductsByCategoryRequest(
        category=category_name,
        limit=limit,
    )
    result = await use_case.execute(use_case_request)
    return [ProductResponse.model_validate(prod) for prod in result.products]


@router.get("/products/featured", response_model=list[ProductResponse])
async def get_featured_products(
    limit: int = 10,
    use_case: GetFeaturedProductsUseCase = Depends(get_featured_products_use_case),
):
    """Get featured products."""
    use_case_request = GetFeaturedProductsRequest(limit=limit)
    result = await use_case.execute(use_case_request)
    return [ProductResponse.model_validate(prod) for prod in result.products]


__all__ = ["router"]
