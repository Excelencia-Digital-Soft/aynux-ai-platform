"""
Async Redis Repository

Provides asynchronous Redis operations using redis.asyncio.
This is the async counterpart to RedisRepository for use in async contexts.
"""

import json
import logging
from typing import Any, Generic, TypeVar

import redis.asyncio as aioredis
from pydantic import BaseModel

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AsyncRedisRepository(Generic[T]):
    """
    Async repository for Redis operations.

    Uses redis.asyncio for non-blocking Redis calls in async contexts.

    Usage:
        repo = AsyncRedisRepository[MyModel](MyModel, prefix="my_prefix")
        await repo.connect()

        value = await repo.get("key")
        await repo.set("key", value, expiration=3600)
    """

    def __init__(self, model_class: type[T], prefix: str = ""):
        self.settings = get_settings()
        self.model_class = model_class
        self.prefix = prefix
        self._redis_client: aioredis.Redis | None = None
        self._is_dummy = False

    async def connect(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """Initialize async Redis connection with retries."""
        import asyncio

        retries = 0
        last_error: Exception | None = None

        while retries < max_retries:
            try:
                self._redis_client = aioredis.Redis(
                    host=self.settings.REDIS_HOST,
                    port=self.settings.REDIS_PORT,
                    db=self.settings.REDIS_DB,
                    password=self.settings.REDIS_PASSWORD,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
                # Verify connection works
                await self._redis_client.ping()
                logger.info(
                    f"Async Redis connection established: "
                    f"{self.settings.REDIS_HOST}:{self.settings.REDIS_PORT}"
                )
                self._is_dummy = False
                return
            except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
                retries += 1
                last_error = e
                logger.warning(
                    f"Async Redis connection attempt {retries}/{max_retries} failed: {e}"
                )
                if retries < max_retries:
                    await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Unexpected error connecting to async Redis: {e}")
                last_error = e
                break

        logger.error(
            f"Could not establish async Redis connection after {max_retries} attempts: {last_error}"
        )
        # Use async dummy client as fallback
        self._redis_client = None
        self._is_dummy = True

    async def _ensure_connected(self) -> None:
        """Ensure Redis is connected, lazy initialization."""
        if self._redis_client is None and not self._is_dummy:
            await self.connect()

    def _get_key(self, key: str) -> str:
        """Build full key with prefix."""
        return f"{self.prefix}:{key}" if self.prefix else key

    async def get(self, key: str) -> T | None:
        """Get an object by its key."""
        await self._ensure_connected()

        if self._is_dummy:
            logger.debug(f"Async dummy Redis: get({key}) -> None")
            return None

        try:
            redis_key = self._get_key(key)
            data = await self._redis_client.get(redis_key)

            if data is None:
                logger.debug(f"Key {redis_key} not found in async Redis")
                return None

            logger.debug(
                f"Data retrieved from async Redis: type={type(data)}, "
                f"length={(len(data) if isinstance(data, (str, bytes)) else 'n/a')}"
            )

            if isinstance(data, bytes):
                data = data.decode("utf-8")
                logger.debug(f"Decoded bytes to string: {data[:100]}...")

            if not data:
                return None

            # For dict model class
            if self.model_class is dict:
                result = json.loads(data)
                logger.debug("Deserialized to dict")
                return result

            # For Pydantic models
            try:
                if isinstance(data, str):
                    data_dict = json.loads(data)
                    result = self.model_class.model_validate(data_dict)
                    logger.debug(f"Deserialized to {self.model_class.__name__}")
                    return result
                else:
                    result = self.model_class.model_validate(data)
                    logger.debug(f"Directly deserialized to {self.model_class.__name__}")
                    return result
            except Exception as pydantic_error:
                logger.error(
                    f"Error validating data for {self.model_class.__name__}: {pydantic_error}"
                )
                return None

        except Exception as e:
            logger.error(f"Error getting data from async Redis: {e}")
            return None

    async def set(
        self, key: str, value: T, expiration: int | None = None
    ) -> bool:
        """Store an object by its key."""
        await self._ensure_connected()

        if self._is_dummy:
            logger.debug(f"Async dummy Redis: set({key}) -> True")
            return True

        try:
            # Serialize based on value type
            if hasattr(value, "model_dump") and callable(value.model_dump):
                # Pydantic v2
                serialized = json.dumps(
                    value.model_dump(mode="json"),
                    default=lambda dt: dt.isoformat(),
                )
            elif isinstance(value, dict):
                serialized = json.dumps(value, default=lambda dt: dt.isoformat())
            else:
                serialized = json.dumps(value, default=lambda dt: dt.isoformat())

            redis_key = self._get_key(key)
            await self._redis_client.set(redis_key, serialized)

            if expiration:
                await self._redis_client.expire(redis_key, expiration)

            return True

        except Exception as e:
            logger.error(f"Error saving to async Redis: {e}")
            return False

    async def set_if_not_exists(
        self, key: str, value: Any, expiration: int | None = None
    ) -> bool:
        """Store a value only if the key does not exist (NX)."""
        await self._ensure_connected()

        if self._is_dummy:
            logger.debug(f"Async dummy Redis: set_if_not_exists({key}) -> True")
            return True

        try:
            # Serialize value if needed
            if isinstance(value, BaseModel):
                value = value.model_dump_json()
            elif not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value)

            redis_key = self._get_key(key)
            result = await self._redis_client.set(redis_key, value, ex=expiration, nx=True)

            return bool(result)

        except Exception as e:
            logger.error(f"Error in async Redis set_if_not_exists: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete an object by its key."""
        await self._ensure_connected()

        if self._is_dummy:
            logger.debug(f"Async dummy Redis: delete({key}) -> True")
            return True

        try:
            redis_key = self._get_key(key)
            result = await self._redis_client.delete(redis_key)
            return bool(result)
        except Exception as e:
            logger.error(f"Error deleting from async Redis: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        await self._ensure_connected()

        if self._is_dummy:
            return False

        try:
            redis_key = self._get_key(key)
            result = await self._redis_client.exists(redis_key)
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking existence in async Redis: {e}")
            return False

    async def hash_set(
        self, key: str, field: str, value: Any, expiration: int | None = None
    ) -> bool:
        """Store a field in a hash."""
        await self._ensure_connected()

        if self._is_dummy:
            return True

        try:
            if isinstance(value, BaseModel):
                value = value.model_dump_json()
            elif not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value)

            redis_key = self._get_key(key)
            await self._redis_client.hset(redis_key, field, value)

            if expiration:
                await self._redis_client.expire(redis_key, expiration)

            return True
        except Exception as e:
            logger.error(f"Error in async Redis hash_set: {e}")
            return False

    async def hash_get(self, key: str, field: str) -> Any:
        """Get a field from a hash."""
        await self._ensure_connected()

        if self._is_dummy:
            return None

        try:
            redis_key = self._get_key(key)
            value = await self._redis_client.hget(redis_key, field)

            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Error in async Redis hash_get: {e}")
            return None

    async def hash_get_all(self, key: str) -> dict[str, Any]:
        """Get all fields from a hash."""
        await self._ensure_connected()

        if self._is_dummy:
            return {}

        try:
            redis_key = self._get_key(key)
            data = await self._redis_client.hgetall(redis_key)
            result = {}

            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except json.JSONDecodeError:
                    result[k] = v

            return result
        except Exception as e:
            logger.error(f"Error in async Redis hash_get_all: {e}")
            return {}

    async def hash_delete(self, key: str, field: str) -> bool:
        """Delete a field from a hash."""
        await self._ensure_connected()

        if self._is_dummy:
            return True

        try:
            redis_key = self._get_key(key)
            result = await self._redis_client.hdel(redis_key, field)
            return bool(result)
        except Exception as e:
            logger.error(f"Error in async Redis hash_delete: {e}")
            return False

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis_client and not self._is_dummy:
            await self._redis_client.close()
            logger.info("Async Redis connection closed")
