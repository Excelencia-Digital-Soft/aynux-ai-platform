"""
Admin API routes for multi-tenant management.

Includes:
- organizations: Organization CRUD
- org_users: User management within organizations
- tenant_config: Tenant-specific configuration
- tenant_credentials: Encrypted credentials per tenant (WhatsApp, DUX, Plex)
- tenant_agents: Agent configuration per tenant
- tenant_prompts: Prompt overrides per tenant
- tenant_documents: Per-tenant knowledge base documents
- agent_knowledge: Global per-agent knowledge bases
- prompts: System-wide prompt management
"""

from . import (
    agent_flow,
    agent_knowledge,
    agents,
    ai_models,
    bypass_rules,
    chattigo_credentials,
    domain_intents,
    domains,
    institution_configs,
    modules,
    org_users,
    organizations,
    prompts,
    response_configs,
    tenant_agents,
    tenant_config,
    tenant_credentials,
    tenant_documents,
    tenant_prompts,
)

__all__ = [
    "organizations",
    "org_users",
    "tenant_config",
    "tenant_credentials",
    "chattigo_credentials",
    "tenant_agents",
    "tenant_prompts",
    "tenant_documents",
    "agent_knowledge",
    "agents",
    "prompts",
    "bypass_rules",
    "ai_models",
    "agent_flow",
    "modules",
    "domains",
    "institution_configs",
    "domain_intents",
    "response_configs",
]
