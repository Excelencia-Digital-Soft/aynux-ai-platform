from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.config.settings import Settings
from app.services.whatsapp_service import WhatsAppService


@pytest.fixture
def mock_settings():
    """Fixture para crear configuraciones mock"""
    settings = MagicMock(spec=Settings)
    settings.WHATSAPP_API_BASE = "https://graph.facebook.com"
    settings.WHATSAPP_API_VERSION = "v18.0"
    settings.PHONE_NUMBER_ID = "123456789"
    settings.ACCESS_TOKEN = "test_token"
    return settings


@pytest.fixture
def whatsapp_service(mock_settings):
    """Fixture para crear el servicio de WhatsApp con configuraciones mock"""
    with patch("app.services.whatsapp_service.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings
        service = WhatsAppService()
        return service


class TestWhatsAppService:
    """Pruebas para el servicio de WhatsApp"""

    @pytest.mark.asyncio
    async def test_enviar_mensaje_texto_success(self, whatsapp_service):
        """Prueba para enviar un mensaje de texto con éxito"""
        # Datos de prueba
        numero = "5491112345678"
        mensaje = "Hola, este es un mensaje de prueba"

        # Respuesta simulada de la API
        api_response = {
            "messaging_product": "whatsapp",
            "contacts": [{"wa_id": numero, "input": mensaje}],
            "messages": [{"id": "wamid.123"}],
        }

        # Simular la respuesta HTTP
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock()
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = api_response
            mock_post.return_value.raise_for_status = MagicMock()

            # Llamar al método y verificar el resultado
            result = await whatsapp_service.enviar_mensaje_texto(numero, mensaje)

            # Verificar que la petición POST se hizo correctamente
            expected_url = f"{whatsapp_service.base_url}/{whatsapp_service.version}/{whatsapp_service.phone_number_id}/messages"
            expected_headers = {
                "Authorization": f"Bearer {whatsapp_service.access_token}",
                "Content-Type": "application/json",
            }
            expected_payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": numero,
                "type": "text",
                "text": {"body": mensaje},
            }

            mock_post.assert_called_once_with(
                expected_url,
                json=expected_payload,
                headers=expected_headers,
                timeout=10.0,
            )

            # Verificar que el resultado contiene la respuesta de la API
            assert result == api_response

    @pytest.mark.asyncio
    async def test_enviar_mensaje_texto_error(self, whatsapp_service):
        """Prueba para enviar un mensaje de texto con error"""
        # Datos de prueba
        numero = "5491112345678"
        mensaje = "Hola, este es un mensaje de prueba"

        # Simular un error HTTP
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.RequestError("Error de conexión")

            # Llamar al método y verificar el resultado
            result = await whatsapp_service.enviar_mensaje_texto(numero, mensaje)

            # Verificar que el resultado indica un error
            assert result["success"] is False
            assert "Error de conexión" in result["error"]

    @pytest.mark.asyncio
    async def test_enviar_documento_success(self, whatsapp_service):
        """Prueba para enviar un documento con éxito"""
        # Datos de prueba
        numero = "5491112345678"
        archivo = b"contenido_del_archivo"
        nombre = "documento.pdf"
        caption = "Este es un documento importante"

        # Respuesta simulada de la API
        api_response = {
            "messaging_product": "whatsapp",
            "contacts": [{"wa_id": numero}],
            "messages": [{"id": "wamid.123"}],
        }

        # Simular la respuesta HTTP
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock()
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = api_response
            mock_post.return_value.raise_for_status = MagicMock()

            # Llamar al método y verificar el resultado
            result = await whatsapp_service.enviar_documento(
                numero, archivo, nombre, caption
            )

            # Verificar que la petición POST se hizo correctamente
            mock_post.assert_called_once()

            # Verificar que el payload incluye el nombre del documento y la descripción
            _, kwargs = mock_post.call_args
            payload = kwargs["json"]
            assert payload["messaging_product"] == "whatsapp"
            assert payload["type"] == "document"
            assert payload["document"]["filename"] == nombre
            assert payload["document"]["caption"] == caption

            # Verificar que el resultado contiene la respuesta de la API
            assert result == api_response

    @pytest.mark.asyncio
    async def test_enviar_ubicacion_success(self, whatsapp_service):
        """Prueba para enviar una ubicación con éxito"""
        # Datos de prueba
        numero = "5491112345678"
        latitud = -34.603722
        longitud = -58.381592
        nombre = "Plaza de Mayo"

        # Respuesta simulada de la API
        api_response = {
            "messaging_product": "whatsapp",
            "contacts": [{"wa_id": numero}],
            "messages": [{"id": "wamid.123"}],
        }

        # Simular la respuesta HTTP
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock()
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = api_response
            mock_post.return_value.raise_for_status = MagicMock()

            # Llamar al método y verificar el resultado
            result = await whatsapp_service.enviar_ubicacion(
                numero, latitud, longitud, nombre
            )

            # Verificar que la petición POST se hizo correctamente
            mock_post.assert_called_once()

            # Verificar que el payload incluye la ubicación y el nombre
            _, kwargs = mock_post.call_args
            payload = kwargs["json"]
            assert payload["messaging_product"] == "whatsapp"
            assert payload["type"] == "location"
            assert payload["location"]["latitude"] == latitud
            assert payload["location"]["longitude"] == longitud
            assert payload["location"]["name"] == nombre

            # Verificar que el resultado contiene la respuesta de la API
            assert result == api_response

    @pytest.mark.asyncio
    async def test_enviar_lista_opciones_success(self, whatsapp_service):
        """Prueba para enviar una lista de opciones con éxito"""
        # Datos de prueba
        numero = "5491112345678"
        titulo = "Servicios Municipales"
        cuerpo = "Seleccione una opción para continuar:"
        opciones = [
            {
                "id": "1",
                "titulo": "Consulta de deudas",
                "descripcion": "Consulte sus deudas municipales",
            },
            {
                "id": "2",
                "titulo": "Certificados",
                "descripcion": "Solicite certificados municipales",
            },
        ]

        # Respuesta simulada de la API
        api_response = {
            "messaging_product": "whatsapp",
            "contacts": [{"wa_id": numero}],
            "messages": [{"id": "wamid.123"}],
        }

        # Simular la respuesta HTTP
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock()
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = api_response
            mock_post.return_value.raise_for_status = MagicMock()

            # Llamar al método y verificar el resultado
            result = await whatsapp_service.enviar_lista_opciones(
                numero, titulo, cuerpo, opciones
            )

            # Verificar que la petición POST se hizo correctamente
            mock_post.assert_called_once()

            # Verificar que el payload incluye el título, cuerpo y opciones
            _, kwargs = mock_post.call_args
            payload = kwargs["json"]
            assert payload["messaging_product"] == "whatsapp"
            assert payload["type"] == "interactive"
            assert payload["interactive"]["type"] == "list"
            assert payload["interactive"]["header"]["text"] == titulo
            assert payload["interactive"]["body"]["text"] == cuerpo

            # Verificar que se incluyen las opciones
            rows = payload["interactive"]["action"]["sections"][0]["rows"]
            assert len(rows) == 2
            assert rows[0]["id"] == "1"
            assert rows[0]["title"] == "Consulta de deudas"
            assert rows[1]["id"] == "2"
            assert rows[1]["title"] == "Certificados"

            # Verificar que el resultado contiene la respuesta de la API
            assert result == api_response

    @pytest.mark.asyncio
    async def test_enviar_botones_success(self, whatsapp_service):
        """Prueba para enviar botones interactivos con éxito"""
        # Datos de prueba
        numero = "5491112345678"
        titulo = "Confirmación"
        cuerpo = "¿Es usted Juan Pérez?"
        botones = [
            {"id": "si", "titulo": "Sí, soy yo"},
            {"id": "no", "titulo": "No, no soy yo"},
        ]

        # Respuesta simulada de la API
        api_response = {
            "messaging_product": "whatsapp",
            "contacts": [{"wa_id": numero}],
            "messages": [{"id": "wamid.123"}],
        }

        # Simular la respuesta HTTP
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock()
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = api_response
            mock_post.return_value.raise_for_status = MagicMock()

            # Llamar al método y verificar el resultado
            result = await whatsapp_service.enviar_botones(
                numero, titulo, cuerpo, botones
            )

            # Verificar que la petición POST se hizo correctamente
            mock_post.assert_called_once()

            # Verificar que el payload incluye el título, cuerpo y botones
            _, kwargs = mock_post.call_args
            payload = kwargs["json"]
            assert payload["messaging_product"] == "whatsapp"
            assert payload["type"] == "interactive"
            assert payload["interactive"]["type"] == "button"
            assert payload["interactive"]["header"]["text"] == titulo
            assert payload["interactive"]["body"]["text"] == cuerpo

            # Verificar que se incluyen los botones
            buttons = payload["interactive"]["action"]["buttons"]
            assert len(buttons) == 2
            assert buttons[0]["reply"]["id"] == "si"
            assert buttons[0]["reply"]["title"] == "Sí, soy yo"
            assert buttons[1]["reply"]["id"] == "no"
            assert buttons[1]["reply"]["title"] == "No, no soy yo"

            # Verificar que el resultado contiene la respuesta de la API
            assert result == api_response
