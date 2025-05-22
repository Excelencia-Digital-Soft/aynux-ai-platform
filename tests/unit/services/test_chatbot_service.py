import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ciudadano import ChatbotResponse, User, UserState
from app.models.message import Contact, TextMessage, WhatsAppMessage
from app.services.chatbot_service import ChatbotService


@pytest.fixture
def mock_dependencies():
    """Fixture para crear mocks de las dependencias del ChatbotService"""
    with (
        patch("app.services.chatbot_service.CiudadanoRepository") as mock_repo,
        patch("app.services.chatbot_service.RedisRepository") as mock_redis,
        patch("app.services.chatbot_service.CiudadanoService") as mock_ciudadano,
        patch("app.services.chatbot_service.WhatsAppService") as mock_whatsapp,
        patch("app.services.chatbot_service.AIService") as mock_ai,
        patch("app.services.chatbot_service.TramitesService") as mock_tramites,
        patch("app.services.chatbot_service.CertificateGenerator") as mock_cert,
    ):
        # Configurar los mocks para devolver instancias mock
        mock_repo_instance = mock_repo.return_value
        mock_redis_instance = mock_redis.return_value
        mock_ciudadano_instance = mock_ciudadano.return_value
        mock_whatsapp_instance = mock_whatsapp.return_value
        mock_ai_instance = mock_ai.return_value
        mock_tramites_instance = mock_tramites.return_value
        mock_cert_instance = mock_cert.return_value

        # Configurar métodos asíncronos
        mock_ciudadano_instance.get_info_ciudadano = AsyncMock()
        mock_whatsapp_instance.enviar_mensaje_texto = AsyncMock()
        mock_whatsapp_instance.enviar_documento = AsyncMock()
        mock_ai_instance.generate_principal_mensaje = AsyncMock()
        mock_ai_instance.verificar_ciudadano = AsyncMock()
        mock_tramites_instance.get_tramites_disponibles = AsyncMock()
        mock_cert_instance.generate_qr_certificate = AsyncMock()

        # Métodos del repositorio
        mock_repo_instance.get_user = MagicMock()
        mock_repo_instance.create_user = MagicMock()
        mock_repo_instance.update_user = MagicMock()
        mock_repo_instance.update_user_state = MagicMock()
        mock_repo_instance.add_user = MagicMock()

        # Métodos del repositorio de Redis
        mock_redis_instance.save_conversation_history = MagicMock()
        mock_redis_instance.get_conversation_history = MagicMock()

        yield {
            "repo": mock_repo_instance,
            "redis": mock_redis_instance,
            "ciudadano": mock_ciudadano_instance,
            "whatsapp": mock_whatsapp_instance,
            "ai": mock_ai_instance,
            "tramites": mock_tramites_instance,
            "cert": mock_cert_instance,
        }


@pytest.fixture
def chatbot_service(mock_dependencies):
    """Fixture para crear el servicio de chatbot con dependencias mock"""
    service = ChatbotService()
    service.user_repo = mock_dependencies["repo"]
    service.redis_repo = mock_dependencies["redis"]
    service.ciudadano_service = mock_dependencies["ciudadano"]
    service.whatsapp_service = mock_dependencies["whatsapp"]
    service.ai_service = mock_dependencies["ai"]
    service.tramites_service = mock_dependencies["tramites"]
    service.certificate_generator = mock_dependencies["cert"]
    return service


@pytest.fixture
def sample_message():
    """Fixture para crear un mensaje de WhatsApp de ejemplo"""
    return WhatsAppMessage(
        from_="5491112345678",
        id="wamid.123",
        timestamp="1621234567890",
        type="text",
        text=TextMessage(body="Hola, quiero consultar mi deuda"),
    )


@pytest.fixture
def sample_contact():
    """Fixture para crear un contacto de WhatsApp de ejemplo"""
    return Contact(wa_id="5491112345678", profile={"name": "Juan Pérez"})


