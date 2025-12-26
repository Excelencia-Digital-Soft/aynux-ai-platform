"""
Agent Knowledge Use Cases

Use cases for managing agent-specific knowledge bases with RAG capabilities.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.shared.infrastructure.repositories.agent_knowledge_repository import (
    AgentKnowledgeRepository,
)
from app.integrations.document_processing import DocumentExtractor
from app.integrations.vector_stores.knowledge_embedding_service import (
    KnowledgeEmbeddingService,
)

logger = logging.getLogger(__name__)


class SearchAgentKnowledgeUseCase:
    """
    Use Case: Search Agent Knowledge Base

    Searches the knowledge base for a specific agent using semantic similarity.

    Responsibilities:
    - Generate query embedding
    - Perform semantic search
    - Format results for agent prompt injection
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        """
        Initialize search use case.

        Args:
            db: Database session
            embedding_service: Service for generating embeddings
        """
        self.db = db
        self.repository = AgentKnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(
        self,
        agent_key: str,
        query: str,
        max_results: int = 3,
        min_similarity: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Search agent knowledge base semantically.

        Args:
            agent_key: Agent identifier
            query: Search query text
            max_results: Maximum results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of relevant documents with similarity scores
        """
        try:
            # Check if agent has any documents
            count = await self.repository.count_by_agent(agent_key)
            if count == 0:
                logger.debug(f"No documents found for agent: {agent_key}")
                return []

            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)

            if not query_embedding:
                logger.warning(f"Failed to generate embedding for query: {query[:50]}")
                # Fall back to full-text search
                return await self.repository.search_fulltext(
                    agent_key=agent_key,
                    query=query,
                    max_results=max_results,
                )

            # Perform semantic search
            results = await self.repository.search_semantic(
                agent_key=agent_key,
                query_embedding=query_embedding,
                max_results=max_results,
                min_similarity=min_similarity,
            )

            logger.info(
                f"Found {len(results)} documents for agent {agent_key} "
                f"(query: {query[:30]}...)"
            )

            return results

        except Exception as e:
            logger.error(f"Error searching agent knowledge: {e}")
            return []

    async def format_as_context(
        self,
        results: list[dict[str, Any]],
        max_content_length: int = 800,
    ) -> str:
        """
        Format search results as context for agent prompt.

        Args:
            results: Search results from execute()
            max_content_length: Max chars per document

        Returns:
            Formatted context string for prompt injection
        """
        if not results:
            return ""

        parts = ["## Contexto Relevante (Knowledge Base):"]

        for i, result in enumerate(results, 1):
            title = result.get("title", "Documento")
            content = result.get("content", "")[:max_content_length]
            score = result.get("similarity_score", 0)

            parts.append(f"\n### {i}. {title} (relevancia: {score:.0%})")
            parts.append(content)

        return "\n".join(parts)


class UploadAgentDocumentUseCase:
    """
    Use Case: Upload Document to Agent Knowledge Base

    Handles uploading documents (PDF, DOCX, TXT, MD) to an agent's knowledge base.

    Responsibilities:
    - Extract text from document
    - Generate embedding
    - Store in agent knowledge base
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: KnowledgeEmbeddingService | None = None,
        document_extractor: DocumentExtractor | None = None,
    ):
        """
        Initialize upload use case.

        Args:
            db: Database session
            embedding_service: Service for generating embeddings
            document_extractor: Service for extracting text from documents
        """
        self.db = db
        self.repository = AgentKnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()
        self.document_extractor = document_extractor or DocumentExtractor()

    async def execute(
        self,
        agent_key: str,
        file_bytes: bytes,
        filename: str,
        title: str | None = None,
        document_type: str = "general",
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Upload document to agent knowledge base.

        Args:
            agent_key: Agent identifier
            file_bytes: Document file content as bytes
            filename: Original filename (used to detect format)
            title: Optional document title (defaults to filename)
            document_type: Type of document
            category: Optional category
            tags: Optional tags

        Returns:
            Created document dictionary

        Raises:
            ValueError: If extraction or embedding fails
        """
        try:
            # 1. Validate file format
            if not self.document_extractor.is_supported(filename):
                supported = ", ".join(self.document_extractor.get_supported_extensions())
                raise ValueError(
                    f"Unsupported file format. Supported: {supported}"
                )

            # 2. Extract text from document
            logger.info(f"Extracting text from {filename}...")
            extraction = self.document_extractor.extract(file_bytes, filename)

            content = extraction.get("text", "")
            if not content or len(content.strip()) < 50:
                raise ValueError(
                    f"Document extraction resulted in insufficient content "
                    f"(minimum 50 characters required, got {len(content)})"
                )

            # 3. Prepare document data
            doc_title = title or filename.rsplit(".", 1)[0]  # Remove extension
            meta_data = {
                "source_filename": filename,
                "format": extraction.get("format", "unknown"),
            }

            if extraction.get("page_count"):
                meta_data["page_count"] = extraction["page_count"]
            if extraction.get("metadata"):
                meta_data["original_metadata"] = extraction["metadata"]

            # 4. Generate embedding
            logger.info(f"Generating embedding for {doc_title}...")
            embedding = await self.embedding_service.generate_embedding(content)

            # 5. Store document
            logger.info(f"Storing document: {doc_title} for agent {agent_key}")
            result = await self.repository.create(
                agent_key=agent_key,
                title=doc_title,
                content=content,
                document_type=document_type,
                category=category,
                tags=tags,
                meta_data=meta_data,
                embedding=embedding,
            )

            logger.info(
                f"Successfully uploaded {filename} to agent {agent_key} "
                f"({len(content)} chars)"
            )

            return result

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            raise ValueError(f"Failed to upload document: {str(e)}") from e


class CreateAgentKnowledgeUseCase:
    """
    Use Case: Create Agent Knowledge Document from Text

    Creates a knowledge document directly from text content.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        self.db = db
        self.repository = AgentKnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(
        self,
        agent_key: str,
        title: str,
        content: str,
        document_type: str = "general",
        category: str | None = None,
        tags: list[str] | None = None,
        auto_embed: bool = True,
    ) -> dict[str, Any]:
        """
        Create knowledge document from text.

        Args:
            agent_key: Agent identifier
            title: Document title
            content: Document content
            document_type: Type of document
            category: Optional category
            tags: Optional tags
            auto_embed: Whether to generate embedding automatically

        Returns:
            Created document dictionary
        """
        try:
            # Validate inputs
            if not title or len(title.strip()) < 3:
                raise ValueError("Title must be at least 3 characters")

            if not content or len(content.strip()) < 50:
                raise ValueError(
                    f"Content must be at least 50 characters "
                    f"(got {len(content.strip())})"
                )

            # Generate embedding if requested
            embedding = None
            if auto_embed:
                logger.info(f"Generating embedding for {title}...")
                embedding = await self.embedding_service.generate_embedding(content)

            # Create document
            result = await self.repository.create(
                agent_key=agent_key,
                title=title.strip(),
                content=content.strip(),
                document_type=document_type,
                category=category,
                tags=tags,
                meta_data={"source": "text_upload"},
                embedding=embedding,
            )

            logger.info(f"Created knowledge document: {title} for agent {agent_key}")
            return result

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating knowledge document: {e}")
            raise ValueError(f"Failed to create document: {str(e)}") from e


class ListAgentKnowledgeUseCase:
    """
    Use Case: List Agent Knowledge Documents
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AgentKnowledgeRepository(db)

    async def execute(
        self,
        agent_key: str,
        active_only: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all knowledge documents for an agent.

        Args:
            agent_key: Agent identifier
            active_only: Only return active documents
            limit: Maximum number of documents

        Returns:
            List of document dictionaries
        """
        return await self.repository.get_by_agent(
            agent_key=agent_key,
            active_only=active_only,
            limit=limit,
        )


class DeleteAgentKnowledgeUseCase:
    """
    Use Case: Delete Agent Knowledge Document
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AgentKnowledgeRepository(db)

    async def execute(
        self,
        doc_id: str,
        hard_delete: bool = False,
    ) -> bool:
        """
        Delete a knowledge document.

        Args:
            doc_id: Document UUID
            hard_delete: If True, permanently delete. If False, soft delete.

        Returns:
            True if deleted, False if not found
        """
        return await self.repository.delete(doc_id, hard=hard_delete)


class GetAgentKnowledgeStatsUseCase:
    """
    Use Case: Get Agent Knowledge Statistics
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AgentKnowledgeRepository(db)

    async def execute(self, agent_key: str) -> dict[str, Any]:
        """
        Get statistics for an agent's knowledge base.

        Args:
            agent_key: Agent identifier

        Returns:
            Statistics dictionary
        """
        return await self.repository.get_stats(agent_key)


class RegenerateAgentKnowledgeEmbeddingUseCase:
    """
    Use Case: Regenerate Embedding for Agent Knowledge Document
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        self.db = db
        self.repository = AgentKnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(self, doc_id: str) -> bool:
        """
        Regenerate embedding for a document.

        Args:
            doc_id: Document UUID

        Returns:
            True if successful, False if document not found
        """
        try:
            # Get document
            doc = await self.repository.get_by_id(doc_id)
            if not doc:
                return False

            # Generate new embedding
            content = doc.get("content", "")
            embedding = await self.embedding_service.generate_embedding(content)

            if not embedding:
                logger.warning(f"Failed to generate embedding for doc {doc_id}")
                return False

            # Update document
            return await self.repository.update_embedding(doc_id, embedding)

        except Exception as e:
            logger.error(f"Error regenerating embedding: {e}")
            return False


__all__ = [
    "SearchAgentKnowledgeUseCase",
    "UploadAgentDocumentUseCase",
    "CreateAgentKnowledgeUseCase",
    "ListAgentKnowledgeUseCase",
    "DeleteAgentKnowledgeUseCase",
    "GetAgentKnowledgeStatsUseCase",
    "RegenerateAgentKnowledgeEmbeddingUseCase",
]
