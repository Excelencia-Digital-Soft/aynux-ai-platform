from fastapi import APIRouter

from app.api.routes import auth, chat, embeddings, phone_normalization, products, sync_status, webhook, dux_sync_admin, langsmith_status

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(webhook.router, tags=["webhook"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(phone_normalization.router, prefix="/phone", tags=["phone"])
api_router.include_router(embeddings.router, tags=["embeddings"])
api_router.include_router(sync_status.router, prefix="/dux", tags=["sync"])
api_router.include_router(dux_sync_admin.router, prefix="/admin/dux", tags=["dux-admin"])
api_router.include_router(langsmith_status.router, prefix="/admin", tags=["monitoring"])