@pytest.mark.asyncio(scope="session")
class TestChatbotService:
    """Pruebas para el servicio de chatbot"""

    async def test_procesar_mensaje_usuario_nuevo(
        self, chatbot_service, mock_dependencies, sample_message, sample_contact
    ):
        """Prueba para procesar un mensaje de un usuario nuevo"""
        # Configurar mocks
        mock_dependencies["repo"].get_user.return_value = None
        mock_dependencies["repo"].add_user.return_value = User(
            phone_number="5491112345678",
            state=UserState(state="inicio", verificado=False, id_ciudadano="123"),
        )

        mock_dependencies["ciudadano"].get_info_ciudadano.side_effect = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "id_ciudadano": "123",
                    "nombre": "Juan",
                    "apellido": "Pérez",
                    "documento": "12345678",
                    "telefono": "5491112345678",
                },
            }
        )

        mock_dependencies["whatsapp"].enviar_mensaje_texto.side_effect = AsyncMock(
            return_value={"success": True}
        )

        # Llamar al método y verificar el resultado
        result = await chatbot_service.procesar_mensaje(sample_message, sample_contact)

        # Verificar que se verificó la información del ciudadano
        mock_dependencies["ciudadano"].get_info_ciudadano.assert_called_once_with(
            sample_contact.wa_id
        )

        # Verificar que se actualizó el estado del usuario
        mock_dependencies["repo"].update_user_state.assert_called_once_with(
            sample_contact.wa_id, "verificar"
        )

        # Verificar que se envió un mensaje de verificación
        mock_dependencies["whatsapp"].enviar_mensaje_texto.assert_called_once()
        args, _ = mock_dependencies["whatsapp"].enviar_mensaje_texto.call_args
        assert args[0] == sample_contact.wa_id
        assert "confirme" in args[1]

        # Verificar el resultado
        assert result["status"] == "success"
        assert result["state"] == "verificar"

    @pytest.mark.asyncio
    async def test_procesar_usuario_verificando_afirmacion(
        self, chatbot_service, mock_dependencies, sample_message, sample_contact
    ):
        """Prueba para procesar un mensaje de verificación con respuesta afirmativa"""
        # Configurar mocks
        mock_dependencies["repo"].get_user.return_value = User(
            phone_number="5491112345678",
            state=UserState(state="verificar", verificado=False, id_ciudadano="123"),
        )

        mock_dependencies["ciudadano"].get_info_ciudadano.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "nombre": "Juan",
                "apellido": "Pérez",
                "documento": "12345678",
                "telefono": "5491112345678",
            },
        }

        mock_dependencies["ai"].verificar_ciudadano.return_value = "afirmacion"
        mock_dependencies["whatsapp"].enviar_mensaje_texto.return_value = {
            "success": True
        }

        # Llamar al método y verificar el resultado
        result = await chatbot_service.procesar_mensaje(sample_message, sample_contact)

        # Verificar que se usó el servicio de AI para verificar la respuesta
        mock_dependencies["ai"].verificar_ciudadano.assert_called_once_with(
            sample_message.text.body
        )

        # Verificar que se actualizó el estado del usuario a verificado
        mock_dependencies["repo"].update_user.assert_called_once()
        args, _ = mock_dependencies["repo"].update_user.call_args
        assert args[0] == sample_contact.wa_id
        assert args[1] == "verificado"
        assert args[2] is True

        # Verificar que se envió un mensaje de confirmación
        mock_dependencies["whatsapp"].enviar_mensaje_texto.assert_called_once()
        args, _ = mock_dependencies["whatsapp"].enviar_mensaje_texto.call_args
        assert "Gracias por confirmar" in args[1]

        # Verificar el resultado
        assert result["status"] == "success"
        assert result["state"] == "verificado"

    @pytest.mark.asyncio
    async def test_procesar_usuario_verificado_consulta_deuda(
        self, chatbot_service, mock_dependencies, sample_message, sample_contact
    ):
        """Prueba para procesar una consulta de deuda de un usuario verificado"""
        # Configurar mocks
        mock_dependencies["repo"].get_user.return_value = User(
            phone_number="5491112345678",
            state=UserState(state="verificado", verificado=True, id_ciudadano="123"),
        )

        mock_dependencies["ciudadano"].get_info_ciudadano.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "nombre": "Juan",
                "apellido": "Pérez",
                "documento": "12345678",
                "telefono": "5491112345678",
            },
        }

        mock_dependencies["redis"].get_conversation_history.return_value = [
            {"role": "persona", "content": "Hola"},
            {"role": "bot", "content": "Hola, ¿en qué puedo ayudarte?"},
        ]

        mock_dependencies["tramites"].get_tramites_disponibles.return_value = {
            "success": True,
            "data": [
                {
                    "id": "1",
                    "nombre": "Consulta de deudas",
                    "descripcion": "Consulta tus deudas municipales",
                },
                {
                    "id": "2",
                    "nombre": "Certificado de residencia",
                    "descripcion": "Solicita un certificado de residencia",
                },
            ],
        }

        # Configurar la respuesta de la IA indicando consulta de deuda
        mock_dependencies["ai"].generate_principal_mensaje.side_effect = AsyncMock(
            return_value=ChatbotResponse(
                mensaje="Entiendo que quieres consultar tu deuda. Voy a buscar esa información.",
                estado="consulta_deuda",
            )
        )

        # Configurar respuesta del servicio de trámites
        # Usar AsyncMock para asegurar que devuelve una corrutina
        mock_result = {
            "success": True,
            "data": [
                {
                    "concepto": "Tasa municipal",
                    "monto": 1500.0,
                    "vencimiento": "2023-12-10",
                },
                {"concepto": "Alumbrado", "monto": 800.0, "vencimiento": "2023-12-15"},
            ],
        }

        # Reemplazar el método completo con un AsyncMock que devuelva el resultado esperado
        mock_dependencies["tramites"].obtener_deuda_contribuyente = AsyncMock(
            return_value=mock_result
        )

        # Llamar al método y verificar el resultado
        result = await chatbot_service.procesar_mensaje(sample_message, sample_contact)

        # Verificar que se utilizó la IA para generar la respuesta
        mock_dependencies["ai"].generate_principal_mensaje.assert_called_once()

        # Verificar que se consultó la deuda
        mock_dependencies[
            "tramites"
        ].obtener_deuda_contribuyente.assert_called_once_with("123")

        # Verificar que se envió un mensaje con la deuda
        mock_dependencies["whatsapp"].enviar_mensaje_texto.assert_called_once()
        args, _ = mock_dependencies["whatsapp"].enviar_mensaje_texto.call_args
        assert "deuda total" in args[1].lower()
        assert "Tasa municipal" in args[1]
        assert "1500.0" in args[1]

        # Verificar el resultado
        assert result["status"] == "success"
        assert result["state"] == "consulta_deuda"

    @pytest.mark.asyncio
    async def test_procesar_usuario_verificado_solicitud_certificado(
        self, chatbot_service, mock_dependencies, sample_message, sample_contact
    ):
        """Prueba para procesar una solicitud de certificado de un usuario verificado"""
        # Configurar mocks
        mock_dependencies["repo"].get_user.return_value = User(
            phone_number="5491112345678",
            state=UserState(state="verificado", verificado=True, id_ciudadano="123"),
        )

        mock_dependencies["ciudadano"].get_info_ciudadano.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "nombre": "Juan",
                "apellido": "Pérez",
                "documento": "12345678",
                "telefono": "5491112345678",
            },
        }

        mock_dependencies["redis"].get_conversation_history.return_value = [
            {"role": "persona", "content": "Hola"},
            {"role": "bot", "content": "Hola, ¿en qué puedo ayudarte?"},
        ]

        mock_dependencies["tramites"].get_tramites_disponibles.return_value = {
            "success": True,
            "data": [
                {
                    "id": "1",
                    "nombre": "Consulta de deudas",
                    "descripcion": "Consulta tus deudas municipales",
                },
                {
                    "id": "2",
                    "nombre": "Certificado de residencia",
                    "descripcion": "Solicita un certificado de residencia",
                },
            ],
        }

        # Configurar la respuesta de la IA indicando solicitud de certificado
        mock_dependencies["ai"].generate_principal_mensaje.side_effect = AsyncMock(
            return_value=ChatbotResponse(
                mensaje="Entiendo que necesitas un certificado de residencia. Te lo genero de inmediato.",
                estado="certificados",
            )
        )

        # Configurar respuesta del generador de certificados
        cert_bytes = b"certificado_simulado_en_bytes"
        mock_dependencies["cert"].generate_qr_certificate.return_value = cert_bytes

        # Configurar respuesta del servicio de WhatsApp
        mock_dependencies["whatsapp"].enviar_documento.return_value = {"success": True}
        mock_dependencies["whatsapp"].enviar_mensaje_texto.return_value = {
            "success": True
        }

        # Llamar al método y verificar el resultado
        result = await chatbot_service.procesar_mensaje(sample_message, sample_contact)

        # Verificar que se utilizó la IA para generar la respuesta
        mock_dependencies["ai"].generate_principal_mensaje.assert_called_once()

        # Verificar que se generó el certificado
        mock_dependencies["cert"].generate_qr_certificate.assert_called_once_with(
            "Juan Pérez", "12345678", "123"
        )

        # Verificar que se envió el documento
        mock_dependencies["whatsapp"].enviar_documento.assert_called_once_with(
            "5491112345678", cert_bytes, "Certificado de Residencia"
        )

        # Verificar que se envió un mensaje de confirmación
        mock_dependencies["whatsapp"].enviar_mensaje_texto.assert_called_once()
        args, _ = mock_dependencies["whatsapp"].enviar_mensaje_texto.call_args
        assert "certificado" in args[1].lower()

        # Verificar el resultado
        assert result["status"] == "success"
        assert result["state"] == "certificados"

    @pytest.mark.asyncio
    async def test_procesar_mensaje_error_info_ciudadano(
        self, chatbot_service, mock_dependencies, sample_message, sample_contact
    ):
        """Prueba para manejar errores al obtener información del ciudadano"""
        # Configurar mocks para simular un error
        mock_dependencies["ciudadano"].get_info_ciudadano.return_value = {
            "success": False,
            "message": "Error al obtener información del ciudadano",
        }

        # Llamar al método y verificar el resultado
        result = await chatbot_service.procesar_mensaje(sample_message, sample_contact)

        # Verificar que se envió un mensaje de error
        mock_dependencies["whatsapp"].enviar_mensaje_texto.assert_called_once()
        args, _ = mock_dependencies["whatsapp"].enviar_mensaje_texto.call_args
        assert "no se pudo obtener su información" in args[1].lower()

        # Verificar el resultado
        assert result["status"] == "error"
        assert "No se pudo obtener información" in result["message"]

    @pytest.mark.asyncio
    async def test_extract_message_text_tipos(self, chatbot_service):
        """Prueba para extraer texto de diferentes tipos de mensajes"""
        # Mensaje de texto
        text_message = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.123",
            timestamp="1621234567890",
            type="text",
            text=TextMessage(body="Hola, este es un mensaje de texto"),
        )
        assert (
            chatbot_service._extract_message_text(text_message)
            == "Hola, este es un mensaje de texto"
        )

        # Mensaje interactivo con botón
        from app.models.message import InteractiveContent, ButtonReply

        button_message = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.123",
            timestamp="1621234567890",
            type="interactive",
            interactive=InteractiveContent(
                type="button_reply",
                button_reply=ButtonReply(id="si", title="Sí, soy yo"),
            ),
        )
        assert chatbot_service._extract_message_text(button_message) == "Sí, soy yo"

        # Mensaje interactivo con lista
        from app.models.message import ListReply

        list_message = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.123",
            timestamp="1621234567890",
            type="interactive",
            interactive=InteractiveContent(
                type="list_reply",
                list_reply=ListReply(
                    id="1", title="Consulta de deudas", description="Ver mis deudas"
                ),
            ),
        )
        assert (
            chatbot_service._extract_message_text(list_message) == "Consulta de deudas"
        )

        # Tipo de mensaje no soportado
        unsupported_message = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.123",
            timestamp="1621234567890",
            type="image",
        )
        assert chatbot_service._extract_message_text(unsupported_message) == ""
