"""
Common utilities for Knowledge Use Cases.

This module contains shared imports, types, and helper functions
used across all knowledge-related use cases.
"""

import logging
from typing import Any

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def knowledge_to_dict(knowledge: Any) -> dict[str, Any]:
    """
    Convert CompanyKnowledge model to dictionary.

    This helper function is shared across all knowledge use cases
    to ensure consistent serialization.

    Args:
        knowledge: CompanyKnowledge model instance

    Returns:
        Dictionary representation of the knowledge document
    """
    return {
        "id": str(knowledge.id),
        "title": knowledge.title,
        "content": knowledge.content,
        "document_type": knowledge.document_type,
        "category": knowledge.category,
        "tags": knowledge.tags or [],
        "metadata": knowledge.meta_data or {},
        "active": knowledge.active,
        "sort_order": knowledge.sort_order,
        "has_embedding": knowledge.embedding is not None,
        "created_at": knowledge.created_at.isoformat(),
        "updated_at": knowledge.updated_at.isoformat(),
    }
