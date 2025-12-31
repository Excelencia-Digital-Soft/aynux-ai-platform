# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Cache de tokens JWT para Chattigo con auto-refresh per DID.
# ============================================================================
"""
Chattigo Token Cache.

Single Responsibility: Manage JWT token lifecycle (obtain, cache, invalidate).
"""

import asyncio
import logging
import time

import httpx

from app.core.tenancy import ChattigoCredentials
from app.repositories.async_redis_repository import AsyncRedisRepository

from .exceptions import ChattigoTokenError
from .models import ChattigoLoginRequest, ChattigoLoginResponse
from .token_models import ChattigoTokenData

logger = logging.getLogger(__name__)


class ChattigoTokenCache:
    """
    Redis-backed cache for Chattigo JWT tokens with auto-refresh per DID.

    Each DID maintains its own token with independent refresh timing.
    Tokens are refreshed before expiration based on token_refresh_hours setting.

    Primary storage: Redis (persistent across restarts)
    Fallback: In-memory dict (if Redis unavailable)

    Thread-safe via asyncio.Lock per DID operation.
    """

    # Token TTL: 8 hours (per Chattigo ISV spec)
    TOKEN_TTL_HOURS = 8
    # Redis key prefix for Chattigo tokens
    REDIS_PREFIX = "chattigo:token"

    def __init__(self) -> None:
        """Initialize token cache."""
        # In-memory fallback cache: {did: (token, expiry_timestamp)}
        self._tokens: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()
        self._http_client: httpx.AsyncClient | None = None
        # Redis repository for persistent token storage (lazy initialized)
        self._redis_repo: AsyncRedisRepository[ChattigoTokenData] | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for token requests."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def _ensure_redis(self) -> AsyncRedisRepository[ChattigoTokenData]:
        """
        Ensure Redis repository is initialized (lazy initialization).

        Returns:
            Initialized Redis repository for ChattigoTokenData
        """
        if self._redis_repo is None:
            self._redis_repo = AsyncRedisRepository[ChattigoTokenData](
                ChattigoTokenData,
                prefix=self.REDIS_PREFIX,
            )
        return self._redis_repo

    async def close(self) -> None:
        """Close HTTP client, Redis connection, and clear cache."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        if self._redis_repo:
            await self._redis_repo.close()
            self._redis_repo = None
        self._tokens.clear()

    async def get_token(
        self, did: str, credentials: ChattigoCredentials
    ) -> str:
        """
        Get valid token for DID, refreshing if needed.

        Token refresh occurs at (TTL - (TTL - refresh_hours)) from expiry,
        which means refresh happens `refresh_hours` after token was obtained.

        Primary storage: Redis (persistent)
        Fallback: In-memory dict (if Redis unavailable)

        Args:
            did: WhatsApp Business phone number (DID)
            credentials: Decrypted Chattigo credentials

        Returns:
            Valid JWT token string

        Raises:
            ChattigoTokenError: If token cannot be obtained
        """
        async with self._lock:
            # Try Redis first (primary storage)
            redis_repo = await self._ensure_redis()
            cached = await redis_repo.get(did)

            if cached:
                # Check if token needs refresh using tolerance from DB
                if not cached.should_refresh(credentials.token_refresh_hours):
                    logger.debug(f"Token for DID {did} retrieved from Redis (still valid)")
                    return cached.token

                logger.info(
                    f"Token for DID {did} needs refresh "
                    f"(age > {credentials.token_refresh_hours}h)"
                )

            # Need to obtain/refresh token
            return await self._refresh_token(did, credentials)

    async def _refresh_token(
        self, did: str, credentials: ChattigoCredentials
    ) -> str:
        """
        Obtain new token from Chattigo ISV and store in Redis.

        Args:
            did: WhatsApp Business phone number (DID)
            credentials: Decrypted Chattigo credentials

        Returns:
            New JWT token string

        Raises:
            ChattigoTokenError: If authentication fails
        """
        client = await self._get_client()

        try:
            payload = ChattigoLoginRequest(
                username=credentials.username,
                password=credentials.password,
            )

            logger.debug(f"Obtaining token for DID {did} from {credentials.login_url}")

            response = await client.post(
                credentials.login_url,
                json=payload.model_dump(),
            )
            response.raise_for_status()

            # Parse response
            json_data = response.json()
            if not json_data:
                raise ChattigoTokenError(f"Login returned empty response for DID {did}")

            data = ChattigoLoginResponse(**json_data)
            token = data.access_token

            # Calculate timestamps
            now = time.time()
            expiry = now + (self.TOKEN_TTL_HOURS * 3600)

            # Store in Redis with TTL (primary storage)
            redis_repo = await self._ensure_redis()
            token_data = ChattigoTokenData(
                token=token,
                obtained_at=now,
                expiry=expiry,
            )

            # TTL in seconds (8 hours)
            ttl_seconds = int(expiry - now)
            await redis_repo.set(did, token_data, expiration=ttl_seconds)

            logger.info(
                f"Token obtained for DID {did} (stored in Redis), "
                f"next refresh in {credentials.token_refresh_hours}h"
            )

            return token

        except httpx.HTTPError as e:
            logger.error(f"Failed to obtain token for DID {did}: {e}")
            raise ChattigoTokenError(
                f"Authentication failed for DID {did}: {e}"
            ) from e
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse login response for DID {did}: {e}")
            raise ChattigoTokenError(
                f"Login response parsing failed for DID {did}: {e}"
            ) from e

    async def invalidate(self, did: str) -> None:
        """
        Invalidate cached token for DID in Redis.

        Call this after receiving 401 errors to force token refresh.

        Args:
            did: WhatsApp Business phone number (DID)
        """
        # Delete from Redis (primary storage)
        redis_repo = await self._ensure_redis()
        deleted = await redis_repo.delete(did)

        if deleted:
            logger.info(f"Token invalidated in Redis for DID {did}")
        else:
            logger.debug(f"No token found in Redis for DID {did}")

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics for monitoring.

        Note: Returns storage backend info. Individual token stats
        require querying Redis directly (not implemented here).
        """
        return {
            "storage_backend": "redis",
            "redis_prefix": self.REDIS_PREFIX,
            "token_ttl_hours": self.TOKEN_TTL_HOURS,
            "note": "Query Redis directly for individual token stats",
        }
