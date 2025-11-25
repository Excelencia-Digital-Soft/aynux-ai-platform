"""
Cliente HTTP para facturas de la API DUX
Responsabilidad: Manejar las comunicaciones HTTP específicas para facturas
"""

import asyncio
import logging
from typing import Optional

import aiohttp
from aiohttp import ClientTimeout

from app.config.langsmith_config import trace_integration
from app.config.settings import get_settings
from app.models.dux import DuxApiError
from app.models.dux.response_facturas import DuxFacturasResponse
from app.utils.rate_limiter import dux_rate_limiter


class DuxFacturasClient:
    """Cliente específico para obtener facturas de la API DUX"""

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
        print("Cerrando sesión HTTP", exc_type, exc_val, exc_tb)
        if hasattr(self, "session"):
            await self.session.close()

    def _get_headers(self) -> dict:
        """Obtiene los headers para las requests"""
        return {
            "accept": "application/json",
            "authorization": self.auth_token,
            "User-Agent": "Aynux-Bot/1.0",
        }

    async def _get_facturas_internal(
        self,
        offset: int,
        limit: int,
        fecha_desde: Optional[str] = None,
        fecha_hasta: Optional[str] = None,
        cliente_id: Optional[int] = None,
        estado: Optional[str] = None,
        timeout_override: Optional[int] = None,
    ) -> DuxFacturasResponse:
        """
        Método interno para obtener facturas (con rate limiting, sin retry)
        """
        # Aplicar rate limiting ANTES de cada request
        rate_info = await dux_rate_limiter.wait_for_next_request()
        if rate_info["wait_time_seconds"] > 0:
            self.logger.debug(
                f"Rate limit wait: {rate_info['wait_time_seconds']:.2f}s "
                f"(facturas request #{rate_info['total_requests']})"
            )

        url = f"{self.base_url}/facturas"

        # Construir parámetros de query
        params = {
            "offset": offset,
            "limit": limit,
        }

        # Agregar filtros opcionales
        if fecha_desde:
            params["fecha_desde"] = fecha_desde
        if fecha_hasta:
            params["fecha_hasta"] = fecha_hasta
        if cliente_id:
            params["cliente_id"] = cliente_id
        if estado:
            params["estado"] = estado

        headers = self._get_headers()

        # Usar timeout personalizado si se proporciona
        if timeout_override:
            timeout = ClientTimeout(total=timeout_override)
        else:
            timeout = self.timeout

        self.logger.info(f"Fetching facturas from DUX API: offset={offset}, limit={limit}, filters={params}")

        try:
            async with self.session.get(url, headers=headers, params=params, timeout=timeout) as response:
                # Log del status code
                self.logger.debug(f"DUX API facturas response status: {response.status}")

                if response.status == 200:
                    data = await response.json()

                    # Manejar diferentes formatos de respuesta
                    if isinstance(data, list):
                        # Si es una lista directa, envolver
                        wrapped_data = {"facturas": data}
                    elif isinstance(data, dict):
                        # Si es un objeto, verificar si tiene las facturas
                        if "facturas" in data:
                            wrapped_data = data
                        elif "results" in data:
                            # Formato con paginación
                            wrapped_data = {"facturas": data["results"], "paging": data.get("paging")}
                        else:
                            # Asumir que todo el objeto es la lista de facturas
                            wrapped_data = {"facturas": [data]}
                    else:
                        wrapped_data = {"facturas": []}

                    # Validar y parsear la respuesta
                    try:
                        result = DuxFacturasResponse(**wrapped_data)
                        # Marcar request como completado DESPUÉS de recibir respuesta exitosa
                        dux_rate_limiter.rate_limiter.mark_request_completed()
                        return result
                    except Exception as e:
                        self.logger.error(f"Error parsing DUX API facturas response: {e}")
                        raise DuxApiError(
                            error_code="PARSE_ERROR", error_message=f"Failed to parse facturas API response: {str(e)}"
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

    @trace_integration("dux_get_facturas")
    async def get_facturas(
        self,
        offset: int = 0,
        limit: int = 20,
        fecha_desde: Optional[str] = None,
        fecha_hasta: Optional[str] = None,
        cliente_id: Optional[int] = None,
        estado: Optional[str] = None,
        timeout_override: Optional[int] = None,
        max_retries: int = 3,
    ) -> DuxFacturasResponse:
        """
        Obtiene facturas de la API DUX con filtros opcionales y retry automático

        Args:
            offset: Offset para paginación
            limit: Límite de resultados por página
            fecha_desde: Fecha desde (formato YYYY-MM-DD)
            fecha_hasta: Fecha hasta (formato YYYY-MM-DD)
            cliente_id: ID del cliente para filtrar
            estado: Estado de las facturas (PENDIENTE, PAGADA, etc.)
            timeout_override: Timeout personalizado para esta request
            max_retries: Número máximo de reintentos en caso de rate limit (default: 3)

        Returns:
            DuxFacturasResponse: Respuesta con las facturas

        Raises:
            DuxApiError: Error de la API después de todos los reintentos
            aiohttp.ClientError: Error de conexión
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await self._get_facturas_internal(
                    offset, limit, fecha_desde, fecha_hasta, cliente_id, estado, timeout_override
                )
            except DuxApiError as e:
                if e.error_code == "RATE_LIMIT" and attempt < max_retries:
                    # Calcular tiempo de espera con backoff exponencial
                    wait_time = 5.0 * (2**attempt)  # 5s, 10s, 20s
                    self.logger.warning(
                        f"Rate limit hit on facturas, retrying in {wait_time:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    await asyncio.sleep(wait_time)
                    last_error = e
                    continue
                else:
                    # Si no es rate limit o ya no hay más reintentos, lanzar la excepción
                    raise
            except Exception:
                # Para otros errores, no reintentar
                raise

        # Si llegamos aquí, todos los reintentos fallaron
        if last_error:
            raise last_error
        else:
            raise DuxApiError(error_code="MAX_RETRIES_EXCEEDED", error_message=f"Failed after {max_retries} retries")

    async def get_factura_by_id(self, id_factura: int) -> Optional[dict]:
        """
        Busca una factura específica por ID

        Args:
            id_factura: ID de la factura a buscar

        Returns:
            dict: Datos de la factura encontrada o None
        """
        try:
            # Intentar obtener la factura específica primero
            # Si la API no soporta búsqueda por ID directa, buscar en la lista
            response = await self.get_facturas(limit=100)  # Obtener un lote grande
            factura = response.find_factura_by_id(id_factura)
            return factura.model_dump() if factura else None
        except Exception as e:
            self.logger.error(f"Failed to get factura by ID {id_factura}: {e}")
            return None

    async def get_factura_by_numero(self, numero_factura: str) -> Optional[dict]:
        """
        Busca una factura específica por número

        Args:
            numero_factura: Número de la factura a buscar

        Returns:
            dict: Datos de la factura encontrada o None
        """
        try:
            response = await self.get_facturas(limit=100)  # Obtener un lote grande
            factura = response.find_factura_by_numero(numero_factura)
            return factura.model_dump() if factura else None
        except Exception as e:
            self.logger.error(f"Failed to get factura by numero '{numero_factura}': {e}")
            return None

    async def get_facturas_by_cliente(self, cliente_id: int, limit: int = 50) -> Optional[DuxFacturasResponse]:
        """
        Obtiene facturas de un cliente específico

        Args:
            cliente_id: ID del cliente
            limit: Límite de resultados

        Returns:
            DuxFacturasResponse: Facturas del cliente o None
        """
        try:
            return await self.get_facturas(cliente_id=cliente_id, limit=limit)
        except Exception as e:
            self.logger.error(f"Failed to get facturas for client {cliente_id}: {e}")
            return None

    async def get_facturas_pendientes(self, limit: int = 50) -> Optional[DuxFacturasResponse]:
        """
        Obtiene facturas pendientes de pago

        Args:
            limit: Límite de resultados

        Returns:
            DuxFacturasResponse: Facturas pendientes o None
        """
        try:
            return await self.get_facturas(estado="PENDIENTE", limit=limit)
        except Exception as e:
            self.logger.error(f"Failed to get pending facturas: {e}")
            return None

    @trace_integration("dux_facturas_test_connection")
    async def test_connection(self) -> bool:
        """
        Prueba la conexión con el endpoint de facturas de la API DUX

        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            # Intentar obtener solo 1 factura para probar la conexión
            # get_facturas() ya aplica rate limiting automáticamente
            await self.get_facturas(offset=0, limit=1)
            self.logger.info("DUX API facturas connection test successful")
            return True
        except DuxApiError as e:
            if e.error_code == "RATE_LIMIT":
                # Para rate limits, registrar pero no fallar inmediatamente
                self.logger.warning(f"DUX API facturas rate limited during connection test: {e.error_message}")
                return False
            else:
                self.logger.error(f"DUX API facturas connection test failed: {e}")
                return False
        except Exception as e:
            self.logger.error(f"DUX API facturas connection test failed: {e}")
            return False

    async def get_total_facturas_count(self) -> int:
        """
        Obtiene el total de facturas disponibles en la API

        Returns:
            int: Total de facturas
        """
        try:
            response = await self.get_facturas(offset=0, limit=1)
            return response.get_total_facturas()
        except Exception as e:
            self.logger.error(f"Failed to get total facturas count: {e}")
            return 0


class DuxFacturasClientFactory:
    """Factory para crear instancias del cliente de facturas DUX"""

    @staticmethod
    def create_client(auth_token: Optional[str] = None, timeout_seconds: int = 30) -> DuxFacturasClient:
        """
        Crea una instancia del cliente de facturas DUX

        Args:
            auth_token: Token de autenticación (usa el default si no se proporciona)
            timeout_seconds: Timeout para las requests

        Returns:
            DuxFacturasClient: Instancia del cliente
        """
        token = auth_token or "UyJ9PjF8mojO9NaexobUURe6mDlnts2J35jnaO8wKVxoSZK4RBTFa6tYZMvyJD7i"

        return DuxFacturasClient(auth_token=token, timeout_seconds=timeout_seconds)
