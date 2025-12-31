# ============================================================================
# Tests for Chattigo HTTP Client with Exponential Backoff
# ============================================================================
"""
Tests for ChattigoHttpClient.

Verifies:
- Exponential backoff on 5xx errors (ISV Chattigo Section 8.1)
- Token refresh on 401
- Rate limiting handling (429)
- Immediate failure on 4xx
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.integrations.chattigo.http_client import (
    ChattigoHttpClient,
    RETRYABLE_STATUS_CODES,
)
from app.integrations.chattigo.exceptions import (
    ChattigoRetryableError,
    ChattigoRateLimitError,
    ChattigoSendError,
)


class TestChattigoHttpClientRetry:
    """Test retry behavior for different HTTP status codes."""

    @pytest.fixture
    def mock_token_provider(self):
        """Mock token provider that returns a valid token."""
        return AsyncMock(return_value="test_token_123")

    @pytest.fixture
    def mock_token_invalidator(self):
        """Mock token invalidator."""
        return MagicMock()

    @pytest.fixture
    def client(self, mock_token_provider, mock_token_invalidator):
        """Create HTTP client with mocked dependencies."""
        return ChattigoHttpClient(
            token_provider=mock_token_provider,
            token_invalidator=mock_token_invalidator,
        )

    @pytest.mark.asyncio
    async def test_successful_request_returns_json(self, client):
        """Test that successful requests return JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            mock_ensure.return_value = mock_http_client

            result = await client.post_with_retry(
                url="https://api.chattigo.com/test",
                payload={"message": "hello"},
            )

        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_401_triggers_token_refresh(self, client, mock_token_invalidator):
        """Test that 401 response triggers token refresh and retry."""
        # First call returns 401, second returns 200
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.text = '{"status": "ok"}'
        mock_response_200.json.return_value = {"status": "ok"}

        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http_client = AsyncMock()
            mock_http_client.post.side_effect = [mock_response_401, mock_response_200]
            mock_ensure.return_value = mock_http_client

            result = await client.post_with_retry(
                url="https://api.chattigo.com/test",
                payload={"message": "hello"},
            )

        # Token should be invalidated on 401
        mock_token_invalidator.assert_called_once()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_error(self, client):
        """Test that 429 response raises ChattigoRateLimitError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "120"}

        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            mock_ensure.return_value = mock_http_client

            with pytest.raises(ChattigoRateLimitError) as exc_info:
                await client.post_with_retry(
                    url="https://api.chattigo.com/test",
                    payload={"message": "hello"},
                )

        assert "Rate limited" in str(exc_info.value)
        assert "120" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_500_retries_with_exponential_backoff(self, client):
        """Test that 500 response triggers exponential backoff retries."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            mock_ensure.return_value = mock_http_client

            # After max retries (3), tenacity reraises the last exception
            with pytest.raises(ChattigoRetryableError) as exc_info:
                await client.post_with_retry(
                    url="https://api.chattigo.com/test",
                    payload={"message": "hello"},
                )

        # Verify the error message
        assert "500" in str(exc_info.value)

        # Verify retry happened (3 attempts = MAX_RETRIES)
        assert mock_http_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_400_fails_immediately_no_retry(self, client):
        """Test that 400 response fails immediately without retry."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="Bad Request",
            request=MagicMock(),
            response=mock_response,
        )

        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            mock_ensure.return_value = mock_http_client

            with pytest.raises(httpx.HTTPStatusError):
                await client.post_with_retry(
                    url="https://api.chattigo.com/test",
                    payload={"message": "hello"},
                )

        # Should only be called once (no retry)
        assert mock_http_client.post.call_count == 1


class TestRetryableStatusCodes:
    """Test that correct status codes are marked as retryable."""

    def test_500_is_retryable(self):
        assert 500 in RETRYABLE_STATUS_CODES

    def test_502_is_retryable(self):
        assert 502 in RETRYABLE_STATUS_CODES

    def test_503_is_retryable(self):
        assert 503 in RETRYABLE_STATUS_CODES

    def test_504_is_retryable(self):
        assert 504 in RETRYABLE_STATUS_CODES

    def test_400_is_not_retryable(self):
        assert 400 not in RETRYABLE_STATUS_CODES

    def test_401_is_not_retryable(self):
        # 401 has special handling (token refresh), not in RETRYABLE_STATUS_CODES
        assert 401 not in RETRYABLE_STATUS_CODES

    def test_429_is_not_retryable(self):
        # 429 has special handling (rate limit), not in RETRYABLE_STATUS_CODES
        assert 429 not in RETRYABLE_STATUS_CODES


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_retryable_error_is_send_error(self):
        """ChattigoRetryableError should inherit from ChattigoSendError."""
        error = ChattigoRetryableError("test")
        assert isinstance(error, ChattigoSendError)

    def test_rate_limit_error_is_send_error(self):
        """ChattigoRateLimitError should inherit from ChattigoSendError."""
        error = ChattigoRateLimitError("test")
        assert isinstance(error, ChattigoSendError)
