"""
Database Helpers for Pharmacy Domain

Shared utilities for database and multi-tenant operations.
Used by nodes and handlers that need to generate responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Default system organization UUID
SYSTEM_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")


def get_organization_id(state: dict[str, Any]) -> UUID:
    """
    Extract organization_id from state.

    Args:
        state: Current state dictionary

    Returns:
        Organization UUID (defaults to system org if not found)
    """
    org_id = state.get("organization_id")
    if org_id is None:
        # Fallback to system org for backward compatibility
        return SYSTEM_ORG_ID
    if isinstance(org_id, UUID):
        return org_id
    try:
        return UUID(str(org_id))
    except (ValueError, TypeError):
        return SYSTEM_ORG_ID


async def get_db_session() -> AsyncSession:
    """
    Get a database session for operations.

    Returns:
        AsyncSession instance

    Usage:
        async with await get_db_session() as db:
            # use db
            pass
    """
    from app.database.async_db import AsyncSessionLocal

    return AsyncSessionLocal()


async def generate_response(
    state: dict[str, Any],
    intent: str,
    user_message: str = "",
    current_task: str = "",
) -> str:
    """
    Generate a response using ResponseGenerator with proper db and org_id.

    This is a convenience function that handles db session and organization_id
    extraction from state automatically.

    Args:
        state: Current state dictionary (should contain organization_id)
        intent: Intent key for response generation
        user_message: User's message
        current_task: Task description for LLM

    Returns:
        Generated response content string
    """
    from app.domains.pharmacy.agents.utils.response_generator import get_response_generator

    response_generator = get_response_generator()
    org_id = get_organization_id(state)

    async with await get_db_session() as db:
        result = await response_generator.generate(
            db=db,
            organization_id=org_id,
            intent=intent,
            state=state,
            user_message=user_message,
            current_task=current_task,
        )
        return result.content


__all__ = [
    "SYSTEM_ORG_ID",
    "get_organization_id",
    "get_db_session",
    "generate_response",
]
