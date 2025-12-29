# ============================================================================
# SCOPE: GLOBAL
# Description: Cliente HTTP para Ollama API. Proporciona acceso a /api/tags
#              y /api/show para listar modelos y obtener información detallada.
# ============================================================================
"""
Ollama HTTP Client - Integration layer for Ollama API.

Single Responsibility: HTTP communication with Ollama service.
No business logic - just API calls and response mapping.

Usage:
    client = OllamaClient(base_url="http://localhost:11434")

    # List all models
    models = await client.list_models()

    # Get model details
    info = await client.get_model_info("llama3.2:3b")

    # Health check
    is_healthy = await client.health_check()
"""

import logging
from dataclasses import dataclass

import httpx

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class OllamaClientError(Exception):
    """Base exception for Ollama client errors."""

    pass


class OllamaConnectionError(OllamaClientError):
    """Raised when connection to Ollama fails."""

    pass


class OllamaAPIError(OllamaClientError):
    """Raised when Ollama API returns an error."""

    pass


@dataclass
class OllamaModelInfo:
    """Model information from /api/tags."""

    name: str
    family: str
    families: list[str]
    parameter_size: str | None
    quantization_level: str | None
    size_bytes: int | None
    modified_at: str | None

    @classmethod
    def from_api_response(cls, data: dict) -> "OllamaModelInfo":
        """Create from Ollama /api/tags response."""
        details = data.get("details", {})
        return cls(
            name=data.get("name", ""),
            family=details.get("family", ""),
            families=details.get("families", []),
            parameter_size=details.get("parameter_size"),
            quantization_level=details.get("quantization_level"),
            size_bytes=data.get("size"),
            modified_at=data.get("modified_at"),
        )


@dataclass
class OllamaModelDetails:
    """Detailed model information from /api/show."""

    capabilities: list[str]
    model_info: dict
    template: str | None
    parameters: str | None
    license: str | None

    @classmethod
    def from_api_response(cls, data: dict) -> "OllamaModelDetails":
        """Create from Ollama /api/show response."""
        return cls(
            capabilities=data.get("capabilities", []),
            model_info=data.get("model_info", {}),
            template=data.get("template"),
            parameters=data.get("parameters"),
            license=data.get("license"),
        )


class OllamaClient:
    """
    HTTP client for Ollama API.

    Single Responsibility: HTTP communication only.
    No capability detection logic - that belongs in CapabilityDetector.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        """Initialize Ollama client.

        Args:
            base_url: Ollama API base URL (defaults to settings)
            timeout: Default request timeout in seconds
        """
        settings = get_settings()
        self._base_url = base_url or settings.OLLAMA_API_URL
        self._timeout = timeout

    # =========================================================================
    # API Methods
    # =========================================================================

    async def list_models(self) -> list[OllamaModelInfo]:
        """List all available models from /api/tags.

        Returns:
            List of OllamaModelInfo for each model

        Raises:
            OllamaConnectionError: If cannot connect to Ollama
            OllamaAPIError: If API returns error status
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/api/tags",
                    timeout=self._timeout,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.ConnectError as e:
            msg = f"Failed to connect to Ollama at {self._base_url}: {e}"
            logger.error(msg)
            raise OllamaConnectionError(msg) from e
        except httpx.HTTPStatusError as e:
            msg = f"Ollama API error: {e.response.status_code}"
            logger.error(msg)
            raise OllamaAPIError(msg) from e
        except Exception as e:
            msg = f"Unexpected error querying Ollama: {e}"
            logger.error(msg)
            raise OllamaClientError(msg) from e

        models = data.get("models", [])
        logger.debug(f"Ollama returned {len(models)} models")

        return [OllamaModelInfo.from_api_response(m) for m in models]

    async def get_model_info(
        self,
        model_name: str,
        timeout: float | None = None,
    ) -> OllamaModelDetails | None:
        """Get detailed model info from /api/show.

        Args:
            model_name: Model name (e.g., "llama3.2:3b")
            timeout: Request timeout (defaults to 5.0 for individual model)

        Returns:
            OllamaModelDetails or None if model not found

        Note:
            Returns None instead of raising for 404 - model may not exist
        """
        request_timeout = timeout or 5.0

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/api/show",
                    json={"name": model_name},
                    timeout=request_timeout,
                )

                if response.status_code == 404:
                    logger.debug(f"Model {model_name} not found in Ollama")
                    return None

                response.raise_for_status()
                data = response.json()

        except httpx.TimeoutException:
            logger.debug(f"Timeout getting info for {model_name}")
            return None
        except httpx.ConnectError as e:
            logger.debug(f"Connection failed for {model_name}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error getting model info for {model_name}: {e}")
            return None

        return OllamaModelDetails.from_api_response(data)

    async def health_check(self) -> bool:
        """Check if Ollama is reachable.

        Returns:
            True if Ollama responds, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/api/tags",
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False

    # =========================================================================
    # Raw API Access
    # =========================================================================

    async def get_raw_models(self) -> list[dict]:
        """Get raw model data from /api/tags.

        Returns:
            Raw list of model dicts from API

        Useful when you need the original API structure.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/api/tags",
                    timeout=self._timeout,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("models", [])

        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            raise OllamaAPIError(f"API error: {e.response.status_code}") from e
        except Exception as e:
            raise OllamaClientError(f"Unexpected error: {e}") from e

    async def get_raw_model_info(self, model_name: str) -> dict | None:
        """Get raw model info from /api/show.

        Args:
            model_name: Model name

        Returns:
            Raw API response dict or None
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/api/show",
                    json={"name": model_name},
                    timeout=5.0,
                )
                if response.status_code != 200:
                    return None
                return response.json()
        except Exception:
            return None
