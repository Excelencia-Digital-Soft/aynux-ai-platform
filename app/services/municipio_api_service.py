import logging
from typing import Any, Dict, Optional

import httpx

from app.config.settings import get_settings
from app.services.municipio_auth_service import MunicipioAuthService

logger = logging.getLogger(__name__)


class MunicipioAPIService:
    """
    Servicio genérico para interactuar con la API de municipalidades
    """

    def __init__(self):
        self.settings = get_settings()
        self.api_base = self.settings.MUNICIPIO_API_BASE
        self.timeout = 15.0  # Timeout en segundos
        self.auth_service = MunicipioAuthService()

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        retry_auth: bool = True,
    ) -> Dict[str, Any] | None:
        """
        Realiza una petición genérica a la API

        Args:
            method: Método HTTP (GET, POST, PUT, DELETE)
            endpoint: Endpoint de la API (sin la URL base)
            params: Parámetros de la consulta (opcional)
            data: Datos para el cuerpo de la petición (opcional)
            headers: Cabeceras adicionales (opcional)
            retry_auth: Si es True, reintenta la petición si falla por autenticación

        Returns:
            Respuesta de la API en formato JSON
        """
        url = f"{self.api_base}/{endpoint}"

        # Obtener cabeceras de autenticación actualizadas
        auth_headers = await self.auth_service.get_auth_headers()

        # Combinar headers por defecto con headers adicionales
        request_headers = auth_headers.copy()
        if headers:
            request_headers.update(headers)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    headers=request_headers,
                    timeout=self.timeout,
                )

                # Registrar información de la petición para debugging
                logger.debug(f"Request to {url} - Status: {response.status_code}")

                # Manejar errores de autenticación
                if response.status_code == 401 and retry_auth:
                    logger.info("Token expirado, renovando...")
                    await self.auth_service.invalidate_token()
                    # Reintentar la petición con un nuevo token
                    return await self.request(
                        method, endpoint, params, data, headers, retry_auth=False
                    )

                # Manejar respuesta
                if response.status_code >= 400:
                    logger.error(f"API Error: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "message": f"Error en la petición: {response.text}",
                    }

                # Intentar parsear la respuesta como JSON
                try:
                    data = response.json()
                    return data
                except Exception as e:
                    logger.error(f"Error parsing JSON response: {e}")
                    return {
                        "success": False,
                        "message": f"Error al procesar la respuesta: {str(e)}",
                        "data": response.text,
                    }

        except httpx.TimeoutException:
            logger.error(f"Timeout in request to {url}")
            return {
                "success": False,
                "message": "La petición ha excedido el tiempo de espera",
            }

        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            return {"success": False, "message": f"Error en la petición: {str(e)}"}

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"success": False, "message": f"Error inesperado: {str(e)}"}

    # Métodos específicos para facilitar el uso
    async def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any] | None:
        """Realiza una petición GET"""
        return await self.request("GET", endpoint, params=params)

    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any] | None:
        """Realiza una petición POST"""
        return await self.request("POST", endpoint, data=data)

    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any] | None:
        """Realiza una petición PUT"""
        return await self.request("PUT", endpoint, data=data)

    async def delete(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any] | None:
        """Realiza una petición DELETE"""
        return await self.request("DELETE", endpoint, params=params)

    # Método para verificar la conexión con la API
    async def verify_connection(self) -> bool:
        """
        Verifica la conexión con la API

        Returns:
            True si la conexión es exitosa, False en caso contrario
        """
        try:
            # Intenta hacer una petición simple para verificar la conexión
            # Reemplaza 'health' con un endpoint válido que sirva
            # para verificar la conexión
            response = await self.get("health")
            return response.get("success", False)
        except Exception as e:
            logger.error(f"Error verificando conexión con la API: {str(e)}")
            return False

    # Aquí puedes añadir métodos específicos para los endpoints más utilizados

    async def get_contribuyentes(
        self,
        documento: Optional[str] = None,
        nombre: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any] | None:
        """
        Obtiene información de contribuyentes según criterios de búsqueda

        Args:
            documento: Número de documento (opcional)
            nombre: Nombre del contribuyente (opcional)
            limit: Límite de resultados a devolver

        Returns:
            Datos de los contribuyentes encontrados
        """
        params = {"limit": limit, "documento": "", "nombre": ""}
        if documento:
            params["documento"] = documento
        if nombre:
            params["nombre"] = nombre

        return await self.get("contribuyentes", params)

    # Añade más métodos específicos según las necesidades de tu aplicación
