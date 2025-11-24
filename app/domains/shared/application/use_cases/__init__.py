"""
Shared Domain - Application Layer

Use Cases compartidos entre múltiples dominios:
- Customer management use cases
- Knowledge base use cases
"""

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
]
