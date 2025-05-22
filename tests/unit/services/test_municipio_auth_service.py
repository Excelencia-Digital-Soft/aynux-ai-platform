import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.municipio_auth_service import MunicipioAuthService


@pytest.fixture
def mock_settings():
    """Fixture para crear configuraciones mock"""
    with patch("app.services.municipio_auth_service.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.MUNICIPIO_API_BASE = "https://api.municipalidad.test"
        mock_settings.MUNICIPIO_API_KEY = "test_api_key"
        mock_settings.MUNICIPIO_API_USERNAME = "test_username"
        mock_settings.MUNICIPIO_API_PASSWORD = "test_password"
        mock_get_settings.return_value = mock_settings
        yield mock_settings


@pytest.fixture
def mock_redis_repository():
    """Fixture para crear un mock del repositorio Redis"""
    with patch("app.services.municipio_auth_service.RedisRepository") as mock_class:
        mock_instance = mock_class.return_value
        # Configurar métodos del repositorio
        mock_instance.get = MagicMock()
        mock_instance.set = MagicMock()
        mock_instance.set_if_not_exists = MagicMock()
        mock_instance.delete = MagicMock()
        mock_instance.exists = MagicMock()
        yield mock_instance


@pytest.fixture
def auth_service(mock_settings, mock_redis_repository):
    """Fixture para crear el servicio de autenticación con mocks"""
    service = MunicipioAuthService()
    service.redis_repo = mock_redis_repository
    return service


class TestMunicipioAuthService:
    """Pruebas para el servicio de autenticación de Municipio"""

    @pytest.mark.asyncio
    async def test_get_auth_headers_with_valid_token(
        self, auth_service, mock_redis_repository
    ):
        """Prueba para obtener cabeceras con token válido existente"""
        # Configurar token válido en Redis
        current_time = time.time()
        token_data = {
            "token": "valid_token_123",
            "id": "36",
            "nombreUsuario": "excelencia",
            "nombreCompleto": "Excelencia Digital",
            "activo": True,
            "expires_in": 28800,
            "expires_at": current_time + 43200,  # 12 horas de validez restante
            "obtained_at": current_time - 43200,  # Obtenido hace 12 horas
        }
        mock_redis_repository.get.return_value = token_data

        # Llamar al método
        headers = await auth_service.get_auth_headers()

        # Verificar que se utilizó el token existente
        mock_redis_repository.get.assert_called_once()

        # Verificar las cabeceras resultantes
        assert headers["Authorization"] == "Bearer valid_token_123"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "text/plain"

    @pytest.mark.asyncio
    async def test_get_auth_headers_with_expiring_token(
        self, auth_service, mock_redis_repository
    ):
        """Prueba para obtener cabeceras cuando el token está a punto de expirar"""
        # Configurar token a punto de expirar en Redis
        current_time = time.time()
        token_data = {
            "token": "expiring_token_123",
            "id": "36",
            "nombreUsuario": "excelencia",
            "nombreCompleto": "Excelencia Digital",
            "activo": True,
            "expires_in": 86400,
            "expires_at": current_time + 200,  # Menos de 5 minutos de validez
            "obtained_at": current_time - 86200,  # Obtenido hace casi 24 horas
        }
        mock_redis_repository.get.return_value = token_data

        # Configurar mock para _obtain_new_token
        with patch.object(
            auth_service, "_obtain_new_token", new_callable=AsyncMock
        ) as mock_obtain_new_token:
            mock_obtain_new_token.return_value = "new_token_456"

            # Llamar al método
            headers = await auth_service.get_auth_headers()

            # Verificar que se intentó obtener un nuevo token
            mock_obtain_new_token.assert_called_once()

            # Verificar las cabeceras resultantes
            assert headers["Authorization"] == "Bearer new_token_456"
            assert headers["Content-Type"] == "application/json"
            assert headers["Accept"] == "text/plain"

    @pytest.mark.asyncio
    async def test_get_auth_headers_with_no_token(
        self, auth_service, mock_redis_repository
    ):
        """Prueba para obtener cabeceras cuando no hay token"""
        # Configurar que no hay token en Redis
        mock_redis_repository.get.return_value = None

        # Configurar mock para _obtain_new_token
        with patch.object(
            auth_service, "_obtain_new_token", new_callable=AsyncMock
        ) as mock_obtain_new_token:
            mock_obtain_new_token.return_value = "new_token_789"

            # Llamar al método
            headers = await auth_service.get_auth_headers()

            # Verificar que se intentó obtener un nuevo token
            mock_obtain_new_token.assert_called_once()

            # Verificar las cabeceras resultantes
            assert headers["Authorization"] == "Bearer new_token_789"

    @pytest.mark.asyncio
    async def test_obtain_new_token_success(self, auth_service, mock_redis_repository):
        """Prueba para obtener un nuevo token con éxito"""
        # Configurar que el bloqueo se adquiere correctamente
        with patch.object(
            auth_service, "_acquire_lock", new_callable=AsyncMock
        ) as mock_acquire_lock:
            mock_acquire_lock.return_value = True

            # Configurar que el bloqueo se libera correctamente
            with patch.object(
                auth_service, "_release_lock", new_callable=AsyncMock
            ) as mock_release_lock:
                mock_release_lock.return_value = True

                # Configurar respuesta de httpx
                with patch("httpx.AsyncClient.post") as mock_post:
                    # Simular respuesta exitosa según formato real de la API
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status = MagicMock()
                    mock_response.json.return_value = {
                        "esExitoso": True,
                        "datos": {
                            "id": 36,
                            "nombreUsuario": "excelencia",
                            "email": "jillanez@excelenciadigital.net",
                            "nombreCompleto": "Excelencia Digital",
                            "activo": True,
                            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJleGNlbGVuY2lhIiwianRpIjoiMTIzNCJ9.qwerty",
                        },
                        "errores": None,
                        "mensaje": "Login exitoso",
                    }
                    mock_post.return_value = mock_response

                    # Llamar al método
                    token = await auth_service._obtain_new_token()

                    # Verificar que se hizo la petición HTTP correcta
                    mock_post.assert_called_once()
                    url_arg = mock_post.call_args[0][0]
                    assert url_arg == "https://api.municipalidad.test/api/v1/Auth/Login"

                    # Verificar datos de autenticación enviados
                    json_arg = mock_post.call_args[1]["json"]
                    assert json_arg["usuario"] == "test_username"
                    assert json_arg["clave"] == "test_password"

                    # Verificar headers correctos
                    headers_arg = mock_post.call_args[1]["headers"]
                    assert headers_arg["accept"] == "text/plain"
                    assert headers_arg["Content-Type"] == "application/json"

                    # Verificar que se guardó el token en Redis
                    mock_redis_repository.set.assert_called_once()
                    key_arg, value_arg = mock_redis_repository.set.call_args[0]
                    assert key_arg == "municipio_api_token"
                    expected_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJleGNlbGVuY2lhIiwianRpIjoiMTIzNCJ9.qwerty"
                    assert value_arg["token"] == expected_token
                    assert value_arg["nombreUsuario"] == "excelencia"
                    assert value_arg["nombreCompleto"] == "Excelencia Digital"

                    # Verificar que se liberó el bloqueo
                    mock_release_lock.assert_called_once()

                    # Verificar el resultado
                    assert token == expected_token

    @pytest.mark.asyncio
    async def test_obtain_new_token_http_error(self, auth_service):
        """Prueba para manejar error HTTP al obtener token"""
        # Configurar que el bloqueo se adquiere correctamente
        with patch.object(
            auth_service, "_acquire_lock", new_callable=AsyncMock
        ) as mock_acquire_lock:
            mock_acquire_lock.return_value = True

            # Configurar que el bloqueo se libera correctamente
            with patch.object(
                auth_service, "_release_lock", new_callable=AsyncMock
            ) as mock_release_lock:
                mock_release_lock.return_value = True

                # Configurar respuesta de httpx con error
                with patch("httpx.AsyncClient.post") as mock_post:
                    mock_post.side_effect = Exception("HTTP Error")

                    # Llamar al método
                    token = await auth_service._obtain_new_token()

                    # Verificar que se liberó el bloqueo a pesar del error
                    mock_release_lock.assert_called_once()

                    # Verificar que se devuelve un string vacío como fallback
                    assert token == ""

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, auth_service, mock_redis_repository):
        """Prueba para adquirir bloqueo con éxito"""
        # Configurar éxito al adquirir el bloqueo
        mock_redis_repository.set_if_not_exists.return_value = True

        # Llamar al método
        result = await auth_service._acquire_lock()

        # Verificar que se intentó establecer el bloqueo
        mock_redis_repository.set_if_not_exists.assert_called_once()

        # Verificar clave y expiración del bloqueo
        key_arg = mock_redis_repository.set_if_not_exists.call_args[0][0]
        assert key_arg == "municipio_api_token_lock"

        expiration_arg = mock_redis_repository.set_if_not_exists.call_args[1][
            "expiration"
        ]
        assert expiration_arg == 30

        # Verificar resultado
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_lock_failure(self, auth_service, mock_redis_repository):
        """Prueba para manejar fallo al adquirir bloqueo"""
        # Configurar fallo al adquirir el bloqueo
        mock_redis_repository.set_if_not_exists.return_value = False

        # Para esta prueba, reducir el timeout a 1 segundo
        with patch("time.time") as mock_time:
            mock_time.side_effect = [0, 0.5, 1.5]  # Simular paso del tiempo

            # Llamar al método con timeout reducido para que la prueba sea rápida
            result = await auth_service._acquire_lock(timeout=1)

            # Verificar que se intentó establecer el bloqueo al menos una vez
            assert mock_redis_repository.set_if_not_exists.call_count >= 1

            # Verificar resultado
            assert result is False

    @pytest.mark.asyncio
    async def test_acquire_lock_force(self, auth_service, mock_redis_repository):
        """Prueba para forzar la adquisición del bloqueo"""
        # Configurar éxito al adquirir el bloqueo
        mock_redis_repository.set_if_not_exists.return_value = True

        # Llamar al método con force=True
        result = await auth_service._acquire_lock(force=True)

        # Verificar que primero se eliminó cualquier bloqueo existente
        mock_redis_repository.delete.assert_called_once_with("municipio_api_token_lock")

        # Verificar que se intentó establecer el bloqueo
        mock_redis_repository.set_if_not_exists.assert_called_once()

        # Verificar resultado
        assert result is True

    @pytest.mark.asyncio
    async def test_release_lock(self, auth_service, mock_redis_repository):
        """Prueba para liberar el bloqueo"""
        # Configurar éxito al eliminar la clave
        mock_redis_repository.delete.return_value = True

        # Llamar al método
        result = auth_service._release_lock()

        # Verificar que se intentó eliminar la clave del bloqueo
        mock_redis_repository.delete.assert_called_once_with("municipio_api_token_lock")

        # Verificar resultado
        assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_token(self, auth_service, mock_redis_repository):
        """Prueba para invalidar el token actual"""
        # Llamar al método
        await auth_service.invalidate_token()

        # Verificar que se eliminó la clave del token
        mock_redis_repository.delete.assert_called_once_with("municipio_api_token")

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_not_needed(
        self, auth_service, mock_redis_repository
    ):
        """Prueba para verificar que no se renueva un token válido"""
        # Configurar token válido en Redis
        current_time = time.time()
        token_data = {
            "access_token": "valid_token_123",
            "token_type": "bearer",
            "expires_in": 3600,
            "expires_at": current_time + 1800,  # 30 minutos de validez
            "obtained_at": current_time - 1800,  # Obtenido hace 30 minutos
        }
        mock_redis_repository.get.return_value = token_data

        # Configurar que no se llama a _obtain_new_token
        with patch.object(auth_service, "_obtain_new_token") as mock_obtain_new_token:
            # Llamar al método
            result = await auth_service.refresh_token_if_needed()

            # Verificar que no se intentó obtener un nuevo token
            mock_obtain_new_token.assert_not_called()

            # Verificar resultado
            assert result is False  # No fue necesario renovar

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_needed(
        self, auth_service, mock_redis_repository
    ):
        """Prueba para verificar que se renueva un token a punto de expirar"""
        # Configurar token a punto de expirar en Redis
        current_time = time.time()
        token_data = {
            "access_token": "expiring_token_123",
            "token_type": "bearer",
            "expires_in": 3600,
            "expires_at": current_time + 200,  # Menos de 5 minutos de validez
            "obtained_at": current_time - 3400,  # Obtenido hace casi 1 hora
        }
        mock_redis_repository.get.return_value = token_data

        # Configurar mock para _obtain_new_token
        with patch.object(
            auth_service, "_obtain_new_token", new_callable=AsyncMock
        ) as mock_obtain_new_token:
            mock_obtain_new_token.return_value = "new_token_456"

            # Llamar al método
            result = await auth_service.refresh_token_if_needed()

            # Verificar que se intentó obtener un nuevo token
            mock_obtain_new_token.assert_called_once()

            # Verificar resultado
            assert result is True  # Fue necesario renovar
