"""
Cliente HTTP para rubros de la API DUX
Responsabilidad: Manejar las comunicaciones HTTP específicas para rubros/categorías
"""

import asyncio
import logging
from typing import Optional

import aiohttp
from aiohttp import ClientTimeout

from app.config.settings import get_settings
from app.models.dux import DuxApiError
from app.models.dux.response_rubros import DuxRubrosResponse
from app.utils.rate_limiter import dux_rate_limiter


class DuxRubrosClient:
    """Cliente específico para obtener rubros de la API DUX"""

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
        print("Cierre sesión HTTP...", exc_type, exc_val, exc_tb)
        if hasattr(self, "session"):
            await self.session.close()

    def _get_headers(self) -> dict:
        """Obtiene los headers para las requests"""
        return {
            "accept": "application/json",
            "authorization": self.auth_token,
            "User-Agent": "Aynux-Bot/1.0",
        }

    async def get_rubros(self, timeout_override: Optional[int] = None) -> DuxRubrosResponse:
        """
        Obtiene rubros/categorías de la API DUX

        Args:
            timeout_override: Timeout personalizado para esta request

        Returns:
            DuxRubrosResponse: Respuesta con los rubros

        Raises:
            DuxApiError: Error de la API
            aiohttp.ClientError: Error de conexión
        """
        url = f"{self.base_url}/rubros"
        headers = self._get_headers()

        # Usar timeout personalizado si se proporciona
        if timeout_override:
            timeout = ClientTimeout(total=timeout_override)
        else:
            timeout = self.timeout

        self.logger.info("Fetching rubros from DUX API")

        try:
            async with self.session.get(url, headers=headers, timeout=timeout) as response:
                # Log del status code
                self.logger.debug(f"DUX API rubros response status: {response.status}")

                if response.status == 200:
                    data = await response.json()

                    # La respuesta es directamente una lista de rubros
                    # Necesitamos envolver en un objeto con key 'rubros'
                    if isinstance(data, list):
                        wrapped_data = {"rubros": data}
                    else:
                        wrapped_data = data

                    # Validar y parsear la respuesta
                    try:
                        return DuxRubrosResponse(**wrapped_data)
                    except Exception as e:
                        self.logger.error(f"Error parsing DUX API rubros response: {e}")
                        raise DuxApiError(
                            error_code="PARSE_ERROR", error_message=f"Failed to parse rubros API response: {str(e)}"
                        ) from e

                elif response.status == 401:
                    error_msg = "Authentication failed - check API token"
                    self.logger.error(error_msg)
                    raise DuxApiError(error_code="AUTH_ERROR", error_message=error_msg)

                elif response.status == 429:
                    error_msg = "Rate limit exceeded"
                    self.logger.warning(error_msg)
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

    async def test_connection(self) -> bool:
        """
        Prueba la conexión con el endpoint de rubros de la API DUX

        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            # Aplicar rate limiting antes de la prueba de conexión
            rate_info = await dux_rate_limiter.wait_for_next_request()
            if rate_info['wait_time_seconds'] > 0:
                self.logger.debug(f"Rate limit wait for rubros connection test: {rate_info['wait_time_seconds']:.2f}s")
            
            await self.get_rubros()
            self.logger.info("DUX API rubros connection test successful")
            return True
        except DuxApiError as e:
            if e.error_code == "RATE_LIMIT":
                # Para rate limits, registrar pero no fallar inmediatamente
                self.logger.warning(f"DUX API rubros rate limited during connection test: {e.error_message}")
                return False
            else:
                self.logger.error(f"DUX API rubros connection test failed: {e}")
                return False
        except Exception as e:
            self.logger.error(f"DUX API rubros connection test failed: {e}")
            return False

    async def get_rubro_by_id(self, id_rubro: int) -> Optional[dict]:
        """
        Busca un rubro específico por ID

        Args:
            id_rubro: ID del rubro a buscar

        Returns:
            dict: Datos del rubro encontrado o None
        """
        try:
            response = await self.get_rubros()
            rubro = response.find_rubro_by_id(id_rubro)
            return rubro.model_dump() if rubro else None
        except Exception as e:
            self.logger.error(f"Failed to get rubro by ID {id_rubro}: {e}")
            return None

    async def get_rubro_by_name(self, nombre: str) -> Optional[dict]:
        """
        Busca un rubro específico por nombre

        Args:
            nombre: Nombre del rubro a buscar

        Returns:
            dict: Datos del rubro encontrado o None
        """
        try:
            response = await self.get_rubros()
            rubro = response.find_rubro_by_name(nombre)
            return rubro.model_dump() if rubro else None
        except Exception as e:
            self.logger.error(f"Failed to get rubro by name '{nombre}': {e}")
            return None


class DuxRubrosClientFactory:
    """Factory para crear instancias del cliente de rubros DUX"""

    @staticmethod
    def create_client(auth_token: Optional[str] = None, timeout_seconds: int = 30) -> DuxRubrosClient:
        """
        Crea una instancia del cliente de rubros DUX

        Args:
            auth_token: Token de autenticación (usa el default si no se proporciona)
            timeout_seconds: Timeout para las requests

        Returns:
            DuxRubrosClient: Instancia del cliente
        """
        token = auth_token or "UyJ9PjF8mojO9NaexobUURe6mDlnts2J35jnaO8wKVxoSZK4RBTFa6tYZMvyJD7i"

        return DuxRubrosClient(auth_token=token, timeout_seconds=timeout_seconds)
