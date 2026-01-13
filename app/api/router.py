from fastapi import APIRouter

from app.api.routes import (
    agent_config,
    agents_admin,
    auth,
    chat,
    conversation_history,
    document_upload,
    domain_admin,
    dux_sync_admin,
    jira_webhook,
    knowledge_admin,
    knowledge_unified,
    langsmith_status,
    mercadopago_webhook,
    phone_normalization,
    sync_status,
    webhook,
    whatsapp_catalog,
)
from app.api.routes.admin import (
    agent_flow,
    agent_knowledge,
    agents as agents_catalog,
    ai_models,
    bypass_rules,
    chat_admin,
    chattigo_credentials,
    domains,
    institution_configs,
    intent_configs,
    modules as modules_admin,
    org_users,
    organizations,
    domain_intents,
    pharmacy_config,
    pharmacy_conversations,
    response_configs,
    routing_config,
    tenant_agents,
    tenant_config,
    tenant_credentials,
    tenant_documents,
    tenant_prompts,
)
from app.api.routes.admin import (
    analytics as analytics_admin,
)
from app.api.routes.admin import (
    pharmacy as pharmacy_admin,
)
from app.api.routes.admin import prompts as admin_prompts

api_router = APIRouter()

# API routes (all have /api/v1 prefix from main.py)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(webhook.router, tags=["webhook"])
api_router.include_router(mercadopago_webhook.router, tags=["Mercado Pago Webhook"])
api_router.include_router(jira_webhook.router, tags=["Jira Webhook"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(phone_normalization.router, prefix="/phone", tags=["phone"])
api_router.include_router(sync_status.router, prefix="/dux", tags=["sync"])
api_router.include_router(dux_sync_admin.router, prefix="/admin/dux", tags=["dux-admin"])
api_router.include_router(agents_admin.router, tags=["agents-admin"])
api_router.include_router(domain_admin.router, tags=["domain-admin"])
api_router.include_router(langsmith_status.router, prefix="/admin", tags=["monitoring"])
api_router.include_router(knowledge_admin.router, tags=["Knowledge Base"])
api_router.include_router(knowledge_unified.router, tags=["Unified Knowledge"])
api_router.include_router(document_upload.router, tags=["Document Upload"])
api_router.include_router(agent_config.router, tags=["Agent Configuration"])
api_router.include_router(whatsapp_catalog.router, tags=["WhatsApp Catalog & Flows"])
api_router.include_router(conversation_history.router)
# Note: excelencia_admin router removed - software catalog now uses company_knowledge

# Admin routes - Software Modules Catalog (Excelencia frontend-compatible API)
api_router.include_router(modules_admin.router, tags=["Software Modules"])

# Admin routes - Prompt Management
api_router.include_router(admin_prompts.router)

# Admin routes - Multi-tenant Organization Management
api_router.include_router(
    organizations.router,
    prefix="/admin/organizations",
    tags=["Organizations"],
)
api_router.include_router(
    org_users.router,
    prefix="/admin/organizations",
    tags=["Organization Users"],
)
api_router.include_router(
    tenant_config.router,
    prefix="/admin/organizations",
    tags=["Tenant Configuration"],
)
api_router.include_router(
    tenant_credentials.router,
    prefix="/admin/organizations",
    tags=["Tenant Credentials"],
)
api_router.include_router(
    tenant_agents.router,
    prefix="/admin/organizations",
    tags=["Tenant Agents"],
)
api_router.include_router(
    bypass_rules.router,
    prefix="/admin/organizations",
    tags=["Bypass Rules"],
)
# Agent Flow Visualization - Global Mode (no org_id)
api_router.include_router(
    agent_flow.router,
    prefix="/admin",
    tags=["Agent Flow Visualization"],
)
# Agent Flow Visualization - Multi-tenant Mode (with org_id)
api_router.include_router(
    agent_flow.router,
    prefix="/admin/organizations",
    tags=["Agent Flow Visualization"],
)
api_router.include_router(
    tenant_prompts.router,
    prefix="/admin/organizations",
    tags=["Tenant Prompts"],
)
api_router.include_router(
    tenant_documents.router,
    prefix="/admin/organizations",
    tags=["Tenant Documents"],
)

# Admin routes - Institution Configs (per-org institution configurations)
api_router.include_router(
    institution_configs.router,
    prefix="/admin/organizations",
    tags=["Institution Configs"],
)

# Admin routes - Agent Knowledge Management (Global per-agent knowledge bases)
api_router.include_router(
    agent_knowledge.router,
    prefix="/admin",
    tags=["Agent Knowledge"],
)

# Admin routes - Analytics (Embedding statistics and management)
api_router.include_router(
    analytics_admin.router,
    prefix="/admin/analytics",
    tags=["Analytics"],
)

# Admin routes - AI Model Management (dynamic model registry)
api_router.include_router(
    ai_models.router,
    prefix="/admin/ai-models",
    tags=["AI Models"],
)

# Admin routes - Agent Catalog Management (replaces ENABLED_AGENTS env var)
api_router.include_router(
    agents_catalog.router,
    prefix="/admin/agents",
    tags=["Agent Catalog"],
)

# Admin routes - Domain Management (centralized domain registry)
api_router.include_router(
    domains.router,
    prefix="/admin/domains",
    tags=["Domains"],
)

# Admin routes - Pharmacy Testing (public - for Vue.js testing interface)
api_router.include_router(
    pharmacy_admin.router,
    tags=["Pharmacy Admin"],
)

# Admin routes - Chat Admin (for Chat Visualizer testing interface)
api_router.include_router(
    chat_admin.router,
    prefix="/admin/chat",
    tags=["Chat Admin"],
)

# Admin routes - Pharmacy Config CRUD (per-organization pharmacy settings)
api_router.include_router(
    pharmacy_config.router,
    prefix="/admin/pharmacy-config",
    tags=["Pharmacy Config"],
)

# Admin routes - Pharmacy Conversations (message history endpoints)
api_router.include_router(
    pharmacy_conversations.router,
    prefix="/admin/pharmacy-config",
    tags=["Pharmacy Conversations"],
)

# Admin routes - Chattigo Credentials (Multi-DID support for Chattigo ISV)
api_router.include_router(
    chattigo_credentials.router,
    prefix="/admin",
    tags=["Chattigo Credentials"],
)

# Admin routes - Domain Intent Patterns (multi-domain, unified structure)
api_router.include_router(
    domain_intents.router,
    prefix="/admin/intents",
    tags=["Domain Intents"],
)

# Admin routes - Response Configs (multi-domain response generation config)
api_router.include_router(
    response_configs.router,
    prefix="/admin/response-configs",
    tags=["Response Configs"],
)

# Admin routes - Intent Configs (intent-agent mappings, flow agents, keywords)
api_router.include_router(
    intent_configs.router,
    prefix="/admin/intent-configs",
    tags=["Intent Configs"],
)

# Admin routes - Routing Configs (DB-driven routing for pharmacy flow)
api_router.include_router(
    routing_config.router,
    prefix="/admin",
    tags=["Routing Configs"],
)
