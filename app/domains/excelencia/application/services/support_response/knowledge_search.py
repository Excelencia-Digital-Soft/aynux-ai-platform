"""
Knowledge base search service for support.

Searches multiple knowledge sources:
1. Agent-specific knowledge (agent_knowledge table)
2. Company knowledge (company_knowledge table) - includes software modules

Uses hybrid search (vector + keyword) for better recall.
"""

import logging
from typing import Any

from app.config.settings import get_settings
from app.database.async_db import get_async_db_context
from app.domains.shared.application.use_cases.agent_knowledge_use_cases import (
    SearchAgentKnowledgeUseCase,
)
from app.integrations.vector_stores.knowledge_embedding_service import (
    KnowledgeEmbeddingService,
)

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

    async def search(self, query: str, query_type: str) -> str:
        """
        Search multiple knowledge sources for support information.

        Searches in order:
        1. Agent-specific knowledge (agent_knowledge table)
        2. Company knowledge (company_knowledge table) - for software modules

        Args:
            query: User query to search for
            query_type: Type of query (for logging/filtering)

        Returns:
            Formatted context string for LLM, or empty string if no results
        """
        if not self._enabled:
            return ""

        all_results: list[dict[str, Any]] = []

        try:
            # 1. Search agent-specific knowledge
            async with get_async_db_context() as db:
                use_case = SearchAgentKnowledgeUseCase(db)
                agent_results = await use_case.execute(
                    agent_key=self._agent_key,
                    query=query,
                    max_results=self._max_results,
                    min_similarity=0.4,
                )
                all_results.extend(agent_results)

                if agent_results:
                    logger.info(
                        f"Found {len(agent_results)} docs in agent_knowledge for '{self._agent_key}'"
                    )

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

            if not all_results:
                logger.debug(f"No knowledge found for query: {query[:50]}...")
                return ""

            logger.info(f"Total: {len(all_results)} knowledge docs found")
            return self._format_results(all_results)

        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return ""

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

    def _format_results(self, results: list[dict[str, Any]]) -> str:
        """Format search results for LLM context."""
        context_parts = ["\n## INFORMACION DE SOPORTE (Knowledge Base):"]

        for i, result in enumerate(results, 1):
            title = result.get("title", "Sin titulo")
            content = result.get("content", "")
            doc_type = result.get("document_type", "")

            content_preview = content[:300] + "..." if len(content) > 300 else content

            context_parts.append(f"\n### {i}. {title}")
            context_parts.append(content_preview)

            if doc_type:
                context_parts.append(f"*Tipo: {doc_type}*")

        return "\n".join(context_parts)
