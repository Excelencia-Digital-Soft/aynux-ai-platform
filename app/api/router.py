from fastapi import APIRouter

from app.api.routes import auth, embeddings, phone_normalization, products, webhook

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(webhook.router, tags=["webhook"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(phone_normalization.router, prefix="/phone", tags=["phone"])
api_router.include_router(embeddings.router, tags=["embeddings"])
