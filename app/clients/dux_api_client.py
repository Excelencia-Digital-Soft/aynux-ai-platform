"""
Cliente HTTP para la API DUX
Responsabilidad: Manejar las comunicaciones HTTP con la API de DUX
"""

import asyncio
import logging
from typing import Optional

import aiohttp
from aiohttp import ClientTimeout
from pydantic import ValidationError

from app.config.langsmith_config import trace_integration
from app.config.settings import get_settings
from app.models.dux import DuxApiError
from app.models.dux.response_items import DuxItemsResponse
from app.utils.rate_limiter import dux_rate_limiter


class DuxApiClient:
    """Cliente para interactuar con la API de DUX"""

    def __init__(
        self,
        base_url: str = "https://erp.duxsoftware.com.ar/WSERP/rest/services",
        auth_token: str = "UyJ9PjF8mojO9NaexobUURe6mDlnts2J35jnaO8wKVxoSZK4RBTFa6tYZMvyJD7i",
        timeout_seconds: int = 30,
    ):
        self.settings = get_settings()
        self.base_url = self.settings.DUX_API_BASE_URL or base_url.rstrip("/")
        self.auth_token = self.settings.DUX_API_KEY or auth_token
        timeout_value = self.settings.DUX_API_TIMEOUT or timeout_seconds
        self.timeout = ClientTimeout(total=timeout_value)
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Inicializa la sesión HTTP"""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cierra la sesión HTTP"""
        print("Cierre sesión HTTP", exc_type, exc_val, exc_tb)
        if hasattr(self, "session"):
            await self.session.close()

    def _get_headers(self) -> dict:
        """Obtiene los headers para las requests"""
        return {
            "accept": "application/json",
            "authorization": self.auth_token,
            "User-Agent": "Aynux-Bot/1.0",
        }

    async def _get_items_internal(
        self, offset: int, limit: int, timeout_override: Optional[int] = None
    ) -> DuxItemsResponse:
        """
        Método interno para obtener items (sin rate limiting ni retry)
        """
        # Aplicar rate limiting ANTES de cada request
        rate_info = await dux_rate_limiter.wait_for_next_request()
        if rate_info['wait_time_seconds'] > 0:
            self.logger.debug(
                f"Rate limit wait: {rate_info['wait_time_seconds']:.2f}s "
                f"(request #{rate_info['total_requests']})"
            )

        url = f"{self.base_url}/items"
        params = {
            "offset": offset,
            "limit": limit,
        }

        headers = self._get_headers()

        # Usar timeout personalizado si se proporciona
        if timeout_override:
            timeout = ClientTimeout(total=timeout_override)
        else:
            timeout = self.timeout

        self.logger.info(f"Fetching items from DUX API: offset={offset}, limit={limit}")

        try:
            async with self.session.get(url, headers=headers, params=params, timeout=timeout) as response:
                # Log del status code
                self.logger.debug(f"DUX API response status: {response.status}")

                if response.status == 200:
                    data = await response.json()

                    # Validar y parsear la respuesta
                    try:
                        result = DuxItemsResponse(**data)
                        # Marcar request como completado DESPUÉS de recibir respuesta exitosa
                        dux_rate_limiter.rate_limiter.mark_request_completed()
                        return result
                    except Exception as e:
                        # Log datos útiles para debugging
                        self.logger.error(f"Error parsing DUX API response: {e}")
                        if isinstance(e, ValidationError):
                            self.logger.error(f"Validation errors: {e.errors()}")

                        # Log una muestra de los datos para debugging
                        if isinstance(data, dict) and "results" in data:
                            sample_size = min(2, len(data.get("results", [])))
                            if sample_size > 0:
                                self.logger.error(
                                    f"Sample data (first {sample_size} items): {data['results'][:sample_size]}"
                                )

                        raise DuxApiError(
                            error_code="PARSE_ERROR", error_message=f"Failed to parse API response: {str(e)}"
                        ) from e

                elif response.status == 401:
                    error_msg = "Authentication failed - check API token"
                    self.logger.error(error_msg)
                    raise DuxApiError(error_code="AUTH_ERROR", error_message=error_msg)

                elif response.status == 429:
                    error_msg = "Rate limit exceeded - API returned 429"
                    self.logger.warning(error_msg)
                    # Esperar 5 segundos adicionales antes de lanzar la excepción
                    # para dar tiempo al rate limiter a resetear
                    await asyncio.sleep(5.0)
                    raise DuxApiError(error_code="RATE_LIMIT", error_message=error_msg)

                else:
                    error_text = await response.text()
                    error_msg = f"API returned status {response.status}: {error_text}"
                    self.logger.error(error_msg)
                    raise DuxApiError(error_code=f"HTTP_{response.status}", error_message=error_msg)

        except (aiohttp.ServerTimeoutError, aiohttp.ClientConnectionError, asyncio.TimeoutError) as tout:
            error_msg = f"Request timeout after {timeout.total} seconds"
            self.logger.error(error_msg)
            raise DuxApiError(error_code="TIMEOUT", error_message=error_msg) from tout

        except aiohttp.ClientError as e:
            error_msg = f"HTTP client error: {str(e)}"
            self.logger.error(error_msg)
            raise DuxApiError(error_code="CONNECTION_ERROR", error_message=error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            raise DuxApiError(error_code="UNEXPECTED_ERROR", error_message=error_msg) from e

    @trace_integration("dux_get_items")
    async def get_items(
        self, offset: int = 0, limit: int = 20, timeout_override: Optional[int] = None, max_retries: int = 3
    ) -> DuxItemsResponse:
        """
        Obtiene items/productos de la API DUX con retry automático

        Args:
            offset: Offset para paginación
            limit: Límite de resultados por página
            timeout_override: Timeout personalizado para esta request
            max_retries: Número máximo de reintentos en caso de rate limit (default: 3)

        Returns:
            DuxItemsResponse: Respuesta con los items

        Raises:
            DuxApiError: Error de la API después de todos los reintentos
            aiohttp.ClientError: Error de conexión
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await self._get_items_internal(offset, limit, timeout_override)
            except DuxApiError as e:
                if e.error_code == "RATE_LIMIT" and attempt < max_retries:
                    # Calcular tiempo de espera con backoff exponencial
                    wait_time = 5.0 * (2 ** attempt)  # 5s, 10s, 20s
                    self.logger.warning(
                        f"Rate limit hit, retrying in {wait_time:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    await asyncio.sleep(wait_time)
                    last_error = e
                    continue
                else:
                    # Si no es rate limit o ya no hay más reintentos, lanzar la excepción
                    raise
            except Exception as e:
                # Para otros errores, no reintentar
                raise

        # Si llegamos aquí, todos los reintentos fallaron
        if last_error:
            raise last_error
        else:
            raise DuxApiError(
                error_code="MAX_RETRIES_EXCEEDED",
                error_message=f"Failed after {max_retries} retries"
            )

    @trace_integration("dux_test_connection")
    async def test_connection(self) -> bool:
        """
        Prueba la conexión con la API DUX

        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            # Intentar obtener solo 1 item para probar la conexión
            # get_items() ya aplica rate limiting automáticamente
            await self.get_items(offset=0, limit=1)
            self.logger.info("DUX API connection test successful")
            return True
        except DuxApiError as e:
            if e.error_code == "RATE_LIMIT":
                # Para rate limits, registrar pero no fallar inmediatamente
                self.logger.warning(f"DUX API rate limited during connection test: {e.error_message}")
                return False
            else:
                self.logger.error(f"DUX API connection test failed: {e}")
                return False
        except Exception as e:
            self.logger.error(f"DUX API connection test failed: {e}")
            return False

    async def get_total_items_count(self) -> int:
        """
        Obtiene el total de items disponibles en la API

        Returns:
            int: Total de items
        """
        try:
            response = await self.get_items(offset=0, limit=1)
            return response.get_total_items()
        except Exception as e:
            self.logger.error(f"Failed to get total items count: {e}")
            return 0


class DuxApiClientFactory:
    """Factory para crear instancias del cliente DUX"""

    @staticmethod
    def create_client(auth_token: Optional[str] = None, timeout_seconds: int = 30) -> DuxApiClient:
        """
        Crea una instancia del cliente DUX

        Args:
            auth_token: Token de autenticación (usa el default si no se proporciona)
            timeout_seconds: Timeout para las requests

        Returns:
            DuxApiClient: Instancia del cliente
        """
        token = auth_token or "UyJ9PjF8mojO9NaexobUURe6mDlnts2J35jnaO8wKVxoSZK4RBTFa6tYZMvyJD7i"

        return DuxApiClient(auth_token=token, timeout_seconds=timeout_seconds)
