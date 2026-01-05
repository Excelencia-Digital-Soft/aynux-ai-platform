"""
Knowledge base search service for support.

Searches multiple knowledge sources:
1. Agent-specific knowledge (agent_knowledge table)
2. Company knowledge (company_knowledge table) - includes software modules
3. Software modules (excelencia.software_modules table) - ERP catalog

Uses hybrid search (vector + keyword) for better recall.
Returns SearchResult with context and metrics for logging by the calling agent.
"""

import logging
import time
from typing import Any

from sqlalchemy import text

from app.config.settings import get_settings
from app.database.async_db import get_async_db_context
from app.domains.shared.application.use_cases.agent_knowledge_use_cases import (
    SearchAgentKnowledgeUseCase,
)
from app.integrations.vector_stores.knowledge_embedding_service import (
    KnowledgeEmbeddingService,
)

from .rag_logger import SearchMetrics, SearchResult

logger = logging.getLogger(__name__)
settings = get_settings()

# Default agent key for Excelencia support
# Uses "support_agent" to match existing data in agent_knowledge table
DEFAULT_AGENT_KEY = "support_agent"


class KnowledgeBaseSearch:
    """Search agent-specific knowledge base for support information."""

    def __init__(self, agent_key: str = DEFAULT_AGENT_KEY, max_results: int = 3):
        """Initialize with agent key and max results.

        Args:
            agent_key: The agent identifier to search knowledge for
            max_results: Maximum number of results to return
        """
        self._agent_key = agent_key
        self._max_results = max_results
        self._enabled = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)

    async def search(self, query: str, query_type: str) -> SearchResult:
        """
        Search multiple knowledge sources for support information.

        Searches in order:
        1. Agent-specific knowledge (agent_knowledge table)
        2. Company knowledge (company_knowledge table) - for software modules
        3. Software modules (excelencia.software_modules table) - ERP catalog

        Args:
            query: User query to search for
            query_type: Type of query (for filtering)

        Returns:
            SearchResult with context string and metrics for logging
        """
        empty_result = SearchResult(
            context="",
            metrics=SearchMetrics(
                latency_ms=0.0,
                relevance_score=None,
                context_used=[],
                result_count=0,
            ),
        )

        if not self._enabled:
            return empty_result

        start_time = time.perf_counter()
        all_results: list[dict[str, Any]] = []

        logger.info(
            f"KnowledgeBaseSearch.search() - query='{query[:50]}...', "
            f"query_type={query_type}, agent_key={self._agent_key}, "
            f"max_results={self._max_results}"
        )

        try:
            # 1. Search agent-specific knowledge
            async with get_async_db_context() as db:
                use_case = SearchAgentKnowledgeUseCase(db)
                agent_results = await use_case.execute(
                    agent_key=self._agent_key,
                    query=query,
                    max_results=self._max_results,
                    min_similarity=0.3,  # Lowered from 0.4 for better recall
                )
                all_results.extend(agent_results)

                if agent_results:
                    logger.info(
                        f"[Source 1] agent_knowledge: Found {len(agent_results)} docs for '{self._agent_key}'"
                    )
                    for i, r in enumerate(agent_results):
                        logger.info(f"  - [{i+1}] {r.get('title', 'N/A')} (sim={r.get('similarity_score', 0):.2f})")
                else:
                    logger.warning(f"[Source 1] agent_knowledge: NO results for agent_key='{self._agent_key}'")

            # 2. Search company knowledge (software_catalog, etc.)
            # This uses hybrid search (vector + keyword) for better recall
            remaining = self._max_results - len(all_results)
            if remaining > 0:
                company_results = await self._search_company_knowledge(query, remaining)
                all_results.extend(company_results)

                if company_results:
                    logger.info(
                        f"Found {len(company_results)} docs in company_knowledge"
                    )

            # 3. Search software_modules (Excelencia ERP catalog)
            # Direct vector search on excelencia.software_modules table
            remaining = self._max_results - len(all_results)
            if remaining > 0:
                module_results = await self._search_software_modules(query, remaining)
                all_results.extend(module_results)

                if module_results:
                    logger.info(
                        f"Found {len(module_results)} docs in software_modules"
                    )

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Build metrics
            context_used = [r.get("title", "Unknown") for r in all_results]
            metrics = SearchMetrics(
                latency_ms=latency_ms,
                relevance_score=self._calculate_avg_relevance(all_results),
                context_used=context_used,
                result_count=len(all_results),
            )

            if not all_results:
                logger.warning(
                    f"No knowledge found for query: '{query[:80]}...' "
                    f"(agent_key={self._agent_key}, min_similarity=0.3). "
                    f"Consider adding relevant content to knowledge base."
                )
                return SearchResult(context="", metrics=metrics)

            logger.info(f"Total: {len(all_results)} knowledge docs found")

            return SearchResult(
                context=self._format_results(all_results),
                metrics=metrics,
            )

        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return empty_result

    def _calculate_avg_relevance(self, results: list[dict[str, Any]]) -> float | None:
        """Calculate average relevance score from results."""
        scores = [
            r.get("similarity_score", 0)
            for r in results
            if r.get("similarity_score") is not None
        ]
        if not scores:
            return None
        return sum(scores) / len(scores)

    async def _search_company_knowledge(
        self, query: str, max_results: int
    ) -> list[dict[str, Any]]:
        """
        Search company_knowledge table using hybrid search.

        This searches all document types including software_catalog
        which contains software module information.
        """
        try:
            embedding_service = KnowledgeEmbeddingService()
            results = await embedding_service.search_knowledge(
                query=query,
                k=max_results,
                min_similarity=0.3,  # Lower threshold for keyword fallback
                keyword_search=True,  # Enable hybrid search
            )

            # Convert to standard format
            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", ""),
                    "content": r.get("content", ""),
                    "document_type": r.get("document_type", ""),
                    "similarity_score": r.get("similarity_score", 0),
                    "match_type": r.get("match_type", "vector"),
                })
            return formatted

        except Exception as e:
            logger.error(f"Error searching company knowledge: {e}")
            return []

    async def _search_software_modules(
        self, query: str, max_results: int
    ) -> list[dict[str, Any]]:
        """
        Search excelencia.software_modules table using vector similarity.

        This directly searches the ERP software modules catalog which has
        its own embedding column with HNSW index.

        Args:
            query: User query to search for
            max_results: Maximum number of results to return

        Returns:
            List of matching software modules
        """
        try:
            # Generate embedding for query
            embedding_service = KnowledgeEmbeddingService()
            query_embedding = await embedding_service.generate_embedding(query)

            if not query_embedding:
                logger.warning("Could not generate embedding for software_modules search")
                return []

            async with get_async_db_context() as db:
                # Vector similarity search on software_modules
                # Uses CAST() instead of ::vector to avoid asyncpg parameter parsing issues
                sql = text("""
                    SELECT
                        id,
                        name,
                        code,
                        description,
                        category,
                        features,
                        1 - (embedding <=> CAST(:embedding AS vector)) as similarity
                    FROM excelencia.software_modules
                    WHERE embedding IS NOT NULL
                      AND active = true
                      AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_sim
                    ORDER BY similarity DESC
                    LIMIT :limit
                """)

                result = await db.execute(sql, {
                    "embedding": str(query_embedding),
                    "min_sim": 0.3,
                    "limit": max_results,
                })

                rows = result.fetchall()

                formatted = []
                for row in rows:
                    # Format features as a comma-separated string
                    features_text = ""
                    if row.features:
                        features_text = f"\nCaracterísticas: {', '.join(row.features)}"

                    formatted.append({
                        "title": f"Módulo ERP: {row.name} ({row.code})",
                        "content": f"{row.description}{features_text}",
                        "document_type": f"software_module/{row.category}",
                        "similarity_score": float(row.similarity),
                        "match_type": "vector",
                    })

                return formatted

        except Exception as e:
            logger.error(f"Error searching software_modules: {e}")
            return []

    def _format_results(self, results: list[dict[str, Any]]) -> str:
        """Format search results for LLM context."""
        context_parts = ["\n## INFORMACION DE SOPORTE (Knowledge Base):"]

        for i, result in enumerate(results, 1):
            title = result.get("title", "Sin titulo")
            content = result.get("content", "")
            doc_type = result.get("document_type", "")

            # Increased from 300 to 1500 chars to include corporate info (CEO, mission, etc.)
            content_preview = content[:1500] + "..." if len(content) > 1500 else content

            context_parts.append(f"\n### {i}. {title}")
            context_parts.append(content_preview)

            if doc_type:
                context_parts.append(f"*Tipo: {doc_type}*")

        return "\n".join(context_parts)
