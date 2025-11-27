"""
Admin Use Cases Module.

This module contains use cases for system administration and domain management.

Domain Management:
- ListDomainsUseCase: List all available domains
- EnableDomainUseCase: Enable a specific domain
- DisableDomainUseCase: Disable a specific domain
- UpdateDomainConfigUseCase: Update domain configuration
- GetDomainStatsUseCase: Get domain system statistics

Contact Domain Assignment:
- GetContactDomainUseCase: Get domain assignment for a contact
- AssignContactDomainUseCase: Assign a domain to a contact
- RemoveContactDomainUseCase: Remove domain assignment
- ClearDomainAssignmentsUseCase: Clear domain assignments
"""

from app.domains.shared.application.use_cases.admin.contact_domain_use_cases import (
    AssignContactDomainUseCase,
    ClearDomainAssignmentsUseCase,
    GetContactDomainUseCase,
    RemoveContactDomainUseCase,
)
from app.domains.shared.application.use_cases.admin.domain_management_use_cases import (
    DisableDomainUseCase,
    EnableDomainUseCase,
    GetDomainStatsUseCase,
    ListDomainsUseCase,
    UpdateDomainConfigUseCase,
)

__all__ = [
    # Domain Management
    "ListDomainsUseCase",
    "EnableDomainUseCase",
    "DisableDomainUseCase",
    "UpdateDomainConfigUseCase",
    "GetDomainStatsUseCase",
    # Contact Domain Assignment
    "GetContactDomainUseCase",
    "AssignContactDomainUseCase",
    "RemoveContactDomainUseCase",
    "ClearDomainAssignmentsUseCase",
]
