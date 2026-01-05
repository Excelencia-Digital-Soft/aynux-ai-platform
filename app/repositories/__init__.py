"""
Repositories Module

Domain-specific repositories should use:
- app.domains.ecommerce.infrastructure.repositories
- app.domains.healthcare.infrastructure.repositories
- app.domains.credit.infrastructure.repositories

Global/core repositories are defined here.
"""

from .agent_repository import AgentRepository
from .ai_model_repository import AIModelRepository
from .knowledge import KnowledgeRepository, KnowledgeSearchRepository

__all__ = [
    "AgentRepository",
    "AIModelRepository",
    "KnowledgeRepository",
    "KnowledgeSearchRepository",
]
