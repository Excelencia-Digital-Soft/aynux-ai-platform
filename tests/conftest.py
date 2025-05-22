import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.config.settings import Settings, get_settings
from app.main import app, create_app
from app.models.ciudadano import ChatbotResponse, User, UserState
from app.models.message import Contact, TextMessage, WhatsAppMessage
from app.repositories.ciudadano_repository import CiudadanoRepository
from app.repositories.redis_repository import RedisRepository
from app.services.ai_service import AIService
from app.services.chatbot_service import ChatbotService
from app.services.ciudadano_service import CiudadanoService
from app.services.municipio_api_service import MunicipioAPIService
from app.services.tramites_service import TramitesService
from app.services.whatsapp_service import WhatsAppService


# Configuración para pruebas asíncronas
@pytest.fixture(scope="session")
def event_loop_policy():
    """Fixture para definir la política de event loop."""
    return asyncio.get_event_loop_policy()


# Configuración de la aplicación
@pytest.fixture
def test_settings():
    """Fixture para crear configuraciones de prueba"""
    return Settings(
        # Configuración para pruebas
        WHATSAPP_API_BASE="https://graph.facebook.com",
        WHATSAPP_API_VERSION="v18.0",
        PHONE_NUMBER_ID="123456789",
        ACCESS_TOKEN="test_token",
        APP_ID="test_app_id",
        APP_SECRET="test_app_secret",
        VERIFY_TOKEN="test_verify_token",
        MUNICIPIO_API_BASE="https://api.municipalidad.test",
        MUNICIPIO_API_KEY="test_municipio_api_key",
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        REDIS_DB=0,
        REDIS_PASSWORD=None,
        GEMINI_API_KEY="test_gemini_api_key",
        GEMINI_MODEL="gemini-test-model",
        JWT_SECRET_KEY="test_jwt_secret_key",
        DEBUG=True,
        ENVIRONMENT="testing",
    )


@pytest.fixture
def app_with_mocked_settings(test_settings):
    """Fixture para crear una aplicación con configuraciones de prueba"""
    with patch("app.config.settings.get_settings", return_value=test_settings):
        app = create_app()
        yield app


@pytest.fixture
def test_app(app_with_mocked_settings) -> FastAPI:
    """Fixture para obtener la aplicación FastAPI de prueba"""
    return app_with_mocked_settings


@pytest.fixture
def test_client(test_app) -> TestClient:
    """Fixture para crear un cliente de prueba"""
    return TestClient(test_app)


