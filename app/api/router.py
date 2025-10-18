from fastapi import APIRouter

from app.api.routes import auth, chat, domain_admin, dux_sync_admin, embeddings, langsmith_status, phone_normalization, products, sync_status, webhook, whatsapp_catalog

api_router = APIRouter()

# API routes (all have /api/v1 prefix from main.py)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(webhook.router, tags=["webhook"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(phone_normalization.router, prefix="/phone", tags=["phone"])
api_router.include_router(embeddings.router, tags=["embeddings"])
api_router.include_router(sync_status.router, prefix="/dux", tags=["sync"])
api_router.include_router(dux_sync_admin.router, prefix="/admin/dux", tags=["dux-admin"])
api_router.include_router(domain_admin.router, tags=["domain-admin"])
api_router.include_router(langsmith_status.router, prefix="/admin", tags=["monitoring"])
api_router.include_router(whatsapp_catalog.router, tags=["WhatsApp Catalog & Flows"])
