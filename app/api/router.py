from fastapi import APIRouter

from app.api.routes import (
    agent_config,
    agents_admin,
    auth,
    chat,
    document_upload,
    domain_admin,
    dux_sync_admin,
    knowledge_admin,
    langsmith_status,
    phone_normalization,
    sync_status,
    webhook,
    whatsapp_catalog,
)
from app.api.routes.admin import prompts as admin_prompts

api_router = APIRouter()

# API routes (all have /api/v1 prefix from main.py)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(webhook.router, tags=["webhook"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(phone_normalization.router, prefix="/phone", tags=["phone"])
api_router.include_router(sync_status.router, prefix="/dux", tags=["sync"])
api_router.include_router(dux_sync_admin.router, prefix="/admin/dux", tags=["dux-admin"])
api_router.include_router(agents_admin.router, tags=["agents-admin"])
api_router.include_router(domain_admin.router, tags=["domain-admin"])
api_router.include_router(langsmith_status.router, prefix="/admin", tags=["monitoring"])
api_router.include_router(knowledge_admin.router, tags=["Knowledge Base"])
api_router.include_router(document_upload.router, tags=["Document Upload"])
api_router.include_router(agent_config.router, tags=["Agent Configuration"])
api_router.include_router(whatsapp_catalog.router, tags=["WhatsApp Catalog & Flows"])

# Admin routes - Prompt Management
api_router.include_router(admin_prompts.router)
