"""
WhatsApp HTTP Client.

Single Responsibility: Handle HTTP communication with WhatsApp Business API.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WhatsAppHttpClient:
    """
    HTTP client for WhatsApp Business API.

    Single Responsibility: Execute HTTP requests to WhatsApp API.
    """

    def __init__(
        self,
        base_url: str,
        version: str,
        phone_number_id: str,
        access_token: str,
        timeout: float = 30.0,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: WhatsApp API base URL
            version: API version
            phone_number_id: Phone number ID for sending messages
            access_token: Bearer token for authentication
            timeout: Request timeout in seconds
        """
        self._base_url = base_url
        self._version = version
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._timeout = timeout

    @property
    def message_url(self) -> str:
        """Get URL for sending messages."""
        return f"{self._base_url}/{self._version}/{self._phone_number_id}/messages"

    def get_url(self, endpoint: str) -> str:
        """Build URL for an endpoint."""
        return f"{self._base_url}/{self._version}/{endpoint}"

    @property
    def headers(self) -> dict[str, str]:
        """Get standard headers for requests."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def post(
        self,
        payload: dict[str, Any],
        endpoint: str = "messages",
    ) -> dict[str, Any]:
        """
        Execute POST request to WhatsApp API.

        Args:
            payload: Request payload
            endpoint: API endpoint (default: messages)

        Returns:
            Response dictionary with success/error status
        """
        url = self.message_url if endpoint == "messages" else self.get_url(endpoint)

        try:
            logger.debug(f"POST {url}")

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=self.headers)

                logger.info(f"WhatsApp API Response: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Request successful: {result}")
                    return {"success": True, "data": result}
                else:
                    return self._handle_error_response(response)

        except httpx.TimeoutException:
            return {"success": False, "error": "Timeout connecting to WhatsApp API"}
        except httpx.ConnectError:
            return {"success": False, "error": "Connection error with WhatsApp API"}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute GET request to WhatsApp API.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            Response dictionary with success/error status
        """
        url = self.get_url(endpoint)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=self.headers, params=params)

                if response.status_code == 200:
                    return {"success": True, "data": response.json()}
                else:
                    return self._handle_error_response(response)

        except Exception as e:
            logger.error(f"GET request failed: {e}")
            return {"success": False, "error": str(e)}

    def _handle_error_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle error response from API."""
        error_detail = response.text
        logger.error(f"Error {response.status_code}: {error_detail}")

        try:
            error_json = response.json()
            error_message = error_json.get("error", {}).get("message", error_detail)
        except Exception:
            error_message = error_detail

        return {
            "success": False,
            "error": f"HTTP {response.status_code}: {error_message}",
            "status_code": response.status_code,
        }
