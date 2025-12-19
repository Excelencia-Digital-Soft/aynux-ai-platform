"""
Mercado Pago API Client

Async client for Mercado Pago payment processing using Bearer Token auth.
Uses Checkout Pro (Preferences) for generating payment links.

Connection Details:
    - Base URL: https://api.mercadopago.com
    - Auth: Bearer Token (Access Token)

Endpoints:
    - POST /checkout/preferences - Create payment preference (link)
    - GET /v1/payments/{id} - Get payment details

Documentation:
    - https://www.mercadopago.com.ar/developers/en/docs/checkout-pro/overview
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import httpx

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class MercadoPagoError(Exception):
    """
    Base exception for Mercado Pago errors.

    Attributes:
        error_code: Machine-readable error code
        error_message: Human-readable error description
    """

    def __init__(self, error_code: str, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(f"{error_code}: {error_message}")


class MercadoPagoAuthError(MercadoPagoError):
    """Authentication error (invalid access token)."""

    def __init__(self, message: str = "Invalid access token"):
        super().__init__("AUTH_ERROR", message)


class MercadoPagoConnectionError(MercadoPagoError):
    """Network connectivity issues."""

    def __init__(self, message: str):
        super().__init__("CONNECTION_ERROR", message)


class MercadoPagoValidationError(MercadoPagoError):
    """Request validation error."""

    def __init__(self, message: str):
        super().__init__("VALIDATION_ERROR", message)


class MercadoPagoClient:
    """
    Async HTTP client for Mercado Pago API.

    Implements payment preference creation and payment status queries
    using Bearer Token authentication over httpx.

    Environment Variables:
        MERCADO_PAGO_ENABLED: Enable/disable MP integration
        MERCADO_PAGO_ACCESS_TOKEN: Bearer token for API auth
        MERCADO_PAGO_SANDBOX: Use sandbox mode for testing
        MERCADO_PAGO_TIMEOUT: Request timeout in seconds (default: 30)
        MERCADO_PAGO_NOTIFICATION_URL: Webhook URL for payment notifications

    Example:
        async with MercadoPagoClient() as client:
            preference = await client.create_preference(
                amount=Decimal("1500.00"),
                description="Pago de deuda",
                external_reference="customer123:debt456",
            )
            # preference["init_point"] contains the payment URL
    """

    BASE_URL = "https://api.mercadopago.com"
    SANDBOX_BASE_URL = "https://api.mercadopago.com"  # Same URL, different behavior

    def __init__(self):
        """Initialize Mercado Pago client with settings."""
        settings = get_settings()

        if not settings.MERCADO_PAGO_ENABLED:
            logger.warning("MercadoPagoClient initialized but MERCADO_PAGO_ENABLED=false")

        self._access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
        self._notification_url = settings.MERCADO_PAGO_NOTIFICATION_URL
        self._timeout = settings.MERCADO_PAGO_TIMEOUT
        self._sandbox = settings.MERCADO_PAGO_SANDBOX
        self._client: httpx.AsyncClient | None = None

        if not self._access_token:
            logger.error("MERCADO_PAGO_ACCESS_TOKEN not configured")

    async def __aenter__(self) -> MercadoPagoClient:
        """Enter async context and create HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
                "X-Idempotency-Key": None,  # Will be set per-request if needed
            },
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *args) -> None:
        """Exit async context and close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def create_preference(
        self,
        amount: Decimal,
        description: str,
        external_reference: str,
        payer_email: str | None = None,
        payer_phone: str | None = None,
        payer_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a Checkout Pro preference (payment link).

        This generates a payment URL that customers can use to pay through
        Mercado Pago's checkout experience.

        Args:
            amount: Payment amount in local currency (ARS)
            description: Payment description shown to customer
            external_reference: Your internal reference for correlation (e.g., "customer_id:debt_id:uuid")
            payer_email: Optional payer email for pre-filling checkout
            payer_phone: Optional payer phone (WhatsApp number)
            payer_name: Optional payer name for pre-filling

        Returns:
            dict with:
                - preference_id: Mercado Pago preference ID
                - init_point: Production payment URL
                - sandbox_init_point: Sandbox payment URL (for testing)

        Raises:
            MercadoPagoAuthError: Invalid access token
            MercadoPagoValidationError: Invalid request parameters
            MercadoPagoConnectionError: Network error
        """
        if not self._client:
            raise MercadoPagoError("CLIENT_NOT_INITIALIZED", "Client not initialized. Use 'async with' context.")

        if amount <= 0:
            raise MercadoPagoValidationError("Amount must be greater than zero")

        payload: dict[str, Any] = {
            "items": [
                {
                    "title": description,
                    "quantity": 1,
                    "unit_price": float(amount),
                    "currency_id": "ARS",
                }
            ],
            "external_reference": external_reference,
            "auto_return": "approved",
            "expires": True,
            "expiration_date_from": None,  # Will use default (now)
            "expiration_date_to": None,  # Will use default (24h)
        }

        # Add notification URL if configured
        if self._notification_url:
            payload["notification_url"] = self._notification_url
            payload["back_urls"] = {
                "success": f"{self._notification_url}/success",
                "failure": f"{self._notification_url}/failure",
                "pending": f"{self._notification_url}/pending",
            }

        # Add payer info if provided
        if payer_email or payer_phone or payer_name:
            payload["payer"] = {}
            if payer_email:
                payload["payer"]["email"] = payer_email
            if payer_name:
                payload["payer"]["name"] = payer_name
            if payer_phone:
                payload["payer"]["phone"] = {"number": payer_phone}

        try:
            logger.info(f"Creating MP preference: amount={amount}, ref={external_reference}")

            response = await self._client.post("/checkout/preferences", json=payload)

            if response.status_code == 401:
                raise MercadoPagoAuthError("Invalid or expired access token")

            if response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get("message", "Validation error")
                raise MercadoPagoValidationError(error_msg)

            response.raise_for_status()

            data = response.json()
            preference_id = data.get("id")

            logger.info(f"MP preference created: {preference_id}")

            return {
                "preference_id": preference_id,
                "init_point": data.get("init_point"),
                "sandbox_init_point": data.get("sandbox_init_point"),
            }

        except httpx.ConnectError as e:
            logger.error(f"MP connection error: {e}")
            raise MercadoPagoConnectionError(f"Could not connect to Mercado Pago: {e}") from e

        except httpx.TimeoutException as e:
            logger.error(f"MP timeout error: {e}")
            raise MercadoPagoConnectionError(f"Mercado Pago request timed out: {e}") from e

    async def get_payment(self, payment_id: str) -> dict[str, Any]:
        """
        Get payment details by ID.

        Used to verify payment status after receiving a webhook notification.

        Args:
            payment_id: Mercado Pago payment ID

        Returns:
            dict with payment details including:
                - id: Payment ID
                - status: Payment status (approved, pending, rejected, etc.)
                - status_detail: Detailed status description
                - transaction_amount: Amount paid
                - external_reference: Your reference for correlation
                - payer: Payer information

        Raises:
            MercadoPagoAuthError: Invalid access token
            MercadoPagoError: Payment not found or other error
        """
        if not self._client:
            raise MercadoPagoError("CLIENT_NOT_INITIALIZED", "Client not initialized. Use 'async with' context.")

        try:
            logger.info(f"Fetching MP payment: {payment_id}")

            response = await self._client.get(f"/v1/payments/{payment_id}")

            if response.status_code == 401:
                raise MercadoPagoAuthError("Invalid or expired access token")

            if response.status_code == 404:
                raise MercadoPagoError("NOT_FOUND", f"Payment {payment_id} not found")

            response.raise_for_status()

            data = response.json()
            logger.info(f"MP payment {payment_id} status: {data.get('status')}")

            return data

        except httpx.ConnectError as e:
            logger.error(f"MP connection error: {e}")
            raise MercadoPagoConnectionError(f"Could not connect to Mercado Pago: {e}") from e

        except httpx.TimeoutException as e:
            logger.error(f"MP timeout error: {e}")
            raise MercadoPagoConnectionError(f"Mercado Pago request timed out: {e}") from e

    async def test_connection(self) -> bool:
        """
        Test API connection and credentials.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._client:
            return False

        try:
            # Simple endpoint to test auth
            response = await self._client.get("/users/me")
            return response.status_code == 200

        except Exception as e:
            logger.error(f"MP connection test failed: {e}")
            return False

    @property
    def is_sandbox(self) -> bool:
        """Check if client is in sandbox mode."""
        return self._sandbox

    @property
    def is_enabled(self) -> bool:
        """Check if MP integration is enabled."""
        settings = get_settings()
        return settings.MERCADO_PAGO_ENABLED and bool(self._access_token)
