"""
Shared Domain Container - Knowledge Use Cases.

Single Responsibility: Wire knowledge-related use cases.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer

logger = logging.getLogger(__name__)


class KnowledgeContainer:
    """
    Knowledge use cases container.

    Single Responsibility: Create knowledge management use cases.
    """

    def __init__(self, base: "BaseContainer"):
        """
        Initialize knowledge container.

        Args:
            base: BaseContainer with shared singletons
        """
        self._base = base

    def create_search_knowledge_use_case(self, db):
        """Create SearchKnowledgeUseCase with dependencies."""
        from app.domains.shared.application.use_cases import SearchKnowledgeUseCase

        return SearchKnowledgeUseCase(db=db)

    def create_create_knowledge_use_case(self, db):
        """Create CreateKnowledgeUseCase with dependencies."""
        from app.domains.shared.application.use_cases import CreateKnowledgeUseCase

        return CreateKnowledgeUseCase(db=db)

    def create_get_knowledge_use_case(self, db):
        """Create GetKnowledgeUseCase with dependencies."""
        from app.domains.shared.application.use_cases import GetKnowledgeUseCase

        return GetKnowledgeUseCase(db=db)

    def create_update_knowledge_use_case(self, db):
        """Create UpdateKnowledgeUseCase with dependencies."""
        from app.domains.shared.application.use_cases import UpdateKnowledgeUseCase

        return UpdateKnowledgeUseCase(db=db)

    def create_delete_knowledge_use_case(self, db):
        """Create DeleteKnowledgeUseCase with dependencies."""
        from app.domains.shared.application.use_cases import DeleteKnowledgeUseCase

        return DeleteKnowledgeUseCase(db=db)

    def create_list_knowledge_use_case(self, db):
        """Create ListKnowledgeUseCase with dependencies."""
        from app.domains.shared.application.use_cases import ListKnowledgeUseCase

        return ListKnowledgeUseCase(db=db)

    def create_get_knowledge_statistics_use_case(self, db):
        """Create GetKnowledgeStatisticsUseCase with dependencies."""
        from app.domains.shared.application.use_cases import GetKnowledgeStatisticsUseCase

        return GetKnowledgeStatisticsUseCase(db=db)

    def create_regenerate_knowledge_embeddings_use_case(self, db):
        """Create RegenerateKnowledgeEmbeddingsUseCase with dependencies."""
        from app.domains.shared.application.use_cases import RegenerateKnowledgeEmbeddingsUseCase

        return RegenerateKnowledgeEmbeddingsUseCase(db=db)
