import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.models.ciudadano import ChatbotResponse
from app.services.ai_service import AIService


@pytest.fixture
def mock_generative_model():
    """Fixture para crear un mock del modelo generativo"""
    with patch("google.generativeai.GenerativeModel") as mock_model_class:
        # Crear un mock para la instancia del modelo
        mock_model = mock_model_class.return_value
        mock_model.generate_content = MagicMock()

        # Configurar el mock para generate_content
        mock_response = MagicMock()
        mock_response.text = (
            '{"mensaje": "Respuesta de prueba", "estado": "verificado"}'
        )
        mock_model.generate_content.return_value = mock_response

        yield mock_model


@pytest.fixture
def mock_settings():
    """Fixture para crear configuraciones mock"""
    with patch("app.services.ai_service.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.GEMINI_API_KEY = "test_api_key"
        mock_settings.GEMINI_MODEL = "gemini-1.5-flash"
        mock_get_settings.return_value = mock_settings
        yield mock_settings


@pytest.fixture
def mock_genai():
    """Fixture para crear un mock del módulo genai"""
    with patch("app.services.ai_service.genai") as mock_genai:
        mock_genai.configure = MagicMock()
        yield mock_genai


@pytest.fixture
def ai_service(mock_generative_model, mock_settings, mock_genai):
    """Fixture para crear el servicio de IA con mocks"""
    service = AIService()
    service.model = mock_generative_model
    return service


class TestAIService:
    """Pruebas para el servicio de IA"""

    @pytest.mark.asyncio
    async def test_generate_principal_mensaje(self, ai_service, mock_generative_model):
        """Prueba para generar un mensaje principal"""
        # Datos de prueba
        nombre_completo = "Juan Pérez"
        estado = "activo"
        estado_conversacion = "verificado"
        tramites = [
            {"id": "1", "nombre": "Consulta de deudas"},
            {"id": "2", "nombre": "Certificado de residencia"},
        ]
        verificado = True
        documento = "12345678"
        message = "Quiero consultar mi deuda municipal"
        historial = "persona: Hola\nbot: Hola, ¿en qué puedo ayudarte?"

        # Configurar la respuesta del modelo
        mock_response = MagicMock()
        mock_response.text = '{"mensaje": "Entiendo que quieres consultar tu deuda municipal. Voy a buscar esa información para ti.", "estado": "consulta_deuda"}'
        mock_generative_model.generate_content.return_value = mock_response

        # Llamar al método y verificar el resultado
        result = await ai_service.generate_principal_mensaje(
            nombre_completo,
            estado,
            estado_conversacion,
            tramites,
            verificado,
            documento,
            message,
            historial,
        )

        # Verificar que el modelo fue llamado con el prompt correcto
        mock_generative_model.generate_content.assert_called_once()
        args, _ = mock_generative_model.generate_content.call_args
        prompt = args[0]

        # Verificar que el prompt contiene la información necesaria
        assert nombre_completo in prompt
        assert estado in prompt
        assert estado_conversacion in prompt
        assert documento in prompt
        assert message in prompt
        assert historial in prompt

        # Verificar que al menos un trámite está en el prompt
        for tramite in tramites:
            for value in tramite.values():
                if isinstance(value, str) and value in prompt:
                    tramite_in_prompt = True
                    break
        assert tramite_in_prompt

        # Verificar el resultado
        assert isinstance(result, ChatbotResponse)
        assert (
            result.mensaje
            == "Entiendo que quieres consultar tu deuda municipal. Voy a buscar esa información para ti."
        )
        assert result.estado == "consulta_deuda"

    @pytest.mark.asyncio
    async def test_verificar_ciudadano_afirmacion(
        self, ai_service, mock_generative_model
    ):
        """Prueba para verificar una respuesta afirmativa del ciudadano"""
        # Configurar la respuesta del modelo
        mock_response = MagicMock()
        mock_response.text = "afirmacion"
        mock_generative_model.generate_content.return_value = mock_response

        # Mensaje de prueba
        mensaje = "Sí, soy yo"

        # Llamar al método y verificar el resultado
        result = await ai_service.verificar_ciudadano(mensaje)

        # Verificar que el modelo fue llamado con el prompt correcto
        mock_generative_model.generate_content.assert_called_once()
        args, _ = mock_generative_model.generate_content.call_args
        prompt = args[0]

        # Verificar que el prompt contiene la información necesaria
        assert "verificar" in prompt.lower()
        assert "respuesta" in prompt.lower()
        assert mensaje in prompt

        # Verificar el resultado
        assert result == "afirmacion"

    @pytest.mark.asyncio
    async def test_verificar_ciudadano_negacion(
        self, ai_service, mock_generative_model
    ):
        """Prueba para verificar una respuesta negativa del ciudadano"""
        # Configurar la respuesta del modelo
        mock_response = MagicMock()
        mock_response.text = "negacion"
        mock_generative_model.generate_content.return_value = mock_response

        # Mensaje de prueba
        mensaje = "No, no soy esa persona"

        # Llamar al método y verificar el resultado
        result = await ai_service.verificar_ciudadano(mensaje)

        # Verificar que el modelo fue llamado con el prompt correcto
        mock_generative_model.generate_content.assert_called_once()

        # Verificar el resultado
        assert result == "negacion"

    @pytest.mark.asyncio
    async def test_verificar_ciudadano_invalido(
        self, ai_service, mock_generative_model
    ):
        """Prueba para verificar una respuesta inválida del ciudadano"""
        # Configurar la respuesta del modelo
        mock_response = MagicMock()
        mock_response.text = "invalido"
        mock_generative_model.generate_content.return_value = mock_response

        # Mensaje de prueba
        mensaje = "Hola, ¿cómo estás?"

        # Llamar al método y verificar el resultado
        result = await ai_service.verificar_ciudadano(mensaje)

        # Verificar que el modelo fue llamado con el prompt correcto
        mock_generative_model.generate_content.assert_called_once()

        # Verificar el resultado
        assert result == "invalido"

    @pytest.mark.asyncio
    async def test_procesar_respuesta_json_valido(self, ai_service):
        """Prueba para procesar una respuesta JSON válida"""
        # JSON válido
        mensaje_json = '{"mensaje": "Respuesta de prueba", "estado": "verificado"}'

        # Llamar al método y verificar el resultado
        result = ai_service._procesar_respuesta(mensaje_json)

        # Verificar el resultado
        assert isinstance(result, ChatbotResponse)
        assert result.mensaje == "Respuesta de prueba"
        assert result.estado == "verificado"

    @pytest.mark.asyncio
    async def test_procesar_respuesta_json_en_bloque_codigo(self, ai_service):
        """Prueba para procesar una respuesta JSON en un bloque de código"""
        # JSON en bloque de código
        mensaje_json = """
        Aquí está la respuesta:
        ```json
        {"mensaje": "Respuesta en bloque de código", "estado": "tramites"}
        ```
        """

        # Llamar al método y verificar el resultado
        result = ai_service._procesar_respuesta(mensaje_json)

        # Verificar el resultado
        assert isinstance(result, ChatbotResponse)
        assert result.mensaje == "Respuesta en bloque de código"
        assert result.estado == "tramites"

    @pytest.mark.asyncio
    async def test_procesar_respuesta_json_invalido(self, ai_service):
        """Prueba para procesar una respuesta JSON inválida"""
        # JSON inválido
        mensaje_json = '{"mensaje": "Respuesta incompleta", "estado":'

        # Llamar al método y verificar el resultado
        result = ai_service._procesar_respuesta(mensaje_json)

        # Verificar que se creó una respuesta por defecto
        assert isinstance(result, ChatbotResponse)
        assert result.mensaje == mensaje_json
        assert result.estado == "verificado"

    @pytest.mark.asyncio
    async def test_procesar_respuesta_texto_sin_json(self, ai_service):
        """Prueba para procesar una respuesta de texto sin formato JSON"""
        # Texto sin formato JSON
        mensaje = "Esta es una respuesta que no está en formato JSON"

        # Llamar al método y verificar el resultado
        result = ai_service._procesar_respuesta(mensaje)

        # Verificar que se devolvió el texto como mensaje y estado por defecto
        assert isinstance(result, ChatbotResponse)
        assert result.mensaje == mensaje
        assert result.estado == "verificado"

    @pytest.mark.asyncio
    async def test_procesar_respuesta_vacia(self, ai_service):
        """Prueba para procesar una respuesta vacía"""
        # Respuesta vacía
        mensaje = ""

        # Llamar al método y verificar el resultado
        with pytest.raises(ValueError, match="La respuesta del chatbot está vacía"):
            ai_service._procesar_respuesta(mensaje)

    @pytest.mark.asyncio
    async def test_generate_content(self, ai_service, mock_generative_model):
        """Prueba para el método _generate_content"""
        # Configurar la respuesta del modelo
        mock_response = MagicMock()
        mock_response.text = "Respuesta generada"
        mock_generative_model.generate_content.return_value = mock_response

        # Prompt de prueba
        prompt = "Este es un prompt de prueba"

        # Llamar al método y verificar el resultado
        result = await ai_service._generate_content(prompt)

        # Verificar que el modelo fue llamado con el prompt correcto
        mock_generative_model.generate_content.assert_called_once_with(prompt)

        # Verificar el resultado
        assert result == "Respuesta generada"

    @pytest.mark.asyncio
    async def test_configuracion_inicial(self, mock_settings, mock_genai):
        """Prueba para verificar la configuración inicial del servicio"""
        # Crear una nueva instancia del servicio
        ai_service = AIService()

        # Verificar que genai.configure fue llamado con la API key correcta
        mock_genai.configure.assert_called_once_with(
            api_key=mock_settings.GEMINI_API_KEY
        )

        # Verificar que el modelo correcto fue seleccionado
        mock_genai.GenerativeModel.assert_called_once_with(mock_settings.GEMINI_MODEL)
