from unittest.mock import AsyncMock, patch

import pytest

from app.services.ciudadano_service import CiudadanoService


@pytest.fixture
def mock_municipio_api():
    """Fixture para crear un mock del servicio de API municipal"""
    with patch("app.services.ciudadano_service.MunicipioAPIService") as mock:
        mock_instance = mock.return_value
        mock_instance.get = AsyncMock()
        mock_instance.post = AsyncMock()
        mock_instance.put = AsyncMock()
        yield mock_instance


@pytest.fixture
def ciudadano_service(mock_municipio_api):
    """Fixture para crear el servicio de ciudadano con API mock"""
    service = CiudadanoService()
    service.api_service = mock_municipio_api
    return service


class TestCiudadanoService:
    """Pruebas para el servicio de ciudadano"""

    @pytest.mark.asyncio
    async def test_get_info_ciudadano_success(
        self, ciudadano_service, mock_municipio_api
    ):
        """Prueba para obtener información de un ciudadano con éxito"""
        # Configurar el mock para simular una respuesta exitosa
        mock_municipio_api.get.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "nombre": "Juan",
                "apellido": "Pérez",
                "documento": "12345678",
                "telefono": "5491112345678",
            },
        }

        # Llamar al método y verificar el resultado
        result = await ciudadano_service.get_info_ciudadano("5491112345678")

        # Verificar que el método get fue llamado con los parámetros correctos
        mock_municipio_api.get.assert_called_once_with(
            "contribuyentes/celular", params={"telefono": "5491112345678"}
        )

        # Verificar la estructura y contenido del resultado
        assert result["success"] is True
        assert result["data"]["id_ciudadano"] == "123"
        assert result["data"]["nombre"] == "Juan"
        assert result["data"]["apellido"] == "Pérez"

    @pytest.mark.asyncio
    async def test_get_info_ciudadano_not_found(
        self, ciudadano_service, mock_municipio_api
    ):
        """Prueba para cuando no se encuentra el ciudadano"""
        # Configurar el mock para simular una respuesta sin datos
        mock_municipio_api.get.return_value = {"success": True, "data": []}

        # Llamar al método y verificar el resultado
        result = await ciudadano_service.get_info_ciudadano("5491112345678")

        # Verificar que el resultado indica que no se encontró un ciudadano
        assert result["success"] is False
        assert "No se encontró un ciudadano" in result["message"]

    @pytest.mark.asyncio
    async def test_get_info_ciudadano_api_error(
        self, ciudadano_service, mock_municipio_api
    ):
        """Prueba para cuando hay un error en la API"""
        # Configurar el mock para simular un error en la API
        mock_municipio_api.get.side_effect = Exception("Error de conexión")

        # Llamar al método y verificar el resultado
        result = await ciudadano_service.get_info_ciudadano("5491112345678")

        # Verificar que el resultado indica un error
        assert result["success"] is False
        assert "Error al obtener información del ciudadano" in result["message"]

    @pytest.mark.asyncio
    async def test_get_ciudadano_by_dni_success(
        self, ciudadano_service, mock_municipio_api
    ):
        """Prueba para obtener un ciudadano por DNI con éxito"""
        # Configurar el mock para simular una respuesta exitosa
        mock_municipio_api.get.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "nombre": "Juan",
                "apellido": "Pérez",
                "documento": "12345678",
                "telefono": "5491112345678",
            },
        }

        # Llamar al método y verificar el resultado
        result = await ciudadano_service.get_ciudadano_by_dni("12345678")

        # Verificar que el método get fue llamado con los parámetros correctos
        mock_municipio_api.get.assert_called_once_with(
            "contribuyentes/documento", params={"documento": "12345678"}
        )

        # Verificar la estructura y contenido del resultado
        assert result["success"] is True
        assert result["data"]["documento"] == "12345678"

    @pytest.mark.asyncio
    async def test_registrar_ciudadano_success(
        self, ciudadano_service, mock_municipio_api
    ):
        """Prueba para registrar un ciudadano con éxito"""
        # Configurar el mock para simular una respuesta exitosa
        mock_municipio_api.post.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "mensaje": "Ciudadano registrado correctamente",
            },
        }

        # Datos de prueba para registro
        nombre = "Juan"
        apellido = "Pérez"
        documento = "12345678"
        telefono = "5491112345678"
        email = "juan.perez@ejemplo.com"
        direccion = "Calle Principal 123"

        # Llamar al método y verificar el resultado
        result = await ciudadano_service.registrar_ciudadano(
            nombre, apellido, documento, telefono, email, direccion
        )

        # Verificar que el método post fue llamado con los parámetros correctos
        mock_municipio_api.post.assert_called_once_with(
            "ciudadanos",
            {
                "nombre": nombre,
                "apellido": apellido,
                "documento": documento,
                "telefono": telefono,
                "email": email,
                "direccion": direccion,
            },
        )

        # Verificar la estructura y contenido del resultado
        assert result["success"] is True
        assert result["data"]["id_ciudadano"] == "123"

    @pytest.mark.asyncio
    async def test_actualizar_ciudadano_telefono(
        self, ciudadano_service, mock_municipio_api
    ):
        """Prueba para actualizar el teléfono de un ciudadano"""
        # Configurar el mock para simular una respuesta exitosa
        mock_municipio_api.post.return_value = {
            "success": True,
            "mensaje": "Teléfono actualizado correctamente",
        }

        # ID y datos a actualizar
        id_ciudadano = "123"
        datos = {"telefono": "5491198765432"}

        # Llamar al método y verificar el resultado
        result = await ciudadano_service.actualizar_ciudadano(id_ciudadano, datos)

        # Verificar que el método post fue llamado con los parámetros correctos
        mock_municipio_api.post.assert_called_once_with(
            "contribuyentes/actualizar-celular",
            {"id_ciudadano": id_ciudadano, "telefono": datos["telefono"]},
        )

        # Verificar la estructura y contenido del resultado
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_actualizar_ciudadano_datos_generales(
        self, ciudadano_service, mock_municipio_api
    ):
        """Prueba para actualizar datos generales de un ciudadano"""
        # Configurar el mock para simular una respuesta exitosa
        mock_municipio_api.put.return_value = {
            "success": True,
            "mensaje": "Datos actualizados correctamente",
        }

        # ID y datos a actualizar
        id_ciudadano = "123"
        datos = {"direccion": "Nueva Dirección 456", "email": "nuevo@ejemplo.com"}

        # Llamar al método y verificar el resultado
        result = await ciudadano_service.actualizar_ciudadano(id_ciudadano, datos)

        # Verificar que el método put fue llamado con los parámetros correctos
        mock_municipio_api.put.assert_called_once_with(
            f"contribuyentes/{id_ciudadano}", datos
        )

        # Verificar la estructura y contenido del resultado
        assert result["success"] is True
