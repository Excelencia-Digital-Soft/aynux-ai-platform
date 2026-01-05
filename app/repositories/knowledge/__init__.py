"""
Knowledge Repository Module.

This module provides data access operations for the company_knowledge table,
split into focused repositories following Single Responsibility Principle:

- KnowledgeRepository: CRUD operations and statistics
- KnowledgeSearchRepository: Vector and text search operations

Usage:
    from app.repositories.knowledge import KnowledgeRepository, KnowledgeSearchRepository

    # For CRUD operations
    repo = KnowledgeRepository(db)
    doc = await repo.create(data)

    # For search operations
    search_repo = KnowledgeSearchRepository(db)
    results = await search_repo.search_by_vector(embedding)
"""

from ._helpers import KnowledgeFilterBuilder, KnowledgeResultFormatter
from .knowledge_repository import KnowledgeRepository
from .knowledge_search import KnowledgeSearchRepository

__all__ = [
    "KnowledgeRepository",
    "KnowledgeSearchRepository",
    "KnowledgeFilterBuilder",
    "KnowledgeResultFormatter",
]
