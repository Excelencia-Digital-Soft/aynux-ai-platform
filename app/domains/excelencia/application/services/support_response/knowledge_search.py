"""
Knowledge base search service for support.

Searches the agent-specific knowledge base for support-related information.
Uses SearchAgentKnowledgeUseCase to query the agent_knowledge table.
"""

import logging
from typing import Any

from app.config.settings import get_settings
from app.database.async_db import get_async_db_context
from app.domains.shared.application.use_cases.agent_knowledge_use_cases import (
    SearchAgentKnowledgeUseCase,
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
        Search agent knowledge base for support information.

        Args:
            query: User query to search for
            query_type: Type of query (for logging/filtering)

        Returns:
            Formatted context string for LLM, or empty string if no results
        """
        if not self._enabled:
            return ""

        try:
            async with get_async_db_context() as db:
                use_case = SearchAgentKnowledgeUseCase(db)
                results = await use_case.execute(
                    agent_key=self._agent_key,
                    query=query,
                    max_results=self._max_results,
                    min_similarity=0.4,  # Lower threshold for better recall
                )

                if not results:
                    logger.debug(
                        f"No knowledge found for agent '{self._agent_key}' "
                        f"query: {query[:50]}..."
                    )
                    return ""

                logger.info(
                    f"Found {len(results)} knowledge docs for '{self._agent_key}'"
                )
                return self._format_results(results)

        except Exception as e:
            logger.error(f"Error searching agent knowledge base: {e}")
            return ""

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
