import pytest

from app.models.ciudadano import ChatbotResponse, User, UserState
from app.models.message import TextMessage, WhatsAppMessage
from app.services.chatbot_service import ChatbotService


class TestIntegrationFlow:
    """Pruebas de integración para flujos completos de mensajes"""

    @pytest.mark.asyncio
    async def test_flujo_verificacion_usuario(
        self,
        sample_message,
        sample_contact,
        mock_ciudadano_service,
        mock_whatsapp_service,
        mock_ai_service,
        mock_redis_repository,
        mock_ciudadano_repository,
    ):
        """
        Prueba el flujo completo de verificación de un usuario:
        1. Usuario envía mensaje inicial
        2. Sistema verifica si el usuario existe
        3. Sistema envía mensaje de verificación
        4. Usuario confirma su identidad
        5. Sistema actualiza el estado y envía mensaje de bienvenida
        """
        # Crear servicio de chatbot con mocks
        chatbot_service = ChatbotService()
        chatbot_service.user_repo = mock_ciudadano_repository
        chatbot_service.redis_repo = mock_redis_repository
        chatbot_service.ciudadano_service = mock_ciudadano_service
        chatbot_service.whatsapp_service = mock_whatsapp_service
        chatbot_service.ai_service = mock_ai_service

        # Configurar escenario inicial: usuario nuevo
        mock_ciudadano_repository.get_user.return_value = None
        mock_ciudadano_repository.add_user.return_value = User(
            phone_number="5491112345678",
            state=UserState(state="inicio", verificado=False, id_ciudadano="123"),
        )

        # Configurar info del ciudadano
        mock_ciudadano_service.get_info_ciudadano.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "nombre": "Juan",
                "apellido": "Pérez",
                "documento": "12345678",
                "telefono": "5491112345678",
            },
        }

        # PASO 1: Mensaje inicial
        message_initial = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.123",
            timestamp="1621234567890",
            type="text",
            text=TextMessage(body="Hola"),
        )

        # Procesar mensaje inicial
        result_initial = await chatbot_service.procesar_mensaje(
            message_initial, sample_contact
        )

        # Verificar que se actualizó el estado a "verificar"
        mock_ciudadano_repository.update_user_state.assert_called_once_with(
            "5491112345678", "verificar"
        )

        # Verificar que se envió un mensaje de verificación
        mock_whatsapp_service.enviar_mensaje_texto.assert_called_once()
        args, _ = mock_whatsapp_service.enviar_mensaje_texto.call_args
        assert "Juan Pérez" in args[1]
        assert "confirme" in args[1].lower()

        # PASO 2: Usuario confirma su identidad
        # Actualizar estado del mock para el siguiente paso
        mock_ciudadano_repository.get_user.return_value = User(
            phone_number="5491112345678",
            state=UserState(state="verificar", verificado=False, id_ciudadano="123"),
        )

        # Configurar respuesta de la IA para verificación
        mock_ai_service.verificar_ciudadano.return_value = "afirmacion"

        # Resetear el mock de enviar mensaje para verificar la siguiente llamada
        mock_whatsapp_service.enviar_mensaje_texto.reset_mock()

        # Mensaje de confirmación del usuario
        message_confirm = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.124",
            timestamp="1621234567891",
            type="text",
            text=TextMessage(body="Sí, soy yo"),
        )

        # Procesar mensaje de confirmación
        result_confirm = await chatbot_service.procesar_mensaje(
            message_confirm, sample_contact
        )

        # Verificar que se llamó al servicio de IA para verificar la respuesta
        mock_ai_service.verificar_ciudadano.assert_called_once_with("Sí, soy yo")

        # Verificar que se actualizó el estado a "verificado"
        mock_ciudadano_repository.update_user.assert_called_once()
        args, _ = mock_ciudadano_repository.update_user.call_args
        assert args[0] == "5491112345678"
        assert args[1] == "verificado"
        assert args[2] is True

        # Verificar que se envió un mensaje de bienvenida
        mock_whatsapp_service.enviar_mensaje_texto.assert_called_once()
        args, _ = mock_whatsapp_service.enviar_mensaje_texto.call_args
        assert "Gracias por confirmar" in args[1]

        # Verificar el estado final
        assert result_confirm["status"] == "success"
        assert result_confirm["state"] == "verificado"

    @pytest.mark.asyncio
    async def test_flujo_consulta_deuda(
        self,
        sample_message,
        sample_contact,
        sample_user,
        sample_tramites_data,
        sample_deuda_data,
        mock_ciudadano_service,
        mock_whatsapp_service,
        mock_ai_service,
        mock_redis_repository,
        mock_ciudadano_repository,
        mock_tramites_service,
    ):
        """
        Prueba el flujo completo de consulta de deuda:
        1. Usuario verificado envía consulta de deuda
        2. Sistema procesa con IA y detecta intención
        3. Sistema consulta deuda en servicio de trámites
        4. Sistema envía respuesta con detalle de deuda
        """
        # Crear servicio de chatbot con mocks
        chatbot_service = ChatbotService()
        chatbot_service.user_repo = mock_ciudadano_repository
        chatbot_service.redis_repo = mock_redis_repository
        chatbot_service.ciudadano_service = mock_ciudadano_service
        chatbot_service.whatsapp_service = mock_whatsapp_service
        chatbot_service.ai_service = mock_ai_service
        chatbot_service.tramites_service = mock_tramites_service

        # Configurar escenario: usuario ya verificado
        mock_ciudadano_repository.get_user.return_value = sample_user

        # Configurar info del ciudadano
        mock_ciudadano_service.get_info_ciudadano.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "nombre": "Juan",
                "apellido": "Pérez",
                "documento": "12345678",
                "telefono": "5491112345678",
            },
        }

        # Configurar historial de conversación
        mock_redis_repository.get_conversation_history.return_value = [
            {"role": "persona", "content": "Hola"},
            {"role": "bot", "content": "Hola, ¿en qué puedo ayudarte?"},
        ]

        # Configurar trámites disponibles
        mock_tramites_service.get_tramites_disponibles.return_value = {
            "success": True,
            "data": sample_tramites_data,
        }

        # Configurar respuesta de la IA indicando consulta de deuda
        mock_ai_service.generate_principal_mensaje.return_value = ChatbotResponse(
            mensaje="Entiendo que quieres consultar tu deuda municipal. Voy a buscar esa información para ti.",
            estado="consulta_deuda",
        )

        # Configurar respuesta del servicio de trámites con la deuda
        mock_tramites_service.obtener_deuda_contribuyente.return_value = {
            "success": True,
            "data": sample_deuda_data,
        }

        # Mensaje del usuario
        message = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.125",
            timestamp="1621234567892",
            type="text",
            text=TextMessage(body="Quiero consultar mi deuda municipal"),
        )

        # Procesar mensaje
        result = await chatbot_service.procesar_mensaje(message, sample_contact)

        # Verificar que se llamó al servicio de IA para procesar el mensaje
        mock_ai_service.generate_principal_mensaje.assert_called_once()
        args, _ = mock_ai_service.generate_principal_mensaje.call_args
        assert args[0] == "Juan Pérez"  # nombre_completo
        assert args[3] == sample_tramites_data  # tramites
        assert args[4] is True  # verificado
        assert args[5] == "12345678"  # documento
        assert args[6] == "Quiero consultar mi deuda municipal"  # message

        # Verificar que se consultó la deuda
        mock_tramites_service.obtener_deuda_contribuyente.assert_called_once_with("123")

        # Verificar que se envió un mensaje con la deuda
        mock_whatsapp_service.enviar_mensaje_texto.assert_called_once()
        args, _ = mock_whatsapp_service.enviar_mensaje_texto.call_args

        # Verificar que el mensaje contiene la información de la deuda
        mensaje_enviado = args[1]
        assert "deuda total" in mensaje_enviado.lower()
        assert "4800" in mensaje_enviado  # Suma de todas las deudas
        assert "Tasa municipal" in mensaje_enviado
        assert "Alumbrado público" in mensaje_enviado
        assert "Impuesto inmobiliario" in mensaje_enviado

        # Verificar el resultado
        assert result["status"] == "success"
        assert result["state"] == "consulta_deuda"

    @pytest.mark.asyncio
    async def test_flujo_solicitud_certificado(
        self,
        sample_message,
        sample_contact,
        sample_user,
        sample_tramites_data,
        mock_ciudadano_service,
        mock_whatsapp_service,
        mock_ai_service,
        mock_redis_repository,
        mock_ciudadano_repository,
        mock_tramites_service,
        mock_certificate_generator,
    ):
        """
        Prueba el flujo completo de solicitud de certificado:
        1. Usuario verificado solicita un certificado
        2. Sistema procesa con IA y detecta intención
        3. Sistema genera el certificado
        4. Sistema envía el certificado al usuario
        """
        # Crear servicio de chatbot con mocks
        chatbot_service = ChatbotService()
        chatbot_service.user_repo = mock_ciudadano_repository
        chatbot_service.redis_repo = mock_redis_repository
        chatbot_service.ciudadano_service = mock_ciudadano_service
        chatbot_service.whatsapp_service = mock_whatsapp_service
        chatbot_service.ai_service = mock_ai_service
        chatbot_service.tramites_service = mock_tramites_service
        chatbot_service.certificate_generator = mock_certificate_generator

        # Configurar escenario: usuario ya verificado
        mock_ciudadano_repository.get_user.return_value = sample_user

        # Configurar info del ciudadano
        mock_ciudadano_service.get_info_ciudadano.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "nombre": "Juan",
                "apellido": "Pérez",
                "documento": "12345678",
                "telefono": "5491112345678",
            },
        }

        # Configurar historial de conversación
        mock_redis_repository.get_conversation_history.return_value = [
            {"role": "persona", "content": "Hola"},
            {"role": "bot", "content": "Hola, ¿en qué puedo ayudarte?"},
        ]

        # Configurar trámites disponibles
        mock_tramites_service.get_tramites_disponibles.return_value = {
            "success": True,
            "data": sample_tramites_data,
        }

        # Configurar respuesta de la IA indicando solicitud de certificado
        mock_ai_service.generate_principal_mensaje.return_value = ChatbotResponse(
            mensaje="Entiendo que necesitas un certificado de residencia. Te lo genero de inmediato.",
            estado="certificados",
        )

        # Configurar respuesta del generador de certificados
        mock_certificate_generator.generate_qr_certificate.return_value = (
            b"certificado_simulado_en_bytes"
        )

        # Configurar respuestas del servicio de WhatsApp
        mock_whatsapp_service.enviar_documento.return_value = {"success": True}
        mock_whatsapp_service.enviar_mensaje_texto.return_value = {"success": True}

        # Mensaje del usuario
        message = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.126",
            timestamp="1621234567893",
            type="text",
            text=TextMessage(body="Necesito un certificado de residencia"),
        )

        # Procesar mensaje
        result = await chatbot_service.procesar_mensaje(message, sample_contact)

        # Verificar que se llamó al servicio de IA para procesar el mensaje
        mock_ai_service.generate_principal_mensaje.assert_called_once()

        # Verificar que se generó el certificado
        mock_certificate_generator.generate_qr_certificate.assert_called_once_with(
            "Juan Pérez", "12345678", "123"
        )

        # Verificar que se envió el documento
        mock_whatsapp_service.enviar_documento.assert_called_once_with(
            "5491112345678",
            b"certificado_simulado_en_bytes",
            "Certificado de Residencia",
        )

        # Verificar que se envió un mensaje de texto explicativo
        mock_whatsapp_service.enviar_mensaje_texto.assert_called_once()
        args, _ = mock_whatsapp_service.enviar_mensaje_texto.call_args
        assert "certificado" in args[1].lower()
        assert "residencia" in args[1].lower()

        # Verificar el resultado
        assert result["status"] == "success"
        assert result["state"] == "certificados"

    @pytest.mark.asyncio
    async def test_flujo_consulta_tramites(
        self,
        sample_message,
        sample_contact,
        sample_user,
        sample_tramites_data,
        mock_ciudadano_service,
        mock_whatsapp_service,
        mock_ai_service,
        mock_redis_repository,
        mock_ciudadano_repository,
        mock_tramites_service,
    ):
        """
        Prueba el flujo completo de consulta de trámites disponibles:
        1. Usuario verificado consulta los trámites disponibles
        2. Sistema procesa con IA y detecta intención
        3. Sistema consulta los trámites disponibles
        4. Sistema envía lista de trámites al usuario
        """
        # Crear servicio de chatbot con mocks
        chatbot_service = ChatbotService()
        chatbot_service.user_repo = mock_ciudadano_repository
        chatbot_service.redis_repo = mock_redis_repository
        chatbot_service.ciudadano_service = mock_ciudadano_service
        chatbot_service.whatsapp_service = mock_whatsapp_service
        chatbot_service.ai_service = mock_ai_service
        chatbot_service.tramites_service = mock_tramites_service

        # Configurar escenario: usuario ya verificado
        mock_ciudadano_repository.get_user.return_value = sample_user

        # Configurar info del ciudadano
        mock_ciudadano_service.get_info_ciudadano.return_value = {
            "success": True,
            "data": {
                "id_ciudadano": "123",
                "nombre": "Juan",
                "apellido": "Pérez",
                "documento": "12345678",
                "telefono": "5491112345678",
            },
        }

        # Configurar historial de conversación
        mock_redis_repository.get_conversation_history.return_value = [
            {"role": "persona", "content": "Hola"},
            {"role": "bot", "content": "Hola, ¿en qué puedo ayudarte?"},
        ]

        # Configurar trámites disponibles
        mock_tramites_service.get_tramites_disponibles.return_value = {
            "success": True,
            "data": sample_tramites_data,
        }

        # Configurar respuesta de la IA indicando consulta de trámites
        mock_ai_service.generate_principal_mensaje.return_value = ChatbotResponse(
            mensaje="Claro, te muestro los trámites disponibles en la municipalidad.",
            estado="tramites",
        )

        # Mensaje del usuario
        message = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.127",
            timestamp="1621234567894",
            type="text",
            text=TextMessage(body="¿Qué trámites puedo hacer?"),
        )

        # Procesar mensaje
        result = await chatbot_service.procesar_mensaje(message, sample_contact)

        # Verificar que se llamó al servicio de IA para procesar el mensaje
        mock_ai_service.generate_principal_mensaje.assert_called_once()

        # Verificar que se consultaron los trámites disponibles
        mock_tramites_service.get_tramites_disponibles.assert_called_once()

        # Verificar que se envió un mensaje con la lista de trámites
        mock_whatsapp_service.enviar_mensaje_texto.assert_called_once()
        args, _ = mock_whatsapp_service.enviar_mensaje_texto.call_args
        mensaje_enviado = args[1]

        # Verificar que el mensaje contiene la información de los trámites
        assert "trámites disponibles" in mensaje_enviado.lower()
        assert "Consulta de deudas" in mensaje_enviado
        assert "Certificado de residencia" in mensaje_enviado
        assert "Reclamo por alumbrado" in mensaje_enviado
        assert "Reclamo por basura" in mensaje_enviado
        assert "¿Desea iniciar alguno" in mensaje_enviado

        # Verificar el resultado
        assert result["status"] == "success"
        assert result["state"] == "tramites"

    @pytest.mark.asyncio
    async def test_manejo_de_errores_api_municipal(
        self,
        sample_message,
        sample_contact,
        sample_user,
        mock_ciudadano_service,
        mock_whatsapp_service,
        mock_ai_service,
        mock_redis_repository,
        mock_ciudadano_repository,
    ):
        """
        Prueba el manejo de errores cuando la API municipal no responde:
        1. Usuario verificado envía un mensaje
        2. La API municipal devuelve un error
        3. El sistema maneja el error y envía un mensaje adecuado
        """
        # Crear servicio de chatbot con mocks
        chatbot_service = ChatbotService()
        chatbot_service.user_repo = mock_ciudadano_repository
        chatbot_service.redis_repo = mock_redis_repository
        chatbot_service.ciudadano_service = mock_ciudadano_service
        chatbot_service.whatsapp_service = mock_whatsapp_service
        chatbot_service.ai_service = mock_ai_service

        # Configurar escenario: error en la API municipal
        mock_ciudadano_service.get_info_ciudadano.return_value = {
            "success": False,
            "message": "Error de conexión con la API municipal",
        }

        # Mensaje del usuario
        message = WhatsAppMessage(
            from_="5491112345678",
            id="wamid.128",
            timestamp="1621234567895",
            type="text",
            text=TextMessage(body="Hola"),
        )

        # Procesar mensaje
        result = await chatbot_service.procesar_mensaje(message, sample_contact)

        # Verificar que se envió un mensaje de error
        mock_whatsapp_service.enviar_mensaje_texto.assert_called_once()
        args, _ = mock_whatsapp_service.enviar_mensaje_texto.call_args
        assert "no se pudo obtener su información" in args[1].lower()

        # Verificar el resultado
        assert result["status"] == "error"
        assert "No se pudo obtener información" in result["message"]
