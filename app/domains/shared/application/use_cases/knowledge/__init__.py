"""
Knowledge Use Cases Module.

This module contains all use cases related to knowledge base management.
Each use case follows the Single Responsibility Principle (SRP).

Use Cases:
- SearchKnowledgeUseCase: Search knowledge base with hybrid approach
- CreateKnowledgeUseCase: Create new knowledge documents
- GetKnowledgeUseCase: Get document by ID
- UpdateKnowledgeUseCase: Update existing documents
- DeleteKnowledgeUseCase: Delete documents (soft/hard)
- ListKnowledgeUseCase: List documents with pagination
- GetKnowledgeStatisticsUseCase: Get knowledge base statistics
- RegenerateKnowledgeEmbeddingsUseCase: Regenerate vector embeddings
"""

from app.domains.shared.application.use_cases.knowledge.create_knowledge_use_case import (
    CreateKnowledgeUseCase,
)
from app.domains.shared.application.use_cases.knowledge.delete_knowledge_use_case import (
    DeleteKnowledgeUseCase,
)
from app.domains.shared.application.use_cases.knowledge.get_knowledge_use_case import (
    GetKnowledgeUseCase,
)
from app.domains.shared.application.use_cases.knowledge.get_statistics_use_case import (
    GetKnowledgeStatisticsUseCase,
)
from app.domains.shared.application.use_cases.knowledge.list_knowledge_use_case import (
    ListKnowledgeUseCase,
)
from app.domains.shared.application.use_cases.knowledge.regenerate_embeddings_use_case import (
    RegenerateKnowledgeEmbeddingsUseCase,
)
from app.domains.shared.application.use_cases.knowledge.search_knowledge_use_case import (
    SearchKnowledgeUseCase,
)
from app.domains.shared.application.use_cases.knowledge.update_knowledge_use_case import (
    UpdateKnowledgeUseCase,
)

__all__ = [
    "SearchKnowledgeUseCase",
    "CreateKnowledgeUseCase",
    "GetKnowledgeUseCase",
    "UpdateKnowledgeUseCase",
    "DeleteKnowledgeUseCase",
    "ListKnowledgeUseCase",
    "GetKnowledgeStatisticsUseCase",
    "RegenerateKnowledgeEmbeddingsUseCase",
]
