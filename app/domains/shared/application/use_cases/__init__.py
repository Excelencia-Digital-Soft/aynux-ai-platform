"""
Shared Domain - Application Layer

Use Cases compartidos entre múltiples dominios:
- Customer management use cases
- Knowledge base use cases
- Admin and domain management use cases
"""

from app.domains.shared.application.use_cases.admin_use_cases import (
    AssignContactDomainUseCase,
    ClearDomainAssignmentsUseCase,
    DisableDomainUseCase,
    EnableDomainUseCase,
    GetContactDomainUseCase,
    GetDomainStatsUseCase,
    ListDomainsUseCase,
    RemoveContactDomainUseCase,
    UpdateDomainConfigUseCase,
)
from app.domains.shared.application.use_cases.customer_use_cases import (
    GetOrCreateCustomerUseCase,
)
from app.domains.shared.application.use_cases.knowledge_use_cases import (
    SearchKnowledgeUseCase,
)

__all__ = [
    # Customer Use Cases
    "GetOrCreateCustomerUseCase",
    # Knowledge Use Cases
    "SearchKnowledgeUseCase",
    # Admin Use Cases
    "ListDomainsUseCase",
    "EnableDomainUseCase",
    "DisableDomainUseCase",
    "UpdateDomainConfigUseCase",
    "GetContactDomainUseCase",
    "AssignContactDomainUseCase",
    "RemoveContactDomainUseCase",
    "ClearDomainAssignmentsUseCase",
    "GetDomainStatsUseCase",
]
