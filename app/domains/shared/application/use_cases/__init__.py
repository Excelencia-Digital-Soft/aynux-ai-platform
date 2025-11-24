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
    CreateKnowledgeUseCase,
    DeleteKnowledgeUseCase,
    GetKnowledgeStatisticsUseCase,
    GetKnowledgeUseCase,
    ListKnowledgeUseCase,
    RegenerateKnowledgeEmbeddingsUseCase,
    SearchKnowledgeUseCase,
    UpdateKnowledgeUseCase,
)
from app.domains.shared.application.use_cases.upload_document_use_case import (
    UploadPDFUseCase,
    UploadTextUseCase,
    BatchUploadDocumentsUseCase,
)
from app.domains.shared.application.use_cases.agent_config_use_case import (
    GetAgentConfigUseCase,
    UpdateAgentModulesUseCase,
    UpdateAgentSettingsUseCase,
)

__all__ = [
    # Customer Use Cases
    "GetOrCreateCustomerUseCase",
    # Knowledge Use Cases
    "SearchKnowledgeUseCase",
    "CreateKnowledgeUseCase",
    "GetKnowledgeUseCase",
    "UpdateKnowledgeUseCase",
    "DeleteKnowledgeUseCase",
    "ListKnowledgeUseCase",
    "GetKnowledgeStatisticsUseCase",
    "RegenerateKnowledgeEmbeddingsUseCase",
    # Document Upload Use Cases
    "UploadPDFUseCase",
    "UploadTextUseCase",
    "BatchUploadDocumentsUseCase",
    # Agent Configuration Use Cases
    "GetAgentConfigUseCase",
    "UpdateAgentModulesUseCase",
    "UpdateAgentSettingsUseCase",
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
