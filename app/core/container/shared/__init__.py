"""
Shared Domain Container.

Single Responsibility: Wire all shared domain dependencies.
Facade for knowledge, admin, and document containers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domains.shared.infrastructure.repositories import SQLAlchemyCustomerRepository

from .admin import AdminContainer
from .documents import DocumentsContainer
from .knowledge import KnowledgeContainer

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer


class SharedContainer:
    """
    Shared domain container (facade).

    Single Responsibility: Compose knowledge, admin, and document containers.
    """

    def __init__(self, base: "BaseContainer"):
        """
        Initialize shared container.

        Args:
            base: BaseContainer with shared singletons
        """
        self._base = base
        self._knowledge = KnowledgeContainer(base)
        self._admin = AdminContainer(base)
        self._documents = DocumentsContainer(base)

    # ==================== REPOSITORIES ====================

    def create_customer_repository(self, db) -> SQLAlchemyCustomerRepository:
        """Create Customer Repository."""
        return SQLAlchemyCustomerRepository(session=db)

    # ==================== CUSTOMER USE CASES ====================

    def create_get_or_create_customer_use_case(self, db):
        """Create GetOrCreateCustomerUseCase with dependencies."""
        from app.domains.shared.application.use_cases import (
            GetOrCreateCustomerUseCase as UseCase,
        )

        return UseCase(customer_repository=self.create_customer_repository(db))

    # ==================== KNOWLEDGE (delegated) ====================

    def create_search_knowledge_use_case(self, db):
        return self._knowledge.create_search_knowledge_use_case(db)

    def create_create_knowledge_use_case(self, db):
        return self._knowledge.create_create_knowledge_use_case(db)

    def create_get_knowledge_use_case(self, db):
        return self._knowledge.create_get_knowledge_use_case(db)

    def create_update_knowledge_use_case(self, db):
        return self._knowledge.create_update_knowledge_use_case(db)

    def create_delete_knowledge_use_case(self, db):
        return self._knowledge.create_delete_knowledge_use_case(db)

    def create_list_knowledge_use_case(self, db):
        return self._knowledge.create_list_knowledge_use_case(db)

    def create_get_knowledge_statistics_use_case(self, db):
        return self._knowledge.create_get_knowledge_statistics_use_case(db)

    def create_regenerate_knowledge_embeddings_use_case(self, db):
        return self._knowledge.create_regenerate_knowledge_embeddings_use_case(db)

    # ==================== ADMIN (delegated) ====================

    def create_list_domains_use_case(self, db):
        return self._admin.create_list_domains_use_case(db)

    def create_enable_domain_use_case(self, db):
        return self._admin.create_enable_domain_use_case(db)

    def create_disable_domain_use_case(self, db):
        return self._admin.create_disable_domain_use_case(db)

    def create_update_domain_config_use_case(self, db):
        return self._admin.create_update_domain_config_use_case(db)

    def create_get_domain_stats_use_case(self, db):
        return self._admin.create_get_domain_stats_use_case(db)

    def create_get_contact_domain_use_case(self, db):
        return self._admin.create_get_contact_domain_use_case(db)

    def create_assign_contact_domain_use_case(self, db):
        return self._admin.create_assign_contact_domain_use_case(db)

    def create_remove_contact_domain_use_case(self, db):
        return self._admin.create_remove_contact_domain_use_case(db)

    def create_clear_domain_assignments_use_case(self, db):
        return self._admin.create_clear_domain_assignments_use_case(db)

    def create_get_agent_config_use_case(self):
        return self._admin.create_get_agent_config_use_case()

    def create_update_agent_modules_use_case(self):
        return self._admin.create_update_agent_modules_use_case()

    def create_update_agent_settings_use_case(self):
        return self._admin.create_update_agent_settings_use_case()

    # ==================== DOCUMENTS (delegated) ====================

    def create_upload_pdf_use_case(self, db):
        return self._documents.create_upload_pdf_use_case(db)

    def create_upload_text_use_case(self, db):
        return self._documents.create_upload_text_use_case(db)

    def create_batch_upload_documents_use_case(self, db):
        return self._documents.create_batch_upload_documents_use_case(db)


__all__ = [
    "SharedContainer",
    "KnowledgeContainer",
    "AdminContainer",
    "DocumentsContainer",
]
