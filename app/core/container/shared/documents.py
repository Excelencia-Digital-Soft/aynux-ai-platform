"""
Shared Domain Container - Document Upload Use Cases.

Single Responsibility: Wire document upload use cases.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer

logger = logging.getLogger(__name__)


class DocumentsContainer:
    """
    Document upload use cases container.

    Single Responsibility: Create document upload use cases.
    """

    def __init__(self, base: "BaseContainer"):
        """
        Initialize documents container.

        Args:
            base: BaseContainer with shared singletons
        """
        self._base = base

    def create_upload_pdf_use_case(self, db):
        """Create UploadPDFUseCase with dependencies."""
        from app.domains.shared.application.use_cases import UploadPDFUseCase

        return UploadPDFUseCase(db=db)

    def create_upload_text_use_case(self, db):
        """Create UploadTextUseCase with dependencies."""
        from app.domains.shared.application.use_cases import UploadTextUseCase

        return UploadTextUseCase(db=db)

    def create_batch_upload_documents_use_case(self, db):
        """Create BatchUploadDocumentsUseCase with dependencies."""
        from app.domains.shared.application.use_cases import BatchUploadDocumentsUseCase

        return BatchUploadDocumentsUseCase(db=db)
