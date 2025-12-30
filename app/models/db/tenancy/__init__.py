# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Modelos SQLAlchemy para el sistema multi-tenant.
#              Todas las tablas aquí almacenan datos aislados por organization_id.
# Tenant-Aware: Yes - todos los modelos tienen FK a organizations.
# ============================================================================
"""
Multi-tenant models for Aynux platform.

This package contains all models related to multi-tenancy support:
- Organization: Tenant/company entity
- OrganizationUser: User membership in organizations
- TenantConfig: Per-tenant configuration
- TenantAgent: Per-tenant agent configuration
- TenantPrompt: Per-tenant prompt overrides
- TenantDocument: Per-tenant knowledge base documents with vector embeddings
"""

from .bypass_rule import BypassRule
from .chattigo_credentials import ChattigoCredentials
from .organization import Organization
from .organization_user import OrganizationUser
from .pharmacy_merchant_config import PharmacyMerchantConfig
from .tenant_agent import TenantAgent
from .tenant_config import TenantConfig
from .tenant_credentials import TenantCredentials
from .tenant_document import TenantDocument
from .tenant_prompt import TenantPrompt

__all__ = [
    "BypassRule",
    "ChattigoCredentials",
    "Organization",
    "OrganizationUser",
    "PharmacyMerchantConfig",
    "TenantConfig",
    "TenantCredentials",
    "TenantAgent",
    "TenantPrompt",
    "TenantDocument",
]
