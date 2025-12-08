"""
Admin API routes for multi-tenant management.

Includes:
- organizations: Organization CRUD
- org_users: User management within organizations
- tenant_config: Tenant-specific configuration
- tenant_agents: Agent configuration per tenant
- tenant_prompts: Prompt overrides per tenant
- tenant_documents: Per-tenant knowledge base documents
- prompts: System-wide prompt management
"""

from . import (
    org_users,
    organizations,
    prompts,
    tenant_agents,
    tenant_config,
    tenant_documents,
    tenant_prompts,
)

__all__ = [
    "organizations",
    "org_users",
    "tenant_config",
    "tenant_agents",
    "tenant_prompts",
    "tenant_documents",
    "prompts",
]
