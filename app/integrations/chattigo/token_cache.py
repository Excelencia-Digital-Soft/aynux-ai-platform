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

from .exceptions import ChattigoTokenError
from .models import ChattigoLoginRequest, ChattigoLoginResponse

logger = logging.getLogger(__name__)


class ChattigoTokenCache:
    """
    In-memory cache for Chattigo JWT tokens with auto-refresh per DID.

    Each DID maintains its own token with independent refresh timing.
    Tokens are refreshed before expiration based on token_refresh_hours setting.

    Thread-safe via asyncio.Lock per DID operation.
    """

    # Token TTL: 8 hours (per Chattigo ISV spec)
    TOKEN_TTL_HOURS = 8

    def __init__(self) -> None:
        """Initialize token cache."""
        # {did: (token, expiry_timestamp)}
        self._tokens: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for token requests."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client and clear cache."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._tokens.clear()

    async def get_token(
        self, did: str, credentials: ChattigoCredentials
    ) -> str:
        """
        Get valid token for DID, refreshing if needed.

        Token refresh occurs at (TTL - (TTL - refresh_hours)) from expiry,
        which means refresh happens `refresh_hours` after token was obtained.

        Args:
            did: WhatsApp Business phone number (DID)
            credentials: Decrypted Chattigo credentials

        Returns:
            Valid JWT token string

        Raises:
            ChattigoTokenError: If token cannot be obtained
        """
        async with self._lock:
            cached = self._tokens.get(did)

            if cached:
                token, expiry = cached
                # Calculate when to refresh: refresh_hours after token was obtained
                # Token was obtained at: expiry - TTL_HOURS * 3600
                token_obtained_at = expiry - (self.TOKEN_TTL_HOURS * 3600)
                refresh_at = token_obtained_at + (credentials.token_refresh_hours * 3600)

                if time.time() < refresh_at:
                    return token  # Token still valid

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
        Obtain new token from Chattigo ISV.

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

            # Store with expiry (8 hours from now)
            expiry = time.time() + (self.TOKEN_TTL_HOURS * 3600)
            self._tokens[did] = (token, expiry)

            logger.info(
                f"Token obtained for DID {did}, "
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

    def invalidate(self, did: str) -> None:
        """
        Invalidate cached token for DID.

        Call this after receiving 401 errors to force token refresh.

        Args:
            did: WhatsApp Business phone number (DID)
        """
        if did in self._tokens:
            del self._tokens[did]
            logger.info(f"Token invalidated for DID {did}")

    def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        now = time.time()
        dids_list: list[dict] = []
        for did, (_, expiry) in self._tokens.items():
            remaining = max(0, expiry - now)
            dids_list.append({
                "did": did,
                "expires_in_seconds": int(remaining),
                "expires_in_hours": round(remaining / 3600, 2),
            })
        return {
            "total_cached": len(self._tokens),
            "dids": dids_list,
        }
