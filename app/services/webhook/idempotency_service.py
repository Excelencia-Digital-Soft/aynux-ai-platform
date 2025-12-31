# ============================================================================
# SCOPE: GLOBAL
# Description: Redis-based idempotency service for webhook processing.
#              Prevents duplicate message processing per Chattigo ISV section 4.2.
# ============================================================================
"""
Idempotency Service for Webhook Processing.

Uses Redis SET NX for atomic duplicate detection.

Per Chattigo ISV Documentation (Section 4.2):
- "Due to network retries, Chattigo may send the same webhook event more than once"
- "ISV system must implement idempotency logic, tracking processed message_ids"

Redis Key Pattern:
    webhook:msg:{message_id}
    Value: {"state": "processing|completed", "timestamp": float}
    TTL: 5min (processing) / 24h (completed)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.repositories.async_redis_repository import AsyncRedisRepository

logger = logging.getLogger(__name__)


class ProcessingState(str, Enum):
    """Message processing states for idempotency tracking."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IdempotencyState(BaseModel):
    """Pydantic model for idempotency state stored in Redis."""

    state: str
    timestamp: float
    completed_at: float | None = None


@dataclass
class IdempotencyResult:
    """Result of idempotency check."""

    is_duplicate: bool
    state: ProcessingState | None
    message_id: str


class IdempotencyService:
    """
    Redis-based idempotency service for webhook processing.

    Uses atomic SET NX to prevent duplicate message processing.
    TTL ensures stale locks are automatically released.

    Usage:
        service = IdempotencyService()
        result = await service.try_acquire_lock("msg_123")

        if result.is_duplicate:
            return {"status": "duplicate"}

        try:
            # Process message
            await service.mark_completed("msg_123")
        except Exception:
            await service.mark_failed("msg_123")  # Allow retry
    """

    PREFIX = "webhook:msg"
    LOCK_TTL = 300  # 5 minutes for processing timeout
    COMPLETED_TTL = 86400  # 24 hours to track completed messages

    def __init__(
        self, redis_repo: AsyncRedisRepository[IdempotencyState] | None = None
    ):
        self._redis: AsyncRedisRepository[IdempotencyState] | None = redis_repo
        self._initialized = False

    async def _ensure_connected(self) -> None:
        """Lazy initialization of Redis connection."""
        if self._redis is None:
            from app.repositories.async_redis_repository import AsyncRedisRepository

            self._redis = AsyncRedisRepository[IdempotencyState](
                IdempotencyState, prefix=self.PREFIX
            )
            await self._redis.connect()
            self._initialized = True
        elif not self._initialized:
            await self._redis.connect()
            self._initialized = True

    async def try_acquire_lock(self, message_id: str) -> IdempotencyResult:
        """
        Attempt to acquire processing lock for message.

        Args:
            message_id: Unique message identifier

        Returns:
            IdempotencyResult with:
            - is_duplicate=False if lock acquired (proceed with processing)
            - is_duplicate=True if message already exists (skip processing)
        """
        if not message_id:
            logger.warning("Empty message_id provided to idempotency check")
            return IdempotencyResult(
                is_duplicate=False,
                state=None,
                message_id="",
            )

        try:
            await self._ensure_connected()

            # Check if message already processed or processing
            existing = await self._redis.get(message_id)
            if existing:
                existing_state = existing.state
                logger.debug(f"Duplicate message detected: {message_id} (state={existing_state})")
                return IdempotencyResult(
                    is_duplicate=True,
                    state=ProcessingState(existing_state),
                    message_id=message_id,
                )

            # Atomic SET NX - only one request wins
            lock_data = IdempotencyState(
                state=ProcessingState.PROCESSING.value,
                timestamp=time.time(),
            )
            acquired = await self._redis.set_if_not_exists(
                message_id,
                lock_data,
                expiration=self.LOCK_TTL,
            )

            if not acquired:
                # Race condition - another request got the lock
                logger.debug(f"Lock race lost for message: {message_id}")
                return IdempotencyResult(
                    is_duplicate=True,
                    state=ProcessingState.PROCESSING,
                    message_id=message_id,
                )

            logger.debug(f"Lock acquired for message: {message_id}")
            return IdempotencyResult(
                is_duplicate=False,
                state=ProcessingState.PROCESSING,
                message_id=message_id,
            )

        except Exception as e:
            # Redis failure - allow processing (better to process twice than not at all)
            logger.warning(
                f"Redis unavailable for idempotency check, proceeding without: {message_id} - {e}"
            )
            return IdempotencyResult(
                is_duplicate=False,
                state=None,
                message_id=message_id,
            )

    async def mark_completed(self, message_id: str) -> bool:
        """
        Mark message as successfully processed.

        Extends TTL to 24h to prevent reprocessing from Chattigo retries.

        Args:
            message_id: Message identifier to mark as completed

        Returns:
            True if updated successfully, False otherwise
        """
        if not message_id:
            return False

        try:
            await self._ensure_connected()
            return await self._redis.set(
                message_id,
                IdempotencyState(
                    state=ProcessingState.COMPLETED.value,
                    timestamp=time.time(),
                    completed_at=time.time(),
                ),
                expiration=self.COMPLETED_TTL,
            )
        except Exception as e:
            logger.error(f"Failed to mark message completed: {message_id} - {e}")
            return False

    async def mark_failed(self, message_id: str) -> bool:
        """
        Mark message as failed and remove lock.

        Deletes the lock to allow retry from Chattigo.

        Args:
            message_id: Message identifier to mark as failed

        Returns:
            True if deleted successfully, False otherwise
        """
        if not message_id:
            return False

        try:
            await self._ensure_connected()
            return await self._redis.delete(message_id)
        except Exception as e:
            logger.error(f"Failed to mark message failed: {message_id} - {e}")
            return False

    async def get_state(self, message_id: str) -> ProcessingState | None:
        """
        Get current processing state of a message.

        Args:
            message_id: Message identifier to check

        Returns:
            ProcessingState if found, None otherwise
        """
        if not message_id:
            return None

        try:
            await self._ensure_connected()
            data = await self._redis.get(message_id)
            if data and isinstance(data, IdempotencyState):
                return ProcessingState(data.state)
            return None
        except Exception as e:
            logger.error(f"Failed to get message state: {message_id} - {e}")
            return None
