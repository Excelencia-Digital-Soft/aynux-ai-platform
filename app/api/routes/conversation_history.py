"""
Conversation History API

REST endpoints for managing conversation history and context.
Provides access to:
- Conversation context (rolling summary, metadata)
- Message history
- Conversation management (clear, regenerate summary)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_async_db
from app.models.conversation_context import (
    ConversationContextResponse,
    ConversationListResponse,
    MessageListResponse,
    SummaryResponse,
)
from app.services.conversation_context_service import ConversationContextService

router = APIRouter(prefix="/conversations", tags=["conversation-history"])
logger = logging.getLogger(__name__)


def _get_context_service(db: AsyncSession) -> ConversationContextService:
    """Get context service with database session."""
    return ConversationContextService(db=db)


@router.get("/{conversation_id}/context", response_model=ConversationContextResponse)
async def get_conversation_context(
    conversation_id: str,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> ConversationContextResponse:
    """
    Get conversation context and summary.

    Args:
        conversation_id: Unique conversation identifier

    Returns:
        ConversationContextResponse with summary and metadata
    """
    service = _get_context_service(db)
    context = await service.get_context(conversation_id)

    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    return ConversationContextResponse(
        conversation_id=conversation_id,
        summary=context.rolling_summary,
        topic_history=context.topic_history,
        total_turns=context.total_turns,
        last_activity=context.last_activity_at.isoformat(),
    )


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def get_conversation_messages(
    conversation_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> MessageListResponse:
    """
    Get paginated conversation messages.

    Args:
        conversation_id: Unique conversation identifier
        limit: Maximum number of messages to return (default: 20)
        offset: Number of messages to skip (default: 0)

    Returns:
        MessageListResponse with list of messages
    """
    service = _get_context_service(db)

    # Verify conversation exists
    context = await service.get_context(conversation_id)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    messages = await service.get_recent_messages(conversation_id, limit=limit + offset)

    # Apply offset
    if offset > 0:
        messages = messages[offset:]

    return MessageListResponse(
        conversation_id=conversation_id,
        messages=messages[:limit],
        limit=limit,
        offset=offset,
        total=context.total_turns,
    )


@router.delete("/{conversation_id}")
async def clear_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> dict[str, Any]:
    """
    Clear conversation history and context.

    Args:
        conversation_id: Unique conversation identifier

    Returns:
        Status response
    """
    service = _get_context_service(db)

    # Verify conversation exists
    context = await service.get_context(conversation_id)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    await service.clear_context(conversation_id)

    return {
        "status": "cleared",
        "conversation_id": conversation_id,
        "message": "Conversation history cleared successfully",
    }


@router.post("/{conversation_id}/summarize", response_model=SummaryResponse)
async def regenerate_summary(
    conversation_id: str,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> SummaryResponse:
    """
    Force regeneration of conversation summary.

    Useful when the rolling summary needs to be refreshed or
    after manual edits to the conversation.

    Args:
        conversation_id: Unique conversation identifier

    Returns:
        SummaryResponse with new summary
    """
    from app.domains.shared.agents.history_agent import HistoryAgent
    from app.integrations.llm import VllmLLM

    service = _get_context_service(db)

    # Verify conversation exists
    context = await service.get_context(conversation_id)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    # Get recent messages for summarization
    messages = await service.get_recent_messages(conversation_id, limit=20)
    if not messages:
        return SummaryResponse(
            conversation_id=conversation_id,
            new_summary="",
            total_turns=context.total_turns,
        )

    # Build conversation text for summarization
    conversation_text = "\n".join(
        f"{msg.sender_type.upper()}: {msg.content}" for msg in messages
    )

    # Initialize history agent for summarization
    llm = VllmLLM()
    history_agent = HistoryAgent(llm=llm)

    try:
        # Generate new summary
        new_summary = await history_agent.summarize(
            previous_summary="",
            user_message="[Full conversation history]",
            bot_response=conversation_text,
        )

        # Update context with new summary
        context.rolling_summary = new_summary
        await service.save_context(conversation_id, context)

        return SummaryResponse(
            conversation_id=conversation_id,
            new_summary=new_summary,
            total_turns=context.total_turns,
        )

    except Exception as e:
        logger.error(f"Error regenerating summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error regenerating summary: {str(e)}",
        ) from e


@router.get("/recent", response_model=ConversationListResponse)
async def get_recent_conversations(
    limit: int = 10,
    organization_id: str | None = None,
    user_phone: str | None = None,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> ConversationListResponse:
    """
    Get recent conversations.

    Args:
        limit: Maximum number of conversations to return (default: 10)
        organization_id: Filter by organization (optional)
        user_phone: Filter by user phone (optional)

    Returns:
        ConversationListResponse with list of recent conversations
    """
    service = _get_context_service(db)

    conversations = await service.get_recent_conversations(
        organization_id=organization_id,
        user_phone=user_phone,
        limit=limit,
    )

    return ConversationListResponse(
        conversations=[
            ConversationContextResponse(
                conversation_id=c.conversation_id,
                summary=c.rolling_summary,
                topic_history=c.topic_history,
                total_turns=c.total_turns,
                last_activity=c.last_activity_at.isoformat(),
            )
            for c in conversations
        ],
        total=len(conversations),
    )
