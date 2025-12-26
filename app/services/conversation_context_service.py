"""
Conversation Context Service

Manages conversation context across Redis (hot cache) and PostgreSQL (persistent storage).
Implements a tiered storage strategy:
- Redis: Fast access for active conversations (7-day TTL)
- PostgreSQL: Persistent storage as source of truth
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_context import (
    ConversationContextModel,
    ConversationMessageModel,
)
from app.models.db.conversation_history import ConversationContext, ConversationMessage
from app.repositories.async_redis_repository import AsyncRedisRepository

logger = logging.getLogger(__name__)

# Cache configuration
CONTEXT_REDIS_TTL = 604800  # 7 days in seconds
MESSAGE_REDIS_TTL = 86400  # 24 hours in seconds
DEFAULT_MESSAGE_LIMIT = 20


class ConversationContextService:
    """
    Service for managing conversation context with Redis and PostgreSQL.

    Usage:
        service = ConversationContextService(db_session)
        context = await service.get_context("whatsapp_123456")
        await service.save_context("whatsapp_123456", updated_context)
    """

    def __init__(self, db: AsyncSession | None = None):
        """
        Initialize the service.

        Args:
            db: Optional SQLAlchemy async session for PostgreSQL access
        """
        self.db = db
        self._redis: AsyncRedisRepository[ConversationContextModel] | None = None

    @property
    def redis(self) -> AsyncRedisRepository[ConversationContextModel]:
        """Lazy initialization of async Redis repository."""
        if self._redis is None:
            self._redis = AsyncRedisRepository[ConversationContextModel](
                ConversationContextModel,
                prefix="conv_ctx",
            )
        return self._redis

    # =========================================================================
    # Main API Methods
    # =========================================================================

    async def get_context(
        self, conversation_id: str
    ) -> ConversationContextModel | None:
        """
        Get conversation context from cache or database.

        Implements tiered lookup: Redis → PostgreSQL

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            ConversationContextModel or None if not found
        """
        # Try Redis first (hot cache) - NOW ASYNC
        context = await self._get_from_cache(conversation_id)
        if context:
            logger.debug(f"Context cache hit for {conversation_id}")
            return context

        # Fall back to PostgreSQL
        context = await self._get_from_db(conversation_id)
        if context:
            logger.debug(f"Context loaded from DB for {conversation_id}")
            # Warm the cache for future requests - NOW ASYNC
            await self._save_to_cache(conversation_id, context)
            return context

        logger.debug(f"No context found for {conversation_id}")
        return None

    async def save_context(
        self, conversation_id: str, context: ConversationContextModel
    ) -> None:
        """
        Save conversation context to both Redis and PostgreSQL.

        Args:
            conversation_id: Unique conversation identifier
            context: The context model to save
        """
        # Update timestamps
        context.updated_at = datetime.now(UTC)
        context.last_activity_at = datetime.now(UTC)

        # Save to Redis (hot cache) - NOW ASYNC
        await self._save_to_cache(conversation_id, context)

        # Save to PostgreSQL (persistent)
        if self.db:
            await self._upsert_to_db(conversation_id, context)
            logger.debug(f"Context saved to DB for {conversation_id}")

    async def save_message(
        self,
        conversation_id: str,
        sender_type: str,
        content: str,
        agent_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Save a single message to the conversation history.

        Args:
            conversation_id: Unique conversation identifier
            sender_type: 'user', 'assistant', or 'system'
            content: Message content
            agent_name: Name of the agent (for assistant messages)
            metadata: Additional message metadata
        """
        if not self.db:
            logger.warning("No DB session available for saving message")
            return

        message = ConversationMessage(
            conversation_id=conversation_id,
            sender_type=sender_type,
            content=content,
            agent_name=agent_name,
            extra_data=metadata or {},
        )

        self.db.add(message)
        await self.db.commit()
        logger.debug(f"Message saved for {conversation_id}: {sender_type}")

    async def get_recent_messages(
        self, conversation_id: str, limit: int = DEFAULT_MESSAGE_LIMIT
    ) -> list[ConversationMessageModel]:
        """
        Get recent messages for a conversation.

        Args:
            conversation_id: Unique conversation identifier
            limit: Maximum number of messages to return

        Returns:
            List of messages, ordered by creation time (oldest first)
        """
        if not self.db:
            logger.warning("No DB session available for getting messages")
            return []

        result = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )

        rows = result.scalars().all()

        # Reverse to get oldest first
        messages = [
            ConversationMessageModel(
                sender_type=row.sender_type,
                content=row.content,
                agent_name=row.agent_name,
                metadata=row.metadata or {},
                created_at=row.created_at,
            )
            for row in reversed(rows)
        ]

        return messages

    async def get_recent_conversations(
        self,
        organization_id: str | None = None,
        user_phone: str | None = None,
        limit: int = 10,
    ) -> list[ConversationContextModel]:
        """
        Get recent conversations, optionally filtered by organization or user.

        Args:
            organization_id: Filter by organization (multi-tenancy)
            user_phone: Filter by user phone number
            limit: Maximum number of conversations to return

        Returns:
            List of conversation contexts, ordered by last activity
        """
        if not self.db:
            return []

        query = select(ConversationContext).order_by(
            ConversationContext.last_activity_at.desc()
        )

        if organization_id:
            query = query.where(
                ConversationContext.organization_id == organization_id
            )

        if user_phone:
            query = query.where(ConversationContext.user_phone == user_phone)

        query = query.limit(limit)

        result = await self.db.execute(query)
        rows = result.scalars().all()

        return [self._row_to_model(row) for row in rows]

    async def clear_context(self, conversation_id: str) -> None:
        """
        Clear conversation context and all messages.

        Args:
            conversation_id: Unique conversation identifier
        """
        # Clear from Redis - NOW ASYNC
        try:
            await self.redis.delete(conversation_id)
        except Exception as e:
            logger.warning(f"Error clearing Redis cache: {e}")

        # Clear from PostgreSQL (cascade will delete messages)
        if self.db:
            result = await self.db.execute(
                select(ConversationContext).where(
                    ConversationContext.conversation_id == conversation_id
                )
            )
            row = result.scalar_one_or_none()
            if row:
                await self.db.delete(row)
                await self.db.commit()
                logger.info(f"Cleared context for {conversation_id}")

    async def get_or_create_context(
        self, conversation_id: str, **initial_data: Any
    ) -> ConversationContextModel:
        """
        Get existing context or create a new one.

        Args:
            conversation_id: Unique conversation identifier
            **initial_data: Initial data for new context (organization_id, user_phone, etc.)

        Returns:
            ConversationContextModel (existing or newly created)
        """
        context = await self.get_context(conversation_id)

        if context is None:
            context = ConversationContextModel(
                conversation_id=conversation_id,
                **initial_data,
            )
            await self.save_context(conversation_id, context)
            logger.info(f"Created new context for {conversation_id}")

        return context

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _get_from_cache(self, conversation_id: str) -> ConversationContextModel | None:
        """Get context from async Redis cache."""
        try:
            return await self.redis.get(conversation_id)
        except Exception as e:
            logger.warning(f"Error reading from async Redis: {e}")
            return None

    async def _save_to_cache(
        self, conversation_id: str, context: ConversationContextModel
    ) -> None:
        """Save context to async Redis cache."""
        try:
            await self.redis.set(conversation_id, context, expiration=CONTEXT_REDIS_TTL)
        except Exception as e:
            logger.warning(f"Error writing to async Redis: {e}")

    async def _get_from_db(
        self, conversation_id: str
    ) -> ConversationContextModel | None:
        """Get context from PostgreSQL."""
        if not self.db:
            return None

        result = await self.db.execute(
            select(ConversationContext).where(
                ConversationContext.conversation_id == conversation_id
            )
        )
        row = result.scalar_one_or_none()

        if row:
            return self._row_to_model(row)
        return None

    async def _upsert_to_db(
        self, conversation_id: str, context: ConversationContextModel
    ) -> None:
        """Upsert context to PostgreSQL."""
        if not self.db:
            return

        stmt = insert(ConversationContext).values(
            conversation_id=conversation_id,
            organization_id=context.organization_id,
            user_phone=context.user_phone,
            rolling_summary=context.rolling_summary,
            topic_history=context.topic_history,
            key_entities=context.key_entities,
            total_turns=context.total_turns,
            last_user_message=context.last_user_message,
            last_bot_response=context.last_bot_response,
            extra_data=context.metadata,
            last_activity_at=context.last_activity_at,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["conversation_id"],
            set_={
                "rolling_summary": context.rolling_summary,
                "topic_history": context.topic_history,
                "key_entities": context.key_entities,
                "total_turns": context.total_turns,
                "last_user_message": context.last_user_message,
                "last_bot_response": context.last_bot_response,
                "extra_data": context.metadata,
                "last_activity_at": context.last_activity_at,
                "updated_at": datetime.now(UTC),
            },
        )

        await self.db.execute(stmt)
        await self.db.commit()

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime:
        """Normalize datetime to UTC-aware.

        Handles both naive datetimes (from legacy DB) and aware datetimes.
        """
        if dt is None:
            return datetime.now(UTC)
        if dt.tzinfo is None:
            # Naive datetime from DB - assume UTC and make aware
            return dt.replace(tzinfo=UTC)
        return dt

    def _row_to_model(self, row: ConversationContext) -> ConversationContextModel:
        """Convert SQLAlchemy row to Pydantic model with timezone normalization."""
        return ConversationContextModel(
            conversation_id=row.conversation_id,
            organization_id=str(row.organization_id) if row.organization_id else None,
            user_phone=row.user_phone,
            rolling_summary=row.rolling_summary or "",
            topic_history=row.topic_history or [],
            key_entities=row.key_entities or {},
            total_turns=row.total_turns,
            last_user_message=row.last_user_message,
            last_bot_response=row.last_bot_response,
            metadata=row.extra_data or {},
            created_at=self._ensure_utc(row.created_at),
            updated_at=self._ensure_utc(row.updated_at),
            last_activity_at=self._ensure_utc(row.last_activity_at),
        )
