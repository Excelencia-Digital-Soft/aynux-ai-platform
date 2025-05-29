from fastapi import APIRouter

from app.api.routes import auth, phone_normalization, webhook

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(webhook.router, tags=["webhook"])
api_router.include_router(phone_normalization.router, prefix="/phone", tags=["phone"])
