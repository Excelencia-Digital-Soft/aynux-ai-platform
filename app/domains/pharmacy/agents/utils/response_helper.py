# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Shared response generation helper.
#              Extracted from payment_processor_node.py and debt_manager_node.py.
# Tenant-Aware: Yes - uses PharmacyResponseGenerator with organization context.
# ============================================================================
"""
Shared response generation helper.

Single Responsibility: Generate responses using PharmacyResponseGenerator.

This module provides a shared helper function that was previously duplicated
in payment_processor_node.py and debt_manager_node.py.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Default fallback message when response generation fails
DEFAULT_FALLBACK_MESSAGE = "Disculpa, tuve un problema. Por favor intenta de nuevo."


async def generate_response(
    db: "AsyncSession",
    organization_id: "UUID",
    intent: str,
    state: dict[str, Any] | Any,
    user_message: str = "",
) -> str:
    """
    Generate response using PharmacyResponseGenerator.

    Falls back to a generic message if response generation fails.

    Args:
        db: Database session
        organization_id: Organization UUID for multi-tenant support
        intent: Intent key for response config lookup
        state: State dict (can be PharmacyStateV2 or plain dict)
        user_message: Optional user message for context

    Returns:
        Generated response content string
    """
    from app.domains.pharmacy.agents.utils.response import get_response_generator

    try:
        generator = get_response_generator()
        response = await generator.generate(
            db=db,
            organization_id=organization_id,
            intent=intent,
            state=state,
            user_message=user_message,
        )
        return response.content
    except Exception as e:
        logger.error(f"Error generating response for intent {intent}: {e}", exc_info=True)
        return DEFAULT_FALLBACK_MESSAGE


async def generate_response_with_type(
    db: "AsyncSession",
    organization_id: "UUID",
    intent: str,
    state: dict[str, Any] | Any,
    user_message: str = "",
) -> tuple[str, str]:
    """
    Generate response and return both content and type.

    Args:
        db: Database session
        organization_id: Organization UUID for multi-tenant support
        intent: Intent key for response config lookup
        state: State dict (can be PharmacyStateV2 or plain dict)
        user_message: Optional user message for context

    Returns:
        Tuple of (content, response_type) where response_type is
        "LLM", "CRITICAL", or "FALLBACK"
    """
    from app.domains.pharmacy.agents.utils.response import get_response_generator

    try:
        generator = get_response_generator()
        response = await generator.generate(
            db=db,
            organization_id=organization_id,
            intent=intent,
            state=state,
            user_message=user_message,
        )
        return response.content, str(response.response_type.value)
    except Exception as e:
        logger.error(f"Error generating response for intent {intent}: {e}", exc_info=True)
        return DEFAULT_FALLBACK_MESSAGE, "FALLBACK"
