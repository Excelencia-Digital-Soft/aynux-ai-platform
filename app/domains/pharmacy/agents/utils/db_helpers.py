"""
Database Helpers for Pharmacy Domain

Shared utilities for database and multi-tenant operations.
Used by nodes and handlers that need to generate responses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

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


# Task manager singleton for efficient caching
_task_manager = None


def _get_task_manager():
    """Get or create TaskManager singleton."""
    global _task_manager
    if _task_manager is None:
        from app.tasks import TaskManager

        _task_manager = TaskManager()
    return _task_manager


async def get_current_task(
    key: str,
    variables: dict[str, Any] | None = None,
) -> str:
    """
    Get current task description from YAML configuration.

    This function loads task descriptions from YAML files in app/tasks/templates/.
    Use TaskRegistry constants for type-safe key access.

    Args:
        key: Task key (e.g., TaskRegistry.PHARMACY_IDENTIFICATION_REQUEST_DNI)
        variables: Optional variables for template substitution

    Returns:
        Task description string, rendered with variables if provided

    Raises:
        ValueError: If task not found

    Example:
        from app.tasks import TaskRegistry

        task = await get_current_task(TaskRegistry.PHARMACY_GREETING_DEFAULT)
        # Returns: "Saluda al cliente cordialmente y ofrece ayuda..."
    """
    manager = _get_task_manager()
    try:
        return await manager.get_task(key, variables)
    except ValueError:
        logger.warning(f"Task not found: {key}, returning empty string")
        return ""


__all__ = [
    "SYSTEM_ORG_ID",
    "get_organization_id",
    "get_db_session",
    "generate_response",
    "get_current_task",
]
