"""
Plex ERP HTTP Client

Async client for Plex ERP integration using HTTP Basic Auth.
Follows DUX client patterns with retry, timeout, and error handling.

Connection Details:
    - Base URL: http://192.168.100.10:8081/wsplex (requires VPN)
    - Auth: HTTP Basic (user: fciacuyo, pass: cuyo202$)

Endpoints:
    - GET /wsplex/clientes - Customer search by phone/document/email/cuit
    - GET /wsplex/saldo_cliente - Balance query by customer ID
    - POST /wsplex/recibo - Create payment receipt
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from app.config.settings import get_settings
from app.domains.pharmacy.domain.entities.plex_customer import PlexCustomer

logger = logging.getLogger(__name__)


class PlexAPIError(Exception):
    """
    Custom exception for Plex ERP errors.

    Attributes:
        error_code: Machine-readable error code (e.g., AUTH_ERROR, TIMEOUT)
        error_message: Human-readable error description
    """

    def __init__(self, error_code: str, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(f"{error_code}: {error_message}")


class PlexConnectionError(PlexAPIError):
    """Network/VPN connectivity issues."""

    def __init__(self, message: str):
        super().__init__("CONNECTION_ERROR", message)


class PlexAuthenticationError(PlexAPIError):
    """HTTP Basic Auth failed."""

    def __init__(self, message: str = "Invalid credentials"):
        super().__init__("AUTH_ERROR", message)


class PlexClient:
    """
    Async HTTP client for Plex ERP integration.

    Implements customer search, balance queries, and receipt creation
    using HTTP Basic Auth over httpx.

    Environment Variables:
        PLEX_API_BASE_URL: Base URL for Plex API
        PLEX_API_USER: HTTP Basic Auth username
        PLEX_API_PASS: HTTP Basic Auth password
        PLEX_API_TIMEOUT: Request timeout in seconds (default: 30)

    Example:
        async with PlexClient() as client:
            customers = await client.search_customer(phone="3446405060")
            if customers:
                balance = await client.get_customer_balance(customers[0].id)
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: int | None = None,
    ):
        """
        Initialize Plex ERP client.

        Args:
            base_url: Base URL for Plex API (defaults to env PLEX_API_BASE_URL)
            username: HTTP Basic Auth username (defaults to env PLEX_API_USER)
            password: HTTP Basic Auth password (defaults to env PLEX_API_PASS)
            timeout_seconds: Request timeout (defaults to env PLEX_API_TIMEOUT or 30)
        """
        settings = get_settings()
        self.base_url = (base_url or settings.PLEX_API_BASE_URL or "").rstrip("/")
        self.username = username or settings.PLEX_API_USER or ""
        self.password = password or settings.PLEX_API_PASS or ""
        self.timeout = timeout_seconds or settings.PLEX_API_TIMEOUT or 30
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> PlexClient:
        """Initialize async client with HTTP Basic Auth."""
        auth = httpx.BasicAuth(self.username, self.password)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            auth=auth,
            headers={
                "Accept": "application/json",
                "User-Agent": "Aynux-Pharmacy-Bot/1.0",
            },
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

    def _get_client(self) -> httpx.AsyncClient:
        """Get the async client, raising error if not initialized."""
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with PlexClient() as client:'")
        return self._client

    # =========================================================================
    # Customer Search Methods
    # =========================================================================

    async def search_customer(
        self,
        phone: str | None = None,
        document: str | None = None,
        email: str | None = None,
        cuit: str | None = None,
        customer_id: int | None = None,
    ) -> list[PlexCustomer]:
        """
        Search for customers by criteria.

        Priority order: customer_id > phone > document > email > cuit

        Args:
            phone: Phone number (will be normalized)
            document: Document number (DNI)
            email: Email address
            cuit: Tax ID
            customer_id: Direct Plex customer ID

        Returns:
            List of matching customers (may be empty or have multiple)

        Raises:
            PlexAPIError: On API errors
        """
        client = self._get_client()

        # Build query params based on priority
        params: dict[str, str] = {}
        if customer_id is not None:
            params["id"] = str(customer_id)
        elif phone:
            normalized = self._normalize_phone(phone)
            params["telefono"] = normalized
            logger.debug(f"Searching Plex customer by phone: {normalized}")
        elif document:
            params["nro_doc"] = document
            logger.debug(f"Searching Plex customer by document: {document}")
        elif email:
            params["email"] = email
        elif cuit:
            params["cuit"] = cuit
        else:
            logger.warning("search_customer called without any criteria")
            return []

        try:
            logger.info(f"Plex customer search: params={params}")
            response = await client.get("/clientes", params=params)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Plex search response: {data}")

            # Unwrap nested PLEX response structure
            # API returns: {"response": {"respcode": "0", "content": {"clientes": [...]}}}
            if isinstance(data, dict) and "response" in data:
                response_data = data.get("response", {})
                respcode = response_data.get("respcode", "")
                respmsg = response_data.get("respmsg", "")

                # respcode "0" = success, non-zero = no results or error
                # "No se encontró" messages are not errors, just empty results
                if respcode != "0":
                    if "no se encontr" in respmsg.lower():
                        logger.debug(f"Plex search returned no results: {respmsg}")
                        return []
                    # Other non-zero codes are real errors
                    raise PlexAPIError("API_ERROR", respmsg or "Unknown error")

                content = response_data.get("content", {})
                clientes = content.get("clientes", [])
                return [PlexCustomer.from_plex_response(c) for c in clientes]
            elif isinstance(data, list):
                return [PlexCustomer.from_plex_response(c) for c in data]
            elif isinstance(data, dict) and data.get("idcliente"):
                return [PlexCustomer.from_plex_response(data)]
            return []

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
        except httpx.TimeoutException as e:
            raise PlexConnectionError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error (VPN?): {e}") from e
        except Exception as e:
            raise PlexAPIError("UNEXPECTED", str(e)) from e

        return []

    # =========================================================================
    # Balance Query Methods
    # =========================================================================

    async def get_customer_balance(
        self,
        customer_id: int,
        detailed: bool = True,
        fecha_hasta: date | None = None,
    ) -> dict[str, Any] | None:
        """
        Get customer balance/debt details.

        Args:
            customer_id: Plex internal customer ID
            detailed: True for line items (detallado=S), False for summary
            fecha_hasta: Cutoff date (defaults to today)

        Returns:
            Balance data dict or None if no balance found

        Raises:
            PlexAPIError: On API errors
        """
        client = self._get_client()

        if fecha_hasta is None:
            fecha_hasta = date.today()

        params = {
            "idcliente": str(customer_id),
            "fecha_hasta": fecha_hasta.strftime("%Y%m%d"),
            "detallado": "S" if detailed else "N",
        }

        try:
            logger.info(f"Plex balance query: customer_id={customer_id}")
            response = await client.get("/saldo_cliente", params=params)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Plex balance response: {data}")

            # Unwrap nested PLEX response structure
            # API returns: {"response": {"respcode": "0", "content": {...}}}
            if isinstance(data, dict) and "response" in data:
                response_data = data.get("response", {})
                respcode = response_data.get("respcode", "")
                respmsg = response_data.get("respmsg", "")

                if respcode != "0":
                    if "no se encontr" in respmsg.lower():
                        logger.debug(f"Plex balance returned no results: {respmsg}")
                        return None
                    raise PlexAPIError("API_ERROR", respmsg or "Unknown error")

                content = response_data.get("content", {})

                # Parse saldo - may be in "33642016,50" format (comma as decimal)
                saldo_str = content.get("saldo", "0")
                if isinstance(saldo_str, str):
                    saldo_str = saldo_str.replace(",", ".")
                    try:
                        content["saldo"] = float(saldo_str)
                    except ValueError:
                        content["saldo"] = 0

                # Parse items amounts and extract additional fields
                items = content.get("items", [])
                for item in items:
                    # Parse adeudado amount (comma as decimal separator)
                    adeudado = item.get("adeudado", "0")
                    if isinstance(adeudado, str):
                        adeudado = adeudado.replace(",", ".")
                        try:
                            item["importe"] = float(adeudado)
                        except ValueError:
                            item["importe"] = 0
                    item["descripcion"] = item.get("detalle", "Item")

                    # Extract comprobante (invoice number)
                    item["comprobante"] = item.get("comprobante", "")

                    # Parse fecha (YYYYMMDD → YYYY-MM-DD)
                    fecha_raw = item.get("fecha", "")
                    if fecha_raw and len(fecha_raw) == 8:
                        item["fecha"] = f"{fecha_raw[:4]}-{fecha_raw[4:6]}-{fecha_raw[6:8]}"
                    else:
                        item["fecha"] = fecha_raw

                content["detalle"] = items
                return content

            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            self._handle_http_error(e)
        except httpx.TimeoutException as e:
            raise PlexConnectionError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error (VPN?): {e}") from e
        except Exception as e:
            raise PlexAPIError("UNEXPECTED", str(e)) from e

        return None

    # =========================================================================
    # Receipt/Payment Methods
    # =========================================================================

    async def create_receipt(
        self,
        customer_id: int,
        amount: Decimal,
        items: list[dict[str, Any]] | None = None,
        fecha: date | None = None,
    ) -> dict[str, Any]:
        """
        Create a payment receipt in Plex ERP.

        Args:
            customer_id: Plex internal customer ID
            amount: Total payment amount
            items: List of payment items/details (optional)
            fecha: Receipt date (defaults to today)

        Returns:
            Receipt confirmation data

        Raises:
            PlexAPIError: On API errors
        """
        client = self._get_client()

        if fecha is None:
            fecha = date.today()

        payload = {
            "idcliente": customer_id,
            "fecha": fecha.strftime("%Y-%m-%d"),
            "monto": float(amount),
        }

        if items:
            payload["items"] = items

        try:
            logger.info(f"Plex create receipt: customer_id={customer_id}, amount={amount}")
            response = await client.post("/recibo", json=payload)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Plex receipt created: {data}")
            return data

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
        except httpx.TimeoutException as e:
            raise PlexConnectionError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error (VPN?): {e}") from e
        except Exception as e:
            raise PlexAPIError("UNEXPECTED", str(e)) from e

        return {}

    async def register_payment(
        self,
        customer_id: int,
        amount: float,
        operation_number: str,
    ) -> dict[str, Any]:
        """
        Register a payment in Plex ERP using REGISTRAR_PAGO_CLIENTE.

        This endpoint records a payment made through an external payment processor
        (like Mercado Pago) in the Plex ERP system.

        Args:
            customer_id: Plex internal customer ID
            amount: Payment amount
            operation_number: External operation number (e.g., Mercado Pago payment ID)

        Returns:
            dict with:
                - respcode: "0" for success
                - respmsg: "OK" for success
                - content:
                    - idcliente: Customer ID
                    - acreditado: Amount credited
                    - comprobante: PLEX receipt number (e.g., "RC X 0001-00016790")
                    - nuevo_saldo: New customer balance

        Raises:
            PlexAPIError: On API errors or registration failure

        Example:
            async with PlexClient() as client:
                result = await client.register_payment(
                    customer_id=697,
                    amount=50000.00,
                    operation_number="123456789",  # MP payment ID
                )
                # result["content"]["comprobante"] = "RC X 0001-00016790"
        """
        client = self._get_client()

        payload = {
            "request": {
                "type": "REGISTRAR_PAGO_CLIENTE",
                "content": {
                    "idcliente": str(customer_id),
                    "importe": str(amount),
                    "nro_operacion": operation_number,
                },
            }
        }

        try:
            logger.info(
                f"Plex register payment: customer_id={customer_id}, "
                f"amount={amount}, operation={operation_number}"
            )
            response = await client.post("/saldo_cliente", json=payload)
            response.raise_for_status()

            data = response.json()

            # Validate response
            resp = data.get("response", {})
            if resp.get("respcode") != "0":
                error_msg = resp.get("respmsg", "Unknown error")
                logger.error(f"Plex payment registration failed: {error_msg}")
                raise PlexAPIError("PAYMENT_REGISTRATION_FAILED", error_msg)

            content = resp.get("content", {})
            logger.info(
                f"Plex payment registered: customer={customer_id}, "
                f"receipt={content.get('comprobante')}, "
                f"new_balance={content.get('nuevo_saldo')}"
            )

            return resp

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
        except httpx.TimeoutException as e:
            raise PlexConnectionError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error (VPN?): {e}") from e
        except PlexAPIError:
            raise
        except Exception as e:
            raise PlexAPIError("UNEXPECTED", str(e)) from e

        return {}

    # =========================================================================
    # Customer Registration Methods
    # =========================================================================

    async def create_customer(
        self,
        nombre: str,
        documento: str,
        telefono: str,
        email: str | None = None,
        direccion: str | None = None,
    ) -> PlexCustomer:
        """
        Register a new customer in Plex ERP.

        Args:
            nombre: Customer full name
            documento: Document number (DNI)
            telefono: Phone number
            email: Email address (optional)
            direccion: Address (optional)

        Returns:
            Created PlexCustomer instance

        Raises:
            PlexAPIError: On API errors or if endpoint not supported
        """
        client = self._get_client()

        payload = {
            "nombre": nombre.upper(),
            "documento": documento,
            "telefono": self._normalize_phone(telefono),
        }

        if email:
            payload["email"] = email
        if direccion:
            payload["direccion"] = direccion

        try:
            logger.info(f"Plex create customer: nombre={nombre}, doc={documento}")
            response = await client.post("/clientes", json=payload)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Plex customer created: {data}")
            return PlexCustomer.from_plex_response(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 405:
                raise PlexAPIError("NOT_SUPPORTED", "Customer registration not supported by this Plex instance") from e
            self._handle_http_error(e)
        except httpx.TimeoutException as e:
            raise PlexConnectionError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise PlexConnectionError(f"Connection error (VPN?): {e}") from e
        except Exception as e:
            raise PlexAPIError("UNEXPECTED", str(e)) from e

        # Should not reach here
        raise PlexAPIError("UNEXPECTED", "Failed to create customer")

    # =========================================================================
    # Connection Test
    # =========================================================================

    async def test_connection(self) -> bool:
        """
        Test Plex connectivity.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Search for a non-existent customer to test auth and connectivity
            await self.search_customer(document="__test_connection__")
            return True
        except PlexAPIError as e:
            if e.error_code == "NOT_FOUND":
                return True  # API works, just no match
            logger.error(f"Plex connection test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Plex connection test failed: {e}")
            return False

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number for Plex search.

        Converts WhatsApp format to local format:
            WhatsApp: 5493446405060 or +5493446405060
            Plex expects: 3446405060 (local without country code)

        Args:
            phone: Phone number in any format

        Returns:
            Normalized phone number for Plex
        """
        # Remove all non-digits
        digits = re.sub(r"\D", "", phone)

        # Remove Argentina country code variations
        if digits.startswith("549") and len(digits) > 10:
            digits = digits[3:]  # Remove 549
        elif digits.startswith("54") and len(digits) > 10:
            digits = digits[2:]  # Remove 54

        return digits

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> None:
        """
        Handle HTTP errors and raise appropriate exception.

        Args:
            error: httpx HTTPStatusError

        Raises:
            PlexAPIError: Always raises with appropriate error code
        """
        status = error.response.status_code

        error_mapping = {
            401: ("AUTH_ERROR", "Invalid credentials - check PLEX_API_USER/PLEX_API_PASS"),
            403: ("FORBIDDEN", "Access denied - user lacks permissions"),
            404: ("NOT_FOUND", "Resource not found"),
            422: ("VALIDATION_ERROR", "Invalid request data"),
            429: ("RATE_LIMIT", "Rate limit exceeded - try again later"),
        }

        if status in error_mapping:
            code, message = error_mapping[status]
            if status == 401:
                raise PlexAuthenticationError(message) from error
            raise PlexAPIError(code, message) from error

        if status >= 500:
            raise PlexAPIError("SERVER_ERROR", f"Plex server error: {status}") from error

        # Try to extract error message from response
        try:
            error_data = error.response.json()
            message = error_data.get("message", error_data.get("error", error.response.text))
        except Exception:
            message = error.response.text

        raise PlexAPIError(f"HTTP_{status}", message) from error


class PlexClientFactory:
    """Factory for creating PlexClient instances."""

    @staticmethod
    def create(
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: int | None = None,
    ) -> PlexClient:
        """
        Create client with settings from environment.

        Args:
            base_url: Optional override for base URL
            username: Optional override for username
            password: Optional override for password
            timeout_seconds: Optional override for timeout

        Returns:
            PlexClient instance
        """
        return PlexClient(
            base_url=base_url,
            username=username,
            password=password,
            timeout_seconds=timeout_seconds,
        )


async def get_plex_client() -> PlexClient:
    """
    Get a Plex client instance.

    This is a dependency injection helper for FastAPI.

    Returns:
        PlexClient instance (use as context manager)

    Example:
        @router.get("/customer")
        async def get_customer(
            phone: str,
            client: PlexClient = Depends(get_plex_client)
        ):
            async with client:
                return await client.search_customer(phone=phone)
    """
    return PlexClient()