@pytest.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Fixture para crear un cliente asíncrono de prueba"""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


# Mocks para servicios y repositorios
@pytest.fixture
def mock_redis_repository():
    """Fixture para crear un mock del repositorio Redis"""
    with patch("app.repositories.redis_repository.RedisRepository") as mock:
        mock_instance = mock.return_value
        # Configurar métodos
        mock_instance.get = MagicMock()
        mock_instance.set = MagicMock()
        mock_instance.delete = MagicMock()
        mock_instance.exists = MagicMock()
        mock_instance.hash_set = MagicMock()
        mock_instance.hash_get = MagicMock()
        mock_instance.hash_get_all = MagicMock()
        mock_instance.hash_delete = MagicMock()
        mock_instance.save_conversation_history = MagicMock()
        mock_instance.get_conversation_history = MagicMock()
        yield mock_instance


@pytest.fixture
def mock_ciudadano_repository(mock_redis_repository):
    """Fixture para crear un mock del repositorio de ciudadanos"""
    with patch("app.repositories.ciudadano_repository.CiudadanoRepository") as mock:
        mock_instance = mock.return_value
        # Configurar métodos
        mock_instance.get_user = MagicMock()
        mock_instance.create_user = MagicMock()
        mock_instance.update_user_state = MagicMock()
        mock_instance.update_user = MagicMock()
        mock_instance.delete_user = MagicMock()
        mock_instance.set_user_session = MagicMock()
        mock_instance.get_user_session = MagicMock()
        mock_instance.update_user_session = MagicMock()
        mock_instance.delete_user_session = MagicMock()
        yield mock_instance


@pytest.fixture
def mock_municipio_api_service():
    """Fixture para crear un mock del servicio de API municipal"""
    with patch("app.services.municipio_api_service.MunicipioAPIService") as mock:
        mock_instance = mock.return_value
        # Configurar métodos asíncronos
        mock_instance.get = AsyncMock()
        mock_instance.post = AsyncMock()
        mock_instance.put = AsyncMock()
        mock_instance.delete = AsyncMock()
        mock_instance.request = AsyncMock()
        mock_instance.verify_connection = AsyncMock()
        mock_instance.get_contribuyentes = AsyncMock()
        yield mock_instance


@pytest.fixture
def mock_whatsapp_service():
    """Fixture para crear un mock del servicio de WhatsApp"""
    with patch("app.services.whatsapp_service.WhatsAppService") as mock:
        mock_instance = mock.return_value
        # Configurar métodos asíncronos
        mock_instance.enviar_mensaje_texto = AsyncMock()
        mock_instance.enviar_documento = AsyncMock()
        mock_instance.enviar_ubicacion = AsyncMock()
        mock_instance.enviar_lista_opciones = AsyncMock()
        mock_instance.enviar_botones = AsyncMock()
        yield mock_instance


@pytest.fixture
def mock_ai_service():
    """Fixture para crear un mock del servicio de IA"""
    with patch("app.services.ai_service.AIService") as mock:
        mock_instance = mock.return_value
        # Configurar métodos asíncronos
        mock_instance.generate_principal_mensaje = AsyncMock()
        mock_instance.verificar_ciudadano = AsyncMock()
        mock_instance._generate_content = AsyncMock()
        yield mock_instance


@pytest.fixture
def mock_tramites_service():
    """Fixture para crear un mock del servicio de trámites"""
    with patch("app.services.tramites_service.TramitesService") as mock:
        mock_instance = mock.return_value
        # Configurar métodos asíncronos
        mock_instance.get_tramites_disponibles = AsyncMock()
        mock_instance.iniciar_tramite = AsyncMock()
        mock_instance.consultar_estado_tramite = AsyncMock()
        mock_instance.obtener_deuda_contribuyente = AsyncMock()
        mock_instance.generar_comprobante_pago = AsyncMock()
        mock_instance.verificar_ciudadano = AsyncMock()
        yield mock_instance


@pytest.fixture
def mock_ciudadano_service(mock_municipio_api_service):
    """Fixture para crear un mock del servicio de ciudadano"""
    with patch("app.services.ciudadano_service.CiudadanoService") as mock:
        mock_instance = mock.return_value
        # Configurar métodos asíncronos
        mock_instance.get_info_ciudadano = AsyncMock()
        mock_instance.get_ciudadano_by_dni = AsyncMock()
        mock_instance.registrar_ciudadano = AsyncMock()
        mock_instance.actualizar_ciudadano = AsyncMock()
        # Asignar la api de municipios mock
        mock_instance.api_service = mock_municipio_api_service
        yield mock_instance


@pytest.fixture
def mock_certificate_generator():
    """Fixture para crear un mock del generador de certificados"""
    with patch("app.utils.certificate_utils.CertificateGenerator") as mock:
        mock_instance = mock.return_value
        # Configurar métodos asíncronos
        mock_instance.generate_qr_certificate = AsyncMock()
        yield mock_instance


@pytest.fixture
def mock_chatbot_service(
    mock_ciudadano_repository,
    mock_redis_repository,
    mock_ciudadano_service,
    mock_whatsapp_service,
    mock_ai_service,
    mock_tramites_service,
    mock_certificate_generator,
):
    """Fixture para crear un mock del servicio de chatbot"""
    with patch("app.services.chatbot_service.ChatbotService") as mock:
        mock_instance = mock.return_value
        # Configurar métodos asíncronos
        mock_instance.procesar_mensaje = AsyncMock()
        # Asignar dependencias mock
        mock_instance.user_repo = mock_ciudadano_repository
        mock_instance.redis_repo = mock_redis_repository
        mock_instance.ciudadano_service = mock_ciudadano_service
        mock_instance.whatsapp_service = mock_whatsapp_service
        mock_instance.ai_service = mock_ai_service
        mock_instance.tramites_service = mock_tramites_service
        mock_instance.certificate_generator = mock_certificate_generator
        yield mock_instance


# Datos de ejemplo para pruebas
@pytest.fixture
def sample_message() -> WhatsAppMessage:
    """Fixture para crear un mensaje de WhatsApp de ejemplo"""
    return WhatsAppMessage(
        from_="5491112345678",
        id="wamid.123",
        timestamp="1621234567890",
        type="text",
        text=TextMessage(body="Hola, quiero consultar mis deudas"),
    )


@pytest.fixture
def sample_contact() -> Contact:
    """Fixture para crear un contacto de WhatsApp de ejemplo"""
    return Contact(wa_id="5491112345678", profile={"name": "Juan Pérez"})


@pytest.fixture
def sample_user() -> User:
    """Fixture para crear un usuario de ejemplo"""
    return User(
        phone_number="5491112345678",
        state=UserState(
            state="verificado",
            verificado=True,
            id_ciudadano="123",
        ),
    )


@pytest.fixture
def sample_user_not_verified() -> User:
    """Fixture para crear un usuario no verificado de ejemplo"""
    return User(
        phone_number="5491112345678",
        state=UserState(
            state="verificar",
            verificado=False,
            id_ciudadano="123",
        ),
    )


@pytest.fixture
def sample_ciudadano_data() -> Dict[str, Any]:
    """Fixture para crear datos de ciudadano de ejemplo"""
    return {
        "id_ciudadano": "123",
        "nombre": "Juan",
        "apellido": "Pérez",
        "documento": "12345678",
        "telefono": "5491112345678",
        "email": "juan.perez@ejemplo.com",
        "direccion": "Calle Principal 123",
    }


@pytest.fixture
def sample_tramites_data() -> List[Dict[str, Any]]:
    """Fixture para crear datos de trámites de ejemplo"""
    return [
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
        {
            "id": "3",
            "nombre": "Reclamo por alumbrado",
            "descripcion": "Reporta problemas con el alumbrado público",
        },
        {
            "id": "4",
            "nombre": "Reclamo por basura",
            "descripcion": "Reporta problemas con la recolección de basura",
        },
    ]


@pytest.fixture
def sample_deuda_data() -> List[Dict[str, Any]]:
    """Fixture para crear datos de deuda de ejemplo"""
    return [
        {
            "id_deuda": "D001",
            "concepto": "Tasa municipal",
            "monto": 1500.0,
            "vencimiento": "2023-12-10",
        },
        {
            "id_deuda": "D002",
            "concepto": "Alumbrado público",
            "monto": 800.0,
            "vencimiento": "2023-12-15",
        },
        {
            "id_deuda": "D003",
            "concepto": "Impuesto inmobiliario",
            "monto": 2500.0,
            "vencimiento": "2023-12-20",
        },
    ]


@pytest.fixture
def sample_conversation_history() -> List[Dict[str, str]]:
    """Fixture para crear un historial de conversación de ejemplo"""
    return [
        {"role": "persona", "content": "Hola"},
        {"role": "bot", "content": "Hola, ¿en qué puedo ayudarte?"},
        {"role": "persona", "content": "Quiero consultar mis deudas"},
        {"role": "bot", "content": "Claro, voy a buscar esa información para ti."},
    ]


@pytest.fixture(autouse=True, scope="function")
async def cleanup_coroutines():
    """
    Fixture global para limpiar corrutinas pendientes después de cada test asíncrono.
    """
    yield
    # Dar tiempo al bucle de eventos para procesar tareas pendientes
    await asyncio.sleep(0)


# Funciones auxiliares para las pruebas
def create_chatbot_service_with_mocks(
    mock_ciudadano_repository: Optional[MagicMock] = None,
    mock_redis_repository: Optional[MagicMock] = None,
    mock_ciudadano_service: Optional[MagicMock] = None,
    mock_whatsapp_service: Optional[MagicMock] = None,
    mock_ai_service: Optional[MagicMock] = None,
    mock_tramites_service: Optional[MagicMock] = None,
    mock_certificate_generator: Optional[MagicMock] = None,
) -> ChatbotService:
    """
    Función auxiliar para crear un servicio de chatbot con mocks específicos
    """
    service = ChatbotService()

    if mock_ciudadano_repository:
        service.user_repo = mock_ciudadano_repository

    if mock_redis_repository:
        service.redis_repo = mock_redis_repository

    if mock_ciudadano_service:
        service.ciudadano_service = mock_ciudadano_service

    if mock_whatsapp_service:
        service.whatsapp_service = mock_whatsapp_service

    if mock_ai_service:
        service.ai_service = mock_ai_service

    if mock_tramites_service:
        service.tramites_service = mock_tramites_service

    if mock_certificate_generator:
        service.certificate_generator = mock_certificate_generator

    return service
