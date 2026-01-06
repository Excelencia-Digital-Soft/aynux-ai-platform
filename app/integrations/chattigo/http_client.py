# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Cliente HTTP para Chattigo API con retry automático.
#              Implementa Exponential Backoff per ISV Chattigo Section 8.1.
# ============================================================================
"""
Chattigo HTTP Client with Exponential Backoff.

Single Responsibility: Execute HTTP requests with automatic retry on transient errors.

Per Chattigo ISV Documentation (Section 8.1):
- 401 Unauthorized: Refresh token and retry
- 429 Rate Limit: Retry with longer backoff
- 500/502/503/504: Retry with exponential backoff + jitter
- 400/403/etc: Fail immediately (client error)
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .exceptions import ChattigoRateLimitError, ChattigoRetryableError, ChattigoSendError

logger = logging.getLogger(__name__)

# HTTP status codes that warrant retry with exponential backoff
RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})


class ChattigoHttpClient:
    """
    HTTP client for Chattigo API with exponential backoff retry.

    Single Responsibility: Execute HTTP requests with intelligent retry.

    Retry Strategy:
    - 401: Refresh token, retry once
    - 429: Raise ChattigoRateLimitError (caller handles backoff)
    - 5xx: Retry with exponential backoff + jitter (via tenacity)
    - 4xx: Fail immediately (client error, needs code fix)

    Uses persistent AsyncClient for better performance (connection reuse).
    """

    DEFAULT_TIMEOUT = 30.0

    # Retry configuration per ISV Chattigo requirements
    MAX_RETRIES = 3  # Total attempts for 5xx errors
    BASE_DELAY = 1.0  # Initial delay in seconds
    MAX_DELAY = 30.0  # Maximum delay between retries
    JITTER_MAX = 5  # Random jitter up to ±5 seconds

    def __init__(
        self,
        token_provider: Callable[[], Awaitable[str]],
        token_invalidator: Callable[[], Any],  # May return coroutine or None
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize HTTP client.

        Args:
            token_provider: Async callable that returns a valid token
            token_invalidator: Callable to invalidate current token (on 401).
                              May be sync (returns None) or return a coroutine.
            timeout: Request timeout in seconds
        """
        self._get_token = token_provider
        self._token_invalidator = token_invalidator
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _invalidate_token(self) -> None:
        """
        Invalidate the current token.

        Handles both sync and async token invalidators:
        - If invalidator returns a coroutine, it will be awaited
        - If invalidator returns None (sync), it completes immediately
        """
        if self._token_invalidator:
            result = self._token_invalidator()
            # Check if result is a coroutine and await it
            if asyncio.iscoroutine(result):
                await result

    async def initialize(self) -> None:
        """Initialize persistent HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "ChattigoHttpClient":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            await self.initialize()
        return self._client  # type: ignore

    def _get_headers(self, token: str) -> dict[str, str]:
        """Get request headers with authorization."""
        # Chattigo uses raw JWT token without "Bearer" prefix
        return {
            "Authorization": token,
            "Content-Type": "application/json",
        }

    async def post_with_retry(
        self,
        url: str,
        payload: dict,
    ) -> dict:
        """
        POST request with automatic retry on transient errors.

        Implements exponential backoff per Chattigo ISV Section 8.1:
        - 401: Refresh token and retry once
        - 429: Raise rate limit error (caller decides backoff)
        - 5xx: Retry with exponential backoff + jitter
        - 4xx: Fail immediately

        Args:
            url: Target URL
            payload: Request body as dict

        Returns:
            Response dict (empty if no body)

        Raises:
            ChattigoSendError: On persistent failures
            ChattigoRateLimitError: On 429 (caller should handle)
            httpx.HTTPError: On non-retryable HTTP errors
        """
        try:
            return await self._execute_with_backoff(url, payload)
        except RetryError as e:
            # Extract the last exception from tenacity
            last_exception = e.last_attempt.exception()
            if last_exception:
                raise ChattigoSendError(
                    f"Max retries ({self.MAX_RETRIES}) exceeded: {last_exception}"
                ) from last_exception
            raise ChattigoSendError(
                f"Max retries ({self.MAX_RETRIES}) exceeded"
            ) from e

    @retry(
        retry=retry_if_exception_type(ChattigoRetryableError),
        stop=stop_after_attempt(3),  # MAX_RETRIES
        wait=wait_exponential_jitter(
            initial=1.0,  # BASE_DELAY
            max=30.0,  # MAX_DELAY
            jitter=5,  # JITTER_MAX
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _execute_with_backoff(
        self,
        url: str,
        payload: dict,
    ) -> dict:
        """
        Execute request with exponential backoff on 5xx errors.

        This method is decorated with tenacity @retry for automatic
        exponential backoff with jitter on transient server errors.

        Raises:
            ChattigoRetryableError: On 5xx (triggers retry)
            ChattigoRateLimitError: On 429 (caller handles)
            httpx.HTTPStatusError: On 4xx (no retry)
        """
        client = await self._ensure_client()
        token = await self._get_token()

        response = await client.post(
            url,
            headers=self._get_headers(token),
            json=payload,
        )

        # 401: Token expired - refresh and retry once (inline)
        if response.status_code == 401:
            logger.warning("Token expired (401), refreshing...")
            await self._invalidate_token()
            token = await self._get_token()

            # Single retry with new token
            response = await client.post(
                url,
                headers=self._get_headers(token),
                json=payload,
            )

            # If still 401, fail
            if response.status_code == 401:
                raise ChattigoSendError(
                    "Authentication failed after token refresh (401)"
                )

        # 429: Rate limiting - raise specific error for caller to handle
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            logger.warning(f"Rate limited (429), Retry-After: {retry_after}s")
            raise ChattigoRateLimitError(
                f"Rate limited by Chattigo API. Retry after {retry_after}s"
            )

        # 5xx: Server error - raise retryable error (tenacity will retry)
        if response.status_code in RETRYABLE_STATUS_CODES:
            error_preview = response.text[:200] if response.text else "No body"
            logger.warning(
                f"Server error {response.status_code}, will retry: {error_preview}"
            )
            raise ChattigoRetryableError(
                f"Chattigo server error {response.status_code}: {error_preview}"
            )

        # 4xx (except 401, 429): Client error - fail immediately
        response.raise_for_status()

        # Success
        return response.json() if response.text.strip() else {}
