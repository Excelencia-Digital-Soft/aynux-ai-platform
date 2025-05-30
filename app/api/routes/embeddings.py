from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Any, Optional
from app.services.embedding_update_service import EmbeddingUpdateService
from app.services.enhanced_product_service import EnhancedProductService
from app.api.dependencies import get_current_user
from app.models.auth import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

@router.post("/update", response_model=Dict[str, Any])
async def update_embeddings(
    background_tasks: BackgroundTasks,
    product_id: Optional[int] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Update product embeddings in the background
    """
    try:
        service = EmbeddingUpdateService()
        
        if product_id:
            # Update specific product
            background_tasks.add_task(service.update_product_embeddings, product_id)
            return {
                "status": "scheduled",
                "message": f"Embedding update scheduled for product {product_id}"
            }
        else:
            # Update all products
            background_tasks.add_task(service.update_all_embeddings)
            return {
                "status": "scheduled", 
                "message": "Full embedding update scheduled for all products"
            }
            
    except Exception as e:
        logger.error(f"Error scheduling embedding update: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to schedule embedding update")

@router.get("/stats", response_model=Dict[str, Any])
async def get_embedding_stats(
    current_user: User = Depends(get_current_user)
):
    """
    Get statistics about product embeddings
    """
    try:
        service = EnhancedProductService()
        stats = await service.get_embedding_stats()
        
        return {
            "status": "success",
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting embedding stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get embedding statistics")

@router.post("/search", response_model=Dict[str, Any])
async def search_products_semantic(
    query: str,
    category: Optional[str] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    """
    Search products using semantic search
    """
    try:
        service = EmbeddingUpdateService()
        results = await service.search_products(
            query=query,
            category=category,
            k=limit
        )
        
        return {
            "status": "success",
            "query": query,
            "category": category,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error in semantic search: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to perform semantic search")