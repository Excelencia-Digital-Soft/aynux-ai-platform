"""
Knowledge Embedding Service - Embedding Generation and Synchronization (SRP)

This service handles generation and synchronization of vector embeddings for
the company knowledge base using pgvector (PostgreSQL).

Responsibilities:
- Generate embeddings using Ollama (nomic-embed-text)
- Sync embeddings to pgvector (PostgreSQL)
- Provide search interface for semantic search

Does NOT contain business logic validation (that's in Knowledge Use Cases).
"""

import logging
from typing import Any, Dict, List, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from sqlalchemy import func, select, text

from app.config.settings import get_settings
from app.database.async_db import get_async_db
from app.models.db.knowledge_base import CompanyKnowledge

logger = logging.getLogger(__name__)


class KnowledgeEmbeddingService:
    """
    Service for managing knowledge base vector embeddings using pgvector.

    Handles embedding generation and synchronization to PostgreSQL pgvector.

    Features:
    - Performance: pgvector with HNSW index for fast search
    - Native SQL integration with application data
    - Automatic embedding generation with Ollama
    """

    def __init__(self):
        """
        Initialize the embedding service.
        """
        settings = get_settings()
        self.embedding_model = settings.OLLAMA_API_MODEL_EMBEDDING
        self.embeddings = OllamaEmbeddings(
            model=settings.OLLAMA_API_MODEL_EMBEDDING, base_url=settings.OLLAMA_API_URL
        )

        # Text splitter for large documents (not typically needed for knowledge base)
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

        logger.info(f"KnowledgeEmbeddingService initialized with model={self.embedding_model} (pgvector only)")

    def _create_knowledge_content(self, knowledge: CompanyKnowledge) -> str:
        """
        Create searchable content from a CompanyKnowledge instance.

        Args:
            knowledge: CompanyKnowledge database model

        Returns:
            String content for embedding generation
        """
        # Build comprehensive document content for embedding
        title = str(knowledge.title) if knowledge.title else ""
        content = str(knowledge.content) if knowledge.content else ""

        content_parts: list[str] = [
            f"# {title}",
            "",
            content,
        ]

        if knowledge.category is not None:
            content_parts.insert(1, f"**Categoría:** {knowledge.category}")

        return "\n".join(content_parts)

    async def generate_embedding(self, text: str, max_chars: int = 6000) -> List[float]:
        """
        Generate embedding vector for a given text.

        Args:
            text: Text to generate embedding for
            max_chars: Maximum characters to use for embedding (default 6000 to fit
                      within nomic-embed-text's ~8192 token context window)

        Returns:
            List of floats representing the embedding vector (768 dimensions for nomic-embed-text)
        """
        try:
            # Truncate text if too long to avoid exceeding model's context length
            if len(text) > max_chars:
                logger.warning(
                    f"Text too long ({len(text)} chars), truncating to {max_chars} chars for embedding"
                )
                text = text[:max_chars]

            # OllamaEmbeddings.embed_query returns the embedding vector
            embedding = await self.embeddings.aembed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def update_knowledge_embeddings(
        self,
        knowledge_id: Optional[str] = None,
    ):
        """
        Update embeddings for knowledge documents in pgvector.

        Args:
            knowledge_id: If provided, update only this document. Otherwise update all.

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

                logger.info(f"Updating pgvector embeddings for {len(knowledge_docs)} knowledge documents")

                # Process each knowledge document
                for knowledge in knowledge_docs:
                    try:
                        # Create content for embedding
                        content = self._create_knowledge_content(knowledge)

                        # Generate embedding
                        embedding = await self.generate_embedding(content)

                        # Update pgvector (PostgreSQL)
                        knowledge.embedding = embedding
                        db.add(knowledge)

                        logger.info(f"Updated pgvector embedding for knowledge '{knowledge.title}'")

                    except Exception as e:
                        logger.error(f"Error updating embeddings for knowledge {knowledge.id}: {e}")
                        continue

                # Commit all pgvector updates
                await db.commit()

                logger.info("Knowledge embedding update completed successfully")

            except Exception as e:
                logger.error(f"Error updating knowledge embeddings: {e}")
                await db.rollback()
                raise

    async def search_knowledge(
        self,
        query: str,
        k: int = 5,
        document_type: Optional[str] = None,
        min_similarity: float = 0.3,
        keyword_search: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using hybrid search (vector + keyword).

        Args:
            query: Search query text
            k: Number of results to return
            document_type: If provided, search only this document type
            min_similarity: Minimum similarity score (0.0-1.0)
            keyword_search: If True, fallback to keyword search when vector results < k

        Returns:
            List of dictionaries with search results
        """
        try:
            # Generate embedding for query
            query_embedding = await self.generate_embedding(query)
            embedding_str = f"[{','.join(str(v) for v in query_embedding)}]"

            async for db in get_async_db():
                try:
                    # Build SQL query with pgvector similarity search
                    # Note: Use CAST() instead of :: to avoid asyncpg parameter confusion
                    # Use core schema explicitly for company_knowledge table
                    base_query = """
                        SELECT
                            id,
                            title,
                            content,
                            document_type,
                            category,
                            tags,
                            meta_data,
                            1 - (embedding <=> CAST(:embedding AS vector)) as similarity
                        FROM core.company_knowledge
                        WHERE active = true
                        AND embedding IS NOT NULL
                    """

                    # Add document type filter if provided
                    if document_type:
                        base_query += " AND document_type = :doc_type"

                    # Add similarity threshold and ordering
                    base_query += """
                        AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_sim
                        ORDER BY similarity DESC
                        LIMIT :limit
                    """

                    params = {
                        "embedding": embedding_str,
                        "min_sim": min_similarity,
                        "limit": k,
                    }
                    if document_type:
                        params["doc_type"] = document_type

                    result = await db.execute(text(base_query), params)
                    rows = result.fetchall()

                    # Format results
                    formatted_results: list[dict[str, Any]] = []
                    for row in rows:
                        tags_value = row.tags if row.tags else []
                        formatted_results.append(
                            {
                                "knowledge_id": str(row.id),
                                "title": row.title,
                                "document_type": row.document_type,
                                "category": row.category or "",
                                "tags": tags_value,
                                "similarity_score": float(row.similarity),
                                "content": row.content,
                                "metadata": row.meta_data or {},
                                "match_type": "vector",
                            }
                        )

                    # Hybrid search: if vector results < k, fallback to keyword search
                    if keyword_search and len(formatted_results) < k:
                        existing_ids = [r["knowledge_id"] for r in formatted_results]
                        remaining = k - len(formatted_results)

                        # Extract keywords from query (words > 3 chars)
                        keywords = [w for w in query.split() if len(w) > 3]

                        if keywords:
                            # Build ILIKE conditions for each keyword
                            keyword_conditions = " OR ".join(
                                f"(content ILIKE '%{kw}%' OR title ILIKE '%{kw}%')"
                                for kw in keywords
                            )

                            keyword_query = f"""
                                SELECT id, title, content, document_type, category, tags, meta_data
                                FROM core.company_knowledge
                                WHERE active = true
                                AND ({keyword_conditions})
                            """

                            if existing_ids:
                                ids_str = ",".join(f"'{id}'" for id in existing_ids)
                                keyword_query += f" AND id::text NOT IN ({ids_str})"

                            if document_type:
                                keyword_query += f" AND document_type = '{document_type}'"

                            keyword_query += f" LIMIT {remaining}"

                            keyword_result = await db.execute(text(keyword_query))
                            keyword_rows = keyword_result.fetchall()

                            for row in keyword_rows:
                                tags_val = row.tags if row.tags else []
                                formatted_results.append(
                                    {
                                        "knowledge_id": str(row.id),
                                        "title": row.title,
                                        "document_type": row.document_type,
                                        "category": row.category or "",
                                        "tags": tags_val,
                                        "similarity_score": 0.0,
                                        "content": row.content,
                                        "metadata": row.meta_data or {},
                                        "match_type": "keyword",
                                    }
                                )

                            if keyword_rows:
                                logger.info(
                                    f"Hybrid search added {len(keyword_rows)} keyword matches for: {keywords}"
                                )

                    return formatted_results

                except Exception as e:
                    logger.error(f"Error in pgvector search: {e}")
                    return []

        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")
            return []

        # Return empty list if async for didn't yield any db sessions
        return []

    async def get_embedding_stats(self) -> Dict[str, Any]:
        """
        Get statistics about knowledge embeddings in pgvector.

        Returns:
            Dictionary with embedding statistics
        """
        async for db in get_async_db():
            try:
                # Get total count
                total_stmt = select(func.count(CompanyKnowledge.id))
                total_result = await db.execute(total_stmt)
                total_count = total_result.scalar() or 0

                # Get count with embeddings
                embedded_stmt = select(func.count(CompanyKnowledge.id)).where(
                    CompanyKnowledge.embedding.isnot(None)
                )
                embedded_result = await db.execute(embedded_stmt)
                embedded_count = embedded_result.scalar() or 0

                # Get count by document type
                type_stmt = select(
                    CompanyKnowledge.document_type,
                    func.count(CompanyKnowledge.id).label("count"),
                ).where(CompanyKnowledge.active.is_(True)).group_by(CompanyKnowledge.document_type)
                type_result = await db.execute(type_stmt)
                type_counts = {row[0]: row[1] for row in type_result.fetchall()}

                return {
                    "total_documents": total_count,
                    "embedded_documents": embedded_count,
                    "missing_embeddings": total_count - embedded_count,
                    "embedding_coverage": (embedded_count / total_count * 100) if total_count > 0 else 0,
                    "by_document_type": type_counts,
                    "store_type": "pgvector",
                }

            except Exception as e:
                logger.error(f"Error getting embedding stats: {e}")
                return {}

        # Return empty dict if async for didn't yield any db sessions
        return {}

    async def delete_knowledge_embeddings(self, knowledge_id: str):
        """
        Clear embeddings for a knowledge document.

        Args:
            knowledge_id: ID of the knowledge document

        Note:
            This sets the embedding to NULL. Full document deletion is handled
            by the Knowledge Use Cases with database cascade.
        """
        try:
            async for db in get_async_db():
                stmt = text(
                    """
                    UPDATE core.company_knowledge
                    SET embedding = NULL, updated_at = NOW()
                    WHERE id = :knowledge_id
                    """
                )
                await db.execute(stmt, {"knowledge_id": knowledge_id})
                await db.commit()
                logger.info(f"Cleared pgvector embedding for knowledge {knowledge_id}")

        except Exception as e:
            logger.error(f"Error deleting knowledge embeddings: {e}")
            raise

    async def rebuild_all_embeddings(self):
        """
        Rebuild all embeddings from scratch in pgvector.

        This is useful for:
        - Changing embedding models
        - Recovering from data corruption
        - Initial setup
        """
        logger.info("Starting full pgvector embedding rebuild...")

        try:
            # Clear all embeddings first
            async for db in get_async_db():
                stmt = text("UPDATE core.company_knowledge SET embedding = NULL")
                await db.execute(stmt)
                await db.commit()
                logger.info("Cleared all existing embeddings")

            # Regenerate all embeddings
            await self.update_knowledge_embeddings(knowledge_id=None)

            logger.info("Full embedding rebuild completed successfully")

        except Exception as e:
            logger.error(f"Error rebuilding embeddings: {e}")
            raise
