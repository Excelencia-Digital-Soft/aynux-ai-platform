"""
Pharmacy ERP HTTP Client

Async client for external Pharmacy ERP integration.
Uses httpx for async HTTP operations with retry and timeout handling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class PharmacyERPError(Exception):
    """Custom exception for Pharmacy ERP errors."""

    def __init__(self, error_code: str, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(f"{error_code}: {error_message}")


class PharmacyERPClient:
    """
    Async HTTP client for Pharmacy ERP integration.

    Implements IPharmacyERPPort interface for use case injection.
    Uses httpx for modern async HTTP with:
    - Automatic retry with exponential backoff
    - Configurable timeouts
    - Bearer token authentication

    Environment Variables:
        PHARMACY_ERP_BASE_URL: Base URL for ERP API
        PHARMACY_API_TOKEN: Bearer token for authentication
        PHARMACY_ERP_TIMEOUT: Request timeout in seconds (default: 30)

    Example:
        async with PharmacyERPClient() as client:
            debt = await client.get_customer_debt("123456")
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        timeout_seconds: int | None = None,
    ):
        """
        Initialize Pharmacy ERP client.

        Args:
            base_url: Base URL for ERP API (defaults to env PHARMACY_ERP_BASE_URL)
            api_token: Bearer token (defaults to env PHARMACY_API_TOKEN)
            timeout_seconds: Request timeout (defaults to env PHARMACY_ERP_TIMEOUT or 30)
        """
        settings = get_settings()
        self.base_url = (base_url or settings.PHARMACY_ERP_BASE_URL or "").rstrip("/")
        self.api_token = api_token or settings.PHARMACY_API_TOKEN or ""
        self.timeout = timeout_seconds or settings.PHARMACY_ERP_TIMEOUT or 30
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "PharmacyERPClient":
        """Initialize async client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers=self._get_headers(),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Close async client."""
        if self._client:
            await self._client.aclose()

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Aynux-Pharmacy-Bot/1.0",
        }

    def _get_client(self) -> httpx.AsyncClient:
        """Get the async client, raising error if not initialized."""
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with PharmacyERPClient() as client:'"
            )
        return self._client

    async def get_customer_debt(self, customer_id: str) -> dict[str, Any] | None:
        """
        Fetch customer debt from ERP.

        Args:
            customer_id: Customer phone number or ERP ID

        Returns:
            Debt data dict or None if no debt

        Raises:
            PharmacyERPError: On API errors
        """
        client = self._get_client()

        try:
            response = await client.get(f"/api/v1/customers/{customer_id}/debt")
            response.raise_for_status()

            data = response.json()

            # Handle "no debt" case
            if not data.get("has_debt", True):
                return None

            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Customer not found or no debt
                return None
            self._handle_http_error(e)
        except httpx.TimeoutException as e:
            raise PharmacyERPError("TIMEOUT", f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise PharmacyERPError("CONNECTION_ERROR", f"Connection error: {e}") from e
        except Exception as e:
            raise PharmacyERPError("UNEXPECTED", str(e)) from e

        return None  # Should not reach here

    async def confirm_debt(self, debt_id: str, customer_id: str) -> dict[str, Any]:
        """
        Confirm debt in ERP system.

        Args:
            debt_id: Debt identifier
            customer_id: Customer identifier

        Returns:
            Confirmation result

        Raises:
            PharmacyERPError: On API errors
        """
        client = self._get_client()

        try:
            response = await client.post(
                f"/api/v1/debts/{debt_id}/confirm",
                json={"customer_id": customer_id},
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
        except httpx.TimeoutException as e:
            raise PharmacyERPError("TIMEOUT", f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise PharmacyERPError("CONNECTION_ERROR", f"Connection error: {e}") from e
        except Exception as e:
            raise PharmacyERPError("UNEXPECTED", str(e)) from e

        return {}  # Should not reach here

    async def generate_invoice(self, debt_id: str, customer_id: str) -> dict[str, Any]:
        """
        Generate invoice for confirmed debt.

        Args:
            debt_id: Confirmed debt identifier
            customer_id: Customer identifier

        Returns:
            Invoice data with invoice_number and pdf_url

        Raises:
            PharmacyERPError: On API errors
        """
        client = self._get_client()

        try:
            response = await client.post(
                f"/api/v1/debts/{debt_id}/invoice",
                json={"customer_id": customer_id},
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
        except httpx.TimeoutException as e:
            raise PharmacyERPError("TIMEOUT", f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise PharmacyERPError("CONNECTION_ERROR", f"Connection error: {e}") from e
        except Exception as e:
            raise PharmacyERPError("UNEXPECTED", str(e)) from e

        return {}  # Should not reach here

    async def test_connection(self) -> bool:
        """
        Test ERP connectivity.

        Returns:
            True if connection successful, False otherwise
        """
        client = self._get_client()

        try:
            response = await client.get("/api/v1/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Pharmacy ERP connection test failed: {e}")
            return False

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> None:
        """
        Handle HTTP errors and raise appropriate exception.

        Args:
            error: httpx HTTPStatusError

        Raises:
            PharmacyERPError: Always raises with appropriate error code
        """
        status = error.response.status_code

        error_mapping = {
            401: ("AUTH_ERROR", "Invalid API token"),
            403: ("FORBIDDEN", "Access denied"),
            404: ("NOT_FOUND", "Resource not found"),
            422: ("VALIDATION_ERROR", "Validation error"),
            429: ("RATE_LIMIT", "Rate limit exceeded"),
        }

        if status in error_mapping:
            code, message = error_mapping[status]
            raise PharmacyERPError(code, message) from error

        if status >= 500:
            raise PharmacyERPError(
                "SERVER_ERROR", f"ERP server error: {status}"
            ) from error

        # Try to extract error message from response
        try:
            error_data = error.response.json()
            message = error_data.get("message", error_data.get("error", error.response.text))
        except Exception:
            message = error.response.text

        raise PharmacyERPError(f"HTTP_{status}", message) from error


class PharmacyERPClientFactory:
    """Factory for creating PharmacyERPClient instances."""

    @staticmethod
    def create(
        base_url: str | None = None,
        api_token: str | None = None,
        timeout_seconds: int | None = None,
    ) -> PharmacyERPClient:
        """
        Create client with settings from environment.

        Args:
            base_url: Optional override for base URL
            api_token: Optional override for API token
            timeout_seconds: Optional override for timeout

        Returns:
            PharmacyERPClient instance
        """
        return PharmacyERPClient(
            base_url=base_url,
            api_token=api_token,
            timeout_seconds=timeout_seconds,
        )


async def get_pharmacy_erp_client() -> PharmacyERPClient:
    """
    Get a pharmacy ERP client instance.

    This is a dependency injection helper for FastAPI.

    Yields:
        PharmacyERPClient instance

    Example:
        @router.get("/debt")
        async def get_debt(
            customer_id: str,
            client: PharmacyERPClient = Depends(get_pharmacy_erp_client)
        ):
            async with client:
                return await client.get_customer_debt(customer_id)
    """
    return PharmacyERPClient()
