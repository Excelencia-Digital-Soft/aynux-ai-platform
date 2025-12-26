"""
Shared Infrastructure Repositories

Repository implementations for the Shared domain.
"""

from app.domains.shared.infrastructure.repositories.agent_knowledge_repository import (
    AgentKnowledgeRepository,
)
from app.domains.shared.infrastructure.repositories.customer_repository import (
    SQLAlchemyCustomerRepository,
)

__all__ = ["AgentKnowledgeRepository", "SQLAlchemyCustomerRepository"]
