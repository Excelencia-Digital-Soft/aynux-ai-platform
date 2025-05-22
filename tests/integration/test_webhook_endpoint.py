from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def test_client():
    """Fixture para crear un cliente de prueba"""
    with (
        patch("app.api.routes.webhook.chatbot_service") as mock_chatbot,
        patch("app.api.dependencies.verify_signature", return_value=True),
    ):
        # Configurar el mock del servicio de chatbot
        mock_chatbot.procesar_mensaje = AsyncMock()

        # Crear cliente de prueba
        client = TestClient(app)
        yield client, mock_chatbot


def test_verify_webhook(test_client):
    """Prueba para verificar el webhook"""
    client, _ = test_client

    # Parámetros de prueba
    verify_token = "test_token"
    challenge = "challenge_code"

    # Configurar el token de verificación en las configuraciones
    with patch("app.api.routes.webhook.get_settings") as mock_settings:
        mock_settings.return_value.VERIFY_TOKEN = verify_token

        # Realizar solicitud GET con parámetros de verificación correctos
        response = client.get(
            "/api/v1/webhook/",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": verify_token,
                "hub.challenge": challenge,
            },
        )

        # Verificar que la respuesta contiene el código de desafío
        assert response.status_code == 200
        assert response.text == challenge

        # Probar con un token incorrecto
        response_invalid = client.get(
            "/api/v1/webhook/",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": challenge,
            },
        )

        # Verificar que la respuesta es un error
        assert response_invalid.status_code == 403


def test_process_webhook_text_message(test_client):
    """Prueba para procesar un mensaje de texto entrante"""
    client, mock_chatbot = test_client

    # Configurar la respuesta del servicio de chatbot
    mock_chatbot.procesar_mensaje.return_value = {"status": "ok", "state": "verificado"}

    # Crear un payload de webhook con un mensaje de texto
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5491112345678",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Juan Pérez"},
                                    "wa_id": "5491112345678",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid.123",
                                    "timestamp": "1621234567890",
                                    "type": "text",
                                    "text": {
                                        "body": "Hola, quiero consultar mis deudas"
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    # Realizar solicitud POST al webhook
    response = client.post("/api/v1/webhook/", json=webhook_payload)

    # Verificar la respuesta
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "result": {"status": "ok", "state": "verificado"},
    }

    # Verificar que se llamó al servicio de chatbot con los parámetros correctos
    mock_chatbot.procesar_mensaje.assert_called_once()
    args, _ = mock_chatbot.procesar_mensaje.call_args

    # Verificar el mensaje
    assert args[0].from_ == "5491112345678"
    assert args[0].type == "text"
    assert args[0].text.body == "Hola, quiero consultar mis deudas"

    # Verificar el contacto
    assert args[1].wa_id == "5491112345678"
    assert args[1].profile["name"] == "Juan Pérez"


def test_process_webhook_interactive_message(test_client):
    """Prueba para procesar un mensaje interactivo entrante"""
    client, mock_chatbot = test_client

    # Configurar la respuesta del servicio de chatbot
    mock_chatbot.procesar_mensaje.return_value = {
        "status": "ok",
        "state": "consulta_deuda",
    }

    # Crear un payload de webhook con un mensaje interactivo (botón)
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5491112345678",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Juan Pérez"},
                                    "wa_id": "5491112345678",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid.123",
                                    "timestamp": "1621234567890",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": "si",
                                            "title": "Sí, soy yo",
                                        },
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    # Realizar solicitud POST al webhook
    response = client.post("/api/v1/webhook/", json=webhook_payload)

    # Verificar la respuesta
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "result": {"status": "ok", "state": "consulta_deuda"},
    }

    # Verificar que se llamó al servicio de chatbot con los parámetros correctos
    mock_chatbot.procesar_mensaje.assert_called_once()
    args, _ = mock_chatbot.procesar_mensaje.call_args

    # Verificar el mensaje
    assert args[0].from_ == "5491112345678"
    assert args[0].type == "interactive"
    assert args[0].interactive.type == "button_reply"
    assert args[0].interactive.button_reply.id == "si"
    assert args[0].interactive.button_reply.title == "Sí, soy yo"


def test_process_webhook_status_update(test_client):
    """Prueba para procesar una actualización de estado"""
    client, mock_chatbot = test_client

    # Crear un payload de webhook con una actualización de estado
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5491112345678",
                                "phone_number_id": "987654321",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.123",
                                    "status": "delivered",
                                    "timestamp": "1621234567890",
                                    "recipient_id": "5491112345678",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    # Realizar solicitud POST al webhook
    response = client.post("/api/v1/webhook/", json=webhook_payload)

    # Verificar la respuesta
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verificar que NO se llamó al servicio de chatbot
    mock_chatbot.procesar_mensaje.assert_not_called()


def test_process_webhook_invalid_payload(test_client):
    """Prueba para procesar un payload inválido"""
    client, mock_chatbot = test_client

    # Crear un payload de webhook inválido (sin messages ni contacts)
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5491112345678",
                                "phone_number_id": "987654321",
                            },
                            # Sin messages ni contacts
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    # Realizar solicitud POST al webhook
    response = client.post("/api/v1/webhook/", json=webhook_payload)

    # Verificar la respuesta
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "error"
    assert "Invalid webhook payload" in result["message"]

    # Verificar que NO se llamó al servicio de chatbot
    mock_chatbot.procesar_mensaje.assert_not_called()
