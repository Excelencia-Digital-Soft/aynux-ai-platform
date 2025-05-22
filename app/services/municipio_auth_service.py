import asyncio
import logging
import time
from datetime import datetime
from typing import Dict

import httpx

from app.config.settings import get_settings
from app.models.redis_municipalidad import AuthToken
from app.repositories.redis_repository import RedisRepository

logger = logging.getLogger(__name__)

# Constantes para la gestión de tokens
TOKEN_KEY = "municipio_api_token"
TOKEN_LOCK_KEY = "municipio_api_token_lock"
TOKEN_EXPIRY_BUFFER = 300  # 5 minutos de margen antes de la expiración


class MunicipioAuthService:
    """
    Servicio para gestionar la autenticación con la API de municipalidades.

    Este servicio se encarga de:
    - Obtener y almacenar tokens de autenticación
    - Verificar la validez de los tokens
    - Renovar automáticamente los tokens expirados
    - Asegurar que solo un proceso renueve el token al mismo tiempo (bloqueo distribuido)
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.MUNICIPIO_API_BASE
        self.api_key = self.settings.MUNICIPIO_API_KEY
        self.username = self.settings.MUNICIPIO_API_USERNAME
        self.password = self.settings.MUNICIPIO_API_PASSWORD
        self.timeout = 15.0  # Timeout en segundos

        # Repositorio para almacenar el token
        self.redis_repo = RedisRepository[AuthToken](AuthToken, prefix="auth")

    async def get_auth_headers(self) -> Dict[str, str]:
        """
        Obtiene las cabeceras de autenticación para las solicitudes a la API.

        Verifica si el token actual es válido y lo renueva si es necesario.

        Returns:
            Diccionario con las cabeceras de autenticación
        """
        token = await self._get_valid_token()

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/plain",
        }

    async def _get_valid_token(self) -> str:
        """
        Obtiene un token válido, renovándolo si es necesario.

        Returns:
            Token válido
        """
        # Obtener directamente el token como string
        token_info = self.redis_repo.get(TOKEN_KEY)

        logger.debug(f"Token info retrieved from Redis: {token_info}")
        print("Token Info type", type(token_info))

        # Verificar si hay token y si está por expirar
        current_time = time.time()
        if (
            not token_info
            or not isinstance(token_info, AuthToken)
            or not token_info.token
            or current_time > token_info.expires_at - TOKEN_EXPIRY_BUFFER
        ):
            return await self._obtain_new_token()
        return token_info.token

    async def _obtain_new_token(self) -> str:
        """
        Obtiene un nuevo token de autenticación y lo almacena.

        Utiliza un mecanismo de bloqueo para evitar múltiples solicitudes simultáneas.

        Returns:
            Nuevo token de autenticación
        """
        # Comprobar bloqueo para evitar múltiples solicitudes simultáneas
        if not await self._acquire_lock():
            # Si no podemos adquirir el bloqueo, esperamos
            await asyncio.sleep(1)
            token_info = self.redis_repo.get(TOKEN_KEY)
            if token_info and isinstance(token_info, AuthToken) and token_info.token:
                return token_info.token
            # Si seguimos sin token, forzamos la adquisición del bloqueo
            await self._acquire_lock(force=True)

        try:
            # Realizar solicitud de autenticación
            url = f"{self.base_url}/auth/login"

            payload = {
                "usuario": self.username,
                "clave": self.password,
            }

            headers = {
                "accept": "text/plain",
                "Content-Type": "application/json",
            }

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url, json=payload, headers=headers, timeout=self.timeout
                    )

                    response.raise_for_status()
                    login_info = response.json()

                    #  Verificar respuesta HTTP
                    if response.status_code >= 400:
                        logger.error(
                            f"Error HTTP {response.status_code}: {response.text}"
                        )
                        return ""

                    try:
                        login_info = response.json()
                    except ValueError:
                        logger.error(f"Respuesta no válida JSON: {response.text}")
                        return ""

                    # Verificar si la autenticación fue exitosa
                    if not login_info.get("esExitoso", False):
                        error_msg = login_info.get(
                            "mensaje", "Error desconocido en la autenticación"
                        )
                        logger.error(f"Fallo de autenticación: {error_msg}")
                        return ""

                    # Extraer token
                    user_data = login_info.get("datos", {})
                    token = user_data.get("token", "")

                    if not token:
                        logger.error("No se pudo obtener el token de autenticación")
                        return ""

                    expires_in = 28800  # 8 horas
                    expires_at = time.time() + expires_in
                    created_at = time.time()

                    # Crear una instancia de AuthToken
                    token_model = AuthToken(
                        token=token,
                        expires_at=expires_at,
                        created_at=created_at,
                        id=str(user_data.get("id", "")),
                        nombre_usuario=user_data.get("nombreUsuario", ""),
                        nombre_completo=user_data.get("nombreCompleto", ""),
                        activo=user_data.get("activo", False),
                    )

                    try:
                        # Guardar en Redis usando el método set estándar
                        success = self.redis_repo.set(
                            TOKEN_KEY, token_model, expiration=expires_in
                        )
                        if not success:
                            logger.warning(
                                "No se pudo guardar el token en Redis, usando caché local temporal"
                            )
                            # Guardar en una variable de instancia como fallback
                            setattr(self, "_local_token", token)
                    except Exception as e:
                        logger.error(e)
                        print("ERROR...", e)

                    logger.info("Token de autenticación renovado correctamente")
                    return token

            except Exception as e:
                logger.error(f"Error al obtener token de autenticación: {str(e)}")
                return ""

        finally:
            # Liberar el bloqueo sin importar el resultado
            await self._release_lock()

    async def _acquire_lock(self, force: bool = False, timeout: int = 10) -> bool:
        """
        Adquiere un bloqueo distribuido para evitar múltiples renovaciones simultáneas.

        Args:
            force: Si es True, fuerza la adquisición del bloqueo
            timeout: Tiempo máximo en segundos para intentar adquirir el bloqueo

        Returns:
            True si se adquirió el bloqueo, False en caso contrario
        """
        if force:
            # Forzar la liberación del bloqueo anterior
            self.redis_repo.delete(TOKEN_LOCK_KEY)

        # Tiempo límite para intentar adquirir el bloqueo
        end_time = time.time() + timeout
        lock_value = f"{datetime.now().isoformat()}"

        while time.time() < end_time:
            # Intentar establecer el bloqueo solo si no existe
            if self.redis_repo.set_if_not_exists(
                TOKEN_LOCK_KEY, lock_value, expiration=30
            ):
                return True

            # Esperar antes de reintentar
            await asyncio.sleep(0.5)

        # Si llegamos aquí, no pudimos adquirir el bloqueo
        logger.warning("No se pudo adquirir el bloqueo para renovar el token")
        return False

    async def _release_lock(self) -> bool:
        """
        Libera el bloqueo distribuido.

        Returns:
            True si se liberó el bloqueo, False en caso contrario
        """
        return self.redis_repo.delete(TOKEN_LOCK_KEY)

    async def invalidate_token(self) -> None:
        """
        Invalida el token actual, forzando una renovación en la próxima solicitud.
        """
        self.redis_repo.delete(TOKEN_KEY)
        # También eliminar cualquier token en caché local
        if hasattr(self, "_local_token"):
            delattr(self, "_local_token")
        logger.info("Token de autenticación invalidado")

    async def refresh_token_if_needed(self) -> bool:
        """
        Verifica y renueva el token si es necesario.

        Returns:
            True si el token se renovó, False si no era necesario o falló
        """
        token_info = self.redis_repo.get(TOKEN_KEY)

        current_time = time.time()
        if (
            not token_info
            or not isinstance(token_info, dict)
            or not token_info.get("token")
            or current_time > token_info.get("expires_at", 0) - TOKEN_EXPIRY_BUFFER
        ):
            new_token = await self._obtain_new_token()
            return bool(new_token)

        return False
