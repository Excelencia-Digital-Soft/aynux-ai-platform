from fastapi import APIRouter

from app.api.routes import auth, webhook

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(webhook.router, tags=["webhook"])
