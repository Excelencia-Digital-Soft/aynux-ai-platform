"""
Payment Idempotency Service

Redis-based idempotency service for Mercado Pago webhook deduplication.
Prevents processing the same payment notification multiple times.

Key Design:
- Uses Redis SET with NX (only set if not exists) + PX (expire in milliseconds)
- Returns previous receipt if payment was already processed
- 24-hour TTL for idempotency keys (matches MP payment preference expiry)

Usage in webhook:
    idempotency = PaymentIdempotencyService(redis)
    is_duplicate, previous_receipt = await idempotency.check_and_lock(payment_id)
    if is_duplicate:
        return {"status": "duplicate", "receipt": previous_receipt}
    ...
    await idempotency.mark_complete(payment_id, receipt_number)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Idempotency key prefix
PAYMENT_KEY_PREFIX = "mp:payment"

# Processing lock TTL (5 minutes) - to prevent concurrent processing
PROCESSING_LOCK_TTL_MS = 5 * 60 * 1000  # 5 minutes

# Completed payment TTL (24 hours) - matches MP preference expiry
COMPLETED_TTL_MS = 24 * 60 * 60 * 1000  # 24 hours


class PaymentIdempotencyService:
    """
    Redis-based idempotency service for payment webhook deduplication.

    Provides two operations:
    1. check_and_lock: Check if payment was already processed and acquire lock
    2. mark_complete: Mark payment as processed with receipt number

    States:
    - Not found: Payment not seen before
    - "processing": Payment is being processed by another worker
    - "receipt:XXX": Payment was processed, XXX is the receipt number
    """

    def __init__(self, redis_client: Redis):
        """
        Initialize idempotency service.

        Args:
            redis_client: Async Redis client instance
        """
        self._redis = redis_client

    def _get_key(self, payment_id: str) -> str:
        """Build Redis key for payment."""
        return f"{PAYMENT_KEY_PREFIX}:{payment_id}"

    async def check_and_lock(
        self,
        payment_id: str,
    ) -> tuple[bool, str | None]:
        """
        Check if payment was already processed and acquire processing lock.

        Uses atomic SET NX PX operation:
        - If key doesn't exist: sets "processing" value and returns (False, None)
        - If key exists with "processing": returns (True, None) - concurrent processing
        - If key exists with "receipt:XXX": returns (True, "XXX") - already processed

        Args:
            payment_id: Mercado Pago payment ID

        Returns:
            Tuple of (is_duplicate, previous_receipt_or_none)
        """
        key = self._get_key(payment_id)

        # Check existing value first
        existing = await self._redis.get(key)

        if existing:
            existing_str = existing.decode() if isinstance(existing, bytes) else str(existing)

            if existing_str == "processing":
                logger.warning(
                    f"[IDEMPOTENCY] Payment {payment_id} is currently being processed"
                )
                return (True, None)

            if existing_str.startswith("receipt:"):
                receipt = existing_str.split(":", 1)[1]
                logger.info(
                    f"[IDEMPOTENCY] Payment {payment_id} already processed: {receipt}"
                )
                return (True, receipt)

            # Unknown value, treat as duplicate
            logger.warning(
                f"[IDEMPOTENCY] Payment {payment_id} has unknown value: {existing_str}"
            )
            return (True, None)

        # Try to acquire lock with NX (only set if not exists)
        acquired = await self._redis.set(
            key,
            "processing",
            nx=True,
            px=PROCESSING_LOCK_TTL_MS,
        )

        if acquired:
            logger.debug(f"[IDEMPOTENCY] Acquired lock for payment {payment_id}")
            return (False, None)
        else:
            # Race condition - another worker acquired lock
            logger.info(f"[IDEMPOTENCY] Lost race for payment {payment_id}")
            return (True, None)

    async def mark_complete(
        self,
        payment_id: str,
        receipt_number: str,
    ) -> None:
        """
        Mark payment as successfully processed.

        Updates the key to "receipt:{receipt_number}" with 24h TTL.

        Args:
            payment_id: Mercado Pago payment ID
            receipt_number: PLEX receipt number (e.g., "RC X 0001-00016790")
        """
        key = self._get_key(payment_id)
        value = f"receipt:{receipt_number}"

        await self._redis.set(key, value, px=COMPLETED_TTL_MS)
        logger.info(f"[IDEMPOTENCY] Marked payment {payment_id} complete: {receipt_number}")

    async def mark_failed(
        self,
        payment_id: str,
        error: str,
    ) -> None:
        """
        Mark payment processing as failed.

        Removes the lock to allow retry. The error is logged but not stored.

        Args:
            payment_id: Mercado Pago payment ID
            error: Error description for logging
        """
        key = self._get_key(payment_id)
        await self._redis.delete(key)
        logger.warning(f"[IDEMPOTENCY] Removed lock for failed payment {payment_id}: {error}")

    async def get_receipt(self, payment_id: str) -> str | None:
        """
        Get receipt number for a processed payment.

        Args:
            payment_id: Mercado Pago payment ID

        Returns:
            Receipt number or None if not found/not processed
        """
        key = self._get_key(payment_id)
        value = await self._redis.get(key)

        if not value:
            return None

        value_str = value.decode() if isinstance(value, bytes) else str(value)

        if value_str.startswith("receipt:"):
            return value_str.split(":", 1)[1]

        return None


# Global service instance factory
_service_instance: PaymentIdempotencyService | None = None


async def get_idempotency_service() -> PaymentIdempotencyService:
    """
    Get or create the global PaymentIdempotencyService instance.

    Uses the shared Redis connection from the app.

    Returns:
        PaymentIdempotencyService instance
    """
    global _service_instance

    if _service_instance is None:
        from app.core.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        _service_instance = PaymentIdempotencyService(redis)

    return _service_instance


__all__ = ["PaymentIdempotencyService", "get_idempotency_service"]
