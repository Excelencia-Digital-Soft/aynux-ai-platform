"""
Knowledge Repository Helpers - Internal utilities for knowledge queries.

This module contains helper classes used by both KnowledgeRepository
and KnowledgeSearchRepository for filter construction and result formatting.
"""

from typing import Any

from app.models.db.knowledge_base import CompanyKnowledge


class KnowledgeFilterBuilder:
    """Builds SQLAlchemy filter conditions for knowledge queries."""

    @staticmethod
    def build_base_filters(
        document_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        active_only: bool = True,
    ) -> list[Any]:
        """
        Build common filter conditions for knowledge queries.

        Args:
            document_type: Filter by document type
            category: Filter by category
            tags: Filter by tags (documents with ANY of these tags)
            active_only: Only include active documents

        Returns:
            List of SQLAlchemy filter conditions
        """
        filters: list[Any] = []
        if active_only:
            filters.append(CompanyKnowledge.active)
        if document_type:
            filters.append(CompanyKnowledge.document_type == document_type)
        if category:
            filters.append(CompanyKnowledge.category == category)
        if tags:
            filters.append(CompanyKnowledge.tags.overlap(tags))
        return filters

    @staticmethod
    def add_embedding_requirement(filters: list[Any]) -> list[Any]:
        """Add filter requiring embedding to be present."""
        filters.append(CompanyKnowledge.embedding.isnot(None))
        return filters

    @staticmethod
    def add_search_vector_requirement(filters: list[Any]) -> list[Any]:
        """Add filter requiring search_vector to be present."""
        filters.append(CompanyKnowledge.search_vector.isnot(None))
        return filters


class KnowledgeResultFormatter:
    """Formats query results into dictionaries for API responses."""

    @staticmethod
    def _format_base(knowledge: CompanyKnowledge) -> dict[str, Any]:
        """Format base knowledge fields common to all search results."""
        return {
            "id": str(knowledge.id),
            "title": knowledge.title,
            "content": knowledge.content,
            "document_type": knowledge.document_type,
            "category": knowledge.category,
            "tags": knowledge.tags,
            "metadata": knowledge.meta_data,
            "created_at": knowledge.created_at.isoformat(),
            "updated_at": knowledge.updated_at.isoformat(),
        }

    @classmethod
    def format_vector_result(cls, row: Any) -> dict[str, Any]:
        """Format a single row from vector similarity search."""
        result = cls._format_base(row.CompanyKnowledge)
        result["similarity_score"] = float(row.similarity_score)
        return result

    @classmethod
    def format_text_result(cls, row: Any) -> dict[str, Any]:
        """Format a single row from full-text search."""
        result = cls._format_base(row.CompanyKnowledge)
        result["text_rank"] = float(row.text_rank)
        return result
