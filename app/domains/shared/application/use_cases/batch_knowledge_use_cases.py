"""
Batch Knowledge Use Cases

Use cases for batch operations on knowledge documents.
Supports operations on company_knowledge, agent_knowledge, and tenant_documents.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.document_processing import DocumentExtractor
from app.integrations.vector_stores.knowledge_embedding_service import (
    KnowledgeEmbeddingService,
)
from app.models.db.agent_knowledge import AgentKnowledge
from app.models.db.knowledge_base import CompanyKnowledge

logger = logging.getLogger(__name__)


@dataclass
class BatchOperationResult:
    """Result of a batch operation."""

    success_count: int = 0
    error_count: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    processed_ids: list[str] = field(default_factory=list)


class BatchUpdateDocumentsUseCase:
    """
    Use Case: Batch Update Documents

    Updates multiple documents with the same change.
    Supports: document_type, category, tags (add/remove), active status.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize batch update use case.

        Args:
            db: Database session
        """
        self.db = db

    async def execute(
        self,
        doc_ids: list[str],
        update_data: dict[str, Any],
        table: Literal["company_knowledge", "agent_knowledge"] = "company_knowledge",
    ) -> BatchOperationResult:
        """
        Update multiple documents.

        Args:
            doc_ids: List of document UUIDs
            update_data: Fields to update. Supports:
                - document_type: str
                - category: str | None
                - active: bool
                - add_tags: list[str] (tags to add)
                - remove_tags: list[str] (tags to remove)
            table: Target table

        Returns:
            BatchOperationResult with success/error counts
        """
        result = BatchOperationResult()

        if not doc_ids:
            return result

        # Select model class
        model_class = CompanyKnowledge if table == "company_knowledge" else AgentKnowledge

        for doc_id in doc_ids:
            try:
                # Get document
                stmt = select(model_class).where(model_class.id == doc_id)
                db_result = await self.db.execute(stmt)
                doc = db_result.scalar_one_or_none()

                if not doc:
                    result.error_count += 1
                    result.errors.append((doc_id, "Document not found"))
                    continue

                # Apply updates
                if "document_type" in update_data:
                    doc.document_type = update_data["document_type"]

                if "category" in update_data:
                    doc.category = update_data["category"]

                if "active" in update_data:
                    doc.active = update_data["active"]

                if "add_tags" in update_data:
                    current_tags = set(doc.tags or [])
                    new_tags = set(update_data["add_tags"])
                    doc.tags = list(current_tags | new_tags)

                if "remove_tags" in update_data:
                    current_tags = set(doc.tags or [])
                    tags_to_remove = set(update_data["remove_tags"])
                    doc.tags = list(current_tags - tags_to_remove)

                result.success_count += 1
                result.processed_ids.append(doc_id)

            except Exception as e:
                result.error_count += 1
                result.errors.append((doc_id, str(e)))
                logger.error(f"Error updating document {doc_id}: {e}")

        # Commit all changes
        try:
            await self.db.commit()
            logger.info(f"Batch update completed: {result.success_count} success, {result.error_count} errors")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Batch update commit failed: {e}")
            # Mark all as failed
            result.errors = [(doc_id, str(e)) for doc_id in doc_ids]
            result.error_count = len(doc_ids)
            result.success_count = 0

        return result


class BatchDeleteDocumentsUseCase:
    """
    Use Case: Batch Delete Documents

    Deletes multiple documents (soft or hard delete).
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize batch delete use case.

        Args:
            db: Database session
        """
        self.db = db

    async def execute(
        self,
        doc_ids: list[str],
        hard_delete: bool = False,
        table: Literal["company_knowledge", "agent_knowledge"] = "company_knowledge",
    ) -> BatchOperationResult:
        """
        Delete multiple documents.

        Args:
            doc_ids: List of document UUIDs
            hard_delete: If True, permanently delete. If False, soft delete.
            table: Target table

        Returns:
            BatchOperationResult with success/error counts
        """
        result = BatchOperationResult()

        if not doc_ids:
            return result

        model_class = CompanyKnowledge if table == "company_knowledge" else AgentKnowledge

        for doc_id in doc_ids:
            try:
                stmt = select(model_class).where(model_class.id == doc_id)
                db_result = await self.db.execute(stmt)
                doc = db_result.scalar_one_or_none()

                if not doc:
                    result.error_count += 1
                    result.errors.append((doc_id, "Document not found"))
                    continue

                if hard_delete:
                    await self.db.delete(doc)
                else:
                    doc.active = False

                result.success_count += 1
                result.processed_ids.append(doc_id)

            except Exception as e:
                result.error_count += 1
                result.errors.append((doc_id, str(e)))
                logger.error(f"Error deleting document {doc_id}: {e}")

        try:
            await self.db.commit()
            delete_type = "hard" if hard_delete else "soft"
            logger.info(
                f"Batch {delete_type} delete completed: {result.success_count} success, {result.error_count} errors"
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Batch delete commit failed: {e}")
            result.errors = [(doc_id, str(e)) for doc_id in doc_ids]
            result.error_count = len(doc_ids)
            result.success_count = 0

        return result


class BatchRegenerateEmbeddingsUseCase:
    """
    Use Case: Batch Regenerate Embeddings

    Regenerates embeddings for multiple documents.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        """
        Initialize batch embedding regeneration use case.

        Args:
            db: Database session
            embedding_service: Service for generating embeddings
        """
        self.db = db
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(
        self,
        doc_ids: list[str],
        table: Literal["company_knowledge", "agent_knowledge"] = "company_knowledge",
    ) -> BatchOperationResult:
        """
        Regenerate embeddings for multiple documents.

        Args:
            doc_ids: List of document UUIDs
            table: Target table

        Returns:
            BatchOperationResult with success/error counts
        """
        result = BatchOperationResult()

        if not doc_ids:
            return result

        model_class = CompanyKnowledge if table == "company_knowledge" else AgentKnowledge

        for doc_id in doc_ids:
            try:
                stmt = select(model_class).where(model_class.id == doc_id)
                db_result = await self.db.execute(stmt)
                doc = db_result.scalar_one_or_none()

                if not doc:
                    result.error_count += 1
                    result.errors.append((doc_id, "Document not found"))
                    continue

                # Generate new embedding
                content = doc.content or ""
                if len(content.strip()) < 50:
                    result.error_count += 1
                    result.errors.append((doc_id, "Content too short for embedding"))
                    continue

                embedding = await self.embedding_service.generate_embedding(content)

                if not embedding:
                    result.error_count += 1
                    result.errors.append((doc_id, "Failed to generate embedding"))
                    continue

                doc.embedding = embedding
                result.success_count += 1
                result.processed_ids.append(doc_id)

                logger.debug(f"Regenerated embedding for {doc_id}")

            except Exception as e:
                result.error_count += 1
                result.errors.append((doc_id, str(e)))
                logger.error(f"Error regenerating embedding for {doc_id}: {e}")

        try:
            await self.db.commit()
            logger.info(
                f"Batch embedding regeneration completed: {result.success_count} success, {result.error_count} errors"
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Batch embedding commit failed: {e}")
            result.errors = [(doc_id, str(e)) for doc_id in doc_ids]
            result.error_count = len(doc_ids)
            result.success_count = 0

        return result


class BatchUploadDocumentsUseCase:
    """
    Use Case: Batch Upload Documents

    Uploads multiple documents from files.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: KnowledgeEmbeddingService | None = None,
        document_extractor: DocumentExtractor | None = None,
    ):
        """
        Initialize batch upload use case.

        Args:
            db: Database session
            embedding_service: Service for generating embeddings
            document_extractor: Service for extracting text from documents
        """
        self.db = db
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()
        self.document_extractor = document_extractor or DocumentExtractor()

    async def execute(
        self,
        files: list[tuple[bytes, str, dict[str, Any]]],
        table: Literal["company_knowledge", "agent_knowledge"] = "company_knowledge",
        agent_key: str | None = None,
    ) -> BatchOperationResult:
        """
        Upload multiple documents.

        Args:
            files: List of (file_bytes, filename, metadata) tuples.
                metadata should include: title, document_type, category, tags
            table: Target table
            agent_key: Required if table is agent_knowledge

        Returns:
            BatchOperationResult with success/error counts
        """
        result = BatchOperationResult()

        if not files:
            return result

        model_class = CompanyKnowledge if table == "company_knowledge" else AgentKnowledge

        for file_bytes, filename, metadata in files:
            try:
                # Validate file format
                if not self.document_extractor.is_supported(filename):
                    result.error_count += 1
                    result.errors.append((filename, "Unsupported file format"))
                    continue

                # Extract text
                extraction = self.document_extractor.extract(file_bytes, filename)
                content = extraction.get("text", "")

                if len(content.strip()) < 50:
                    result.error_count += 1
                    result.errors.append((filename, f"Content too short ({len(content)} chars)"))
                    continue

                # Generate embedding
                embedding = await self.embedding_service.generate_embedding(content)

                # Prepare document data
                title = metadata.get("title") or filename.rsplit(".", 1)[0]
                doc_data = {
                    "title": title,
                    "content": content,
                    "document_type": metadata.get("document_type", "general"),
                    "category": metadata.get("category"),
                    "tags": metadata.get("tags", []),
                    "meta_data": {
                        "source_filename": filename,
                        "format": extraction.get("format", "unknown"),
                        "page_count": extraction.get("page_count"),
                    },
                    "embedding": embedding,
                    "active": True,
                }

                if table == "agent_knowledge" and agent_key:
                    doc_data["agent_key"] = agent_key

                # Create document
                doc = model_class(**doc_data)
                self.db.add(doc)

                result.success_count += 1
                result.processed_ids.append(title)

                logger.debug(f"Uploaded document: {title}")

            except Exception as e:
                result.error_count += 1
                result.errors.append((filename, str(e)))
                logger.error(f"Error uploading {filename}: {e}")

        try:
            await self.db.commit()
            logger.info(f"Batch upload completed: {result.success_count} success, {result.error_count} errors")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Batch upload commit failed: {e}")
            result.errors = [(f[1], str(e)) for f in files]
            result.error_count = len(files)
            result.success_count = 0

        return result


__all__ = [
    "BatchOperationResult",
    "BatchUpdateDocumentsUseCase",
    "BatchDeleteDocumentsUseCase",
    "BatchRegenerateEmbeddingsUseCase",
    "BatchUploadDocumentsUseCase",
]
