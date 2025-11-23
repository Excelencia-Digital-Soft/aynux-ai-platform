"""
Knowledge Embedding Service - Embedding Generation and Synchronization (SRP)

This service handles generation and synchronization of vector embeddings for
the company knowledge base. It supports both pgvector (PostgreSQL) and
ChromaDB for hybrid search capabilities.

Responsibilities:
- Generate embeddings using Ollama (nomic-embed-text)
- Sync embeddings to pgvector (PostgreSQL)
- Sync embeddings to ChromaDB collections
- Maintain embedding consistency across both stores
- Provide search interfaces for both vector stores

Does NOT contain business logic validation (that's in KnowledgeService).
"""

import logging
import os
from typing import Any, Dict, List, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from sqlalchemy import select

from app.database.async_db import get_async_db
from app.models.db.knowledge_base import CompanyKnowledge

logger = logging.getLogger(__name__)


class KnowledgeEmbeddingService:
    """
    Service for managing knowledge base vector embeddings.

    Handles embedding generation and synchronization to both:
    - pgvector (PostgreSQL native vector search)
    - ChromaDB (document-based vector store)

    This hybrid approach provides:
    - Performance: pgvector with HNSW index for fast search
    - Flexibility: ChromaDB for document-based operations
    - Redundancy: Fallback if one system fails
    """

    def __init__(self, embedding_model: str = "nomic-embed-text", ollama_base_url: str = "http://localhost:11434"):
        """
        Initialize the embedding service.

        Args:
            embedding_model: Name of the Ollama embedding model
            ollama_base_url: Base URL for Ollama API
        """
        self.embedding_model = embedding_model
        self.embeddings = OllamaEmbeddings(model=embedding_model, base_url=ollama_base_url)

        # Text splitter for large documents (not typically needed for knowledge base)
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

        # ChromaDB setup
        self.chroma_path = "data/chroma/knowledge"
        os.makedirs(self.chroma_path, exist_ok=True)

        # Initialize ChromaDB collections by document type
        self.chroma_collections = {}
        self._initialize_chroma_collections()

        logger.info(
            f"KnowledgeEmbeddingService initialized with model={embedding_model}, chroma_path={self.chroma_path}"
        )

    def _initialize_chroma_collections(self):
        """Initialize ChromaDB collections for each document type."""
        # Create collections for each document type
        document_types = [
            "mission_vision",
            "contact_info",
            "software_catalog",
            "faq",
            "clients",
            "success_stories",
            "general",
            "all_knowledge",  # Collection for all documents
        ]

        for doc_type in document_types:
            collection_path = os.path.join(self.chroma_path, doc_type)
            os.makedirs(collection_path, exist_ok=True)

            self.chroma_collections[doc_type] = Chroma(
                collection_name=f"knowledge_{doc_type}",
                embedding_function=self.embeddings,
                persist_directory=collection_path,
            )

        logger.info(f"Initialized {len(self.chroma_collections)} ChromaDB collections")

    def _create_knowledge_document(self, knowledge: CompanyKnowledge) -> Document:
        """
        Create a LangChain Document from a CompanyKnowledge instance.

        Args:
            knowledge: CompanyKnowledge database model

        Returns:
            LangChain Document with content and metadata
        """
        # Build comprehensive document content
        content_parts = [
            f"# {knowledge.title}",
            "",
            knowledge.content,
        ]

        if knowledge.category is not None:
            content_parts.insert(1, f"**Categoría:** {knowledge.category}")

        content = "\n".join(content_parts)

        # Create metadata (ChromaDB only accepts str, int, float, bool)
        # Convert arrays to comma-separated strings
        tags_value = ""
        if knowledge.tags is not None and len(knowledge.tags) > 0:
            tags_value = ",".join(knowledge.tags)

        metadata = {
            "knowledge_id": str(knowledge.id),
            "title": knowledge.title,
            "document_type": knowledge.document_type,
            "category": knowledge.category or "",
            "tags": tags_value,
            "active": knowledge.active,
            "sort_order": knowledge.sort_order,
            "updated_at": knowledge.updated_at.isoformat(),
        }

        # Add custom metadata (only simple types)
        if knowledge.meta_data is not None:
            for key, value in knowledge.meta_data.items():
                if isinstance(value, (str, int, float, bool)):
                    metadata[key] = value

        return Document(page_content=content, metadata=metadata)

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for a given text.

        Args:
            text: Text to generate embedding for

        Returns:
            List of floats representing the embedding vector (1024 dimensions)
        """
        try:
            # OllamaEmbeddings.embed_query returns the embedding vector
            embedding = await self.embeddings.aembed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def update_knowledge_embeddings(
        self,
        knowledge_id: Optional[str] = None,
        update_pgvector: bool = True,
        update_chroma: bool = True,
    ):
        """
        Update embeddings for knowledge documents.

        Args:
            knowledge_id: If provided, update only this document. Otherwise update all.
            update_pgvector: Whether to update pgvector embeddings
            update_chroma: Whether to update ChromaDB embeddings

        Raises:
            Exception: If embedding generation or update fails
        """
        async for db in get_async_db():
            try:
                # Build query
                stmt = select(CompanyKnowledge).where(CompanyKnowledge.active.is_(True))

                if knowledge_id:
                    stmt = stmt.where(CompanyKnowledge.id == knowledge_id)

                result = await db.execute(stmt)
                knowledge_docs = result.scalars().all()

                logger.info(f"Updating embeddings for {len(knowledge_docs)} knowledge documents")

                # Process each knowledge document
                for knowledge in knowledge_docs:
                    try:
                        # Create document for embedding
                        doc = self._create_knowledge_document(knowledge)

                        # Generate embedding
                        embedding = await self.generate_embedding(doc.page_content)

                        # Update pgvector (PostgreSQL)
                        if update_pgvector:
                            knowledge.embedding = embedding  # type: ignore[assignment]
                            db.add(knowledge)

                        # Update ChromaDB
                        if update_chroma:
                            # Delete existing embeddings for this document
                            for collection in self.chroma_collections.values():
                                try:
                                    collection.delete(where={"knowledge_id": str(knowledge.id)})
                                except Exception as e:
                                    # Collection might not have this document, which is fine
                                    logger.debug(f"Could not delete from collection: {e}")

                            # Add to type-specific collection
                            doc_type = knowledge.document_type
                            if doc_type in self.chroma_collections:
                                self.chroma_collections[doc_type].add_documents([doc])

                            # Also add to all_knowledge collection
                            self.chroma_collections["all_knowledge"].add_documents([doc])

                        logger.info(
                            f"Updated embeddings for knowledge '{knowledge.title}' "
                            f"(pgvector={update_pgvector}, chroma={update_chroma})"
                        )

                    except Exception as e:
                        logger.error(f"Error updating embeddings for knowledge {knowledge.id}: {e}")
                        continue

                # Commit all pgvector updates
                if update_pgvector:
                    await db.commit()

                logger.info("Knowledge embedding update completed successfully")

            except Exception as e:
                logger.error(f"Error updating knowledge embeddings: {e}")
                await db.rollback()
                raise

    async def search_knowledge_chroma(
        self,
        query: str,
        k: int = 5,
        document_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using ChromaDB.

        Args:
            query: Search query text
            k: Number of results to return
            document_type: If provided, search only this document type

        Returns:
            List of dictionaries with search results
        """
        try:
            # Determine which collection to search
            if document_type and document_type in self.chroma_collections:
                collection = self.chroma_collections[document_type]
            else:
                collection = self.chroma_collections["all_knowledge"]

            # Perform similarity search
            results = collection.similarity_search_with_score(query, k=k)

            # Format results
            formatted_results = []
            for doc, score in results:
                formatted_results.append(
                    {
                        "knowledge_id": doc.metadata.get("knowledge_id"),
                        "title": doc.metadata.get("title"),
                        "document_type": doc.metadata.get("document_type"),
                        "category": doc.metadata.get("category"),
                        "tags": doc.metadata.get("tags", []),
                        "similarity_score": float(score),
                        "content": doc.page_content,
                        "metadata": {
                            k: v
                            for k, v in doc.metadata.items()
                            if k not in ["knowledge_id", "title", "document_type", "category", "tags"]
                        },
                    }
                )

            return formatted_results

        except Exception as e:
            logger.error(f"Error searching ChromaDB: {e}")
            return []

    def get_chroma_collection_stats(self) -> Dict[str, int]:
        """
        Get statistics about ChromaDB collections.

        Returns:
            Dictionary with collection names and document counts
        """
        stats = {}
        for collection_name, collection in self.chroma_collections.items():
            try:
                # Get collection info
                chroma_collection = collection._collection
                count = chroma_collection.count()
                stats[collection_name] = count
            except Exception as e:
                logger.error(f"Error getting stats for collection {collection_name}: {e}")
                stats[collection_name] = 0

        return stats

    async def delete_knowledge_embeddings(self, knowledge_id: str, delete_from_chroma: bool = True):
        """
        Delete embeddings for a knowledge document.

        Args:
            knowledge_id: ID of the knowledge document
            delete_from_chroma: Whether to delete from ChromaDB as well

        Note:
            pgvector embeddings are deleted automatically when the document is deleted
            due to database cascade. This method is mainly for ChromaDB cleanup.
        """
        try:
            if delete_from_chroma:
                # Delete from all ChromaDB collections
                for collection in self.chroma_collections.values():
                    try:
                        collection.delete(where={"knowledge_id": knowledge_id})
                    except Exception as e:
                        logger.debug(f"Could not delete knowledge {knowledge_id} from collection: {e}")

                logger.info(f"Deleted ChromaDB embeddings for knowledge {knowledge_id}")

        except Exception as e:
            logger.error(f"Error deleting knowledge embeddings: {e}")
            raise

    async def rebuild_all_embeddings(self, update_pgvector: bool = True, update_chroma: bool = True):
        """
        Rebuild all embeddings from scratch.

        This is useful for:
        - Changing embedding models
        - Recovering from data corruption
        - Initial setup

        Args:
            update_pgvector: Whether to update pgvector embeddings
            update_chroma: Whether to update ChromaDB embeddings
        """
        logger.info("Starting full embedding rebuild...")

        try:
            # Clear all ChromaDB collections if updating
            if update_chroma:
                for collection in self.chroma_collections.values():
                    try:
                        collection.delete(where={})  # Delete all
                    except Exception as e:
                        logger.warning(f"Could not clear collection: {e}")

            # Update all embeddings
            await self.update_knowledge_embeddings(
                knowledge_id=None,
                update_pgvector=update_pgvector,
                update_chroma=update_chroma,
            )

            logger.info("Full embedding rebuild completed successfully")

        except Exception as e:
            logger.error(f"Error rebuilding embeddings: {e}")
            raise
