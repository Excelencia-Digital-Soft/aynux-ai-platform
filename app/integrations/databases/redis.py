"""
Redis Integration

Provides Redis client and connection management.
"""

import logging
from typing import Any

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

_redis_client = None


def get_redis_client():
    """
    Get Redis client instance (singleton).

    Returns:
        Redis client instance
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    settings = get_settings()

    try:
        import redis

        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )

        # Test connection
        _redis_client.ping()
        logger.info(f"Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

        return _redis_client
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise


async def get_async_redis_client():
    """
    Get async Redis client instance.

    Returns:
        Async Redis client instance
    """
    settings = get_settings()

    try:
        import redis.asyncio as aioredis

        client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )

        # Test connection
        await client.ping()
        logger.info(f"Async Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

        return client
    except Exception as e:
        logger.error(f"Async Redis connection failed: {e}")
        raise


def close_redis_client() -> None:
    """Close Redis client connection."""
    global _redis_client

    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


__all__ = [
    "get_redis_client",
    "get_async_redis_client",
    "close_redis_client",
]
