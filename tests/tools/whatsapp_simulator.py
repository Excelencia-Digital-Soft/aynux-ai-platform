#!/usr/bin/env python
"""
Simulador avanzado de mensajes de WhatsApp para pruebas del webhook
-----------------------------------------------------
Este script permite enviar mensajes simulados al endpoint del webhook para probar
la funcionalidad del chatbot sin necesidad de usar la API real de WhatsApp.

Soporta múltiples tipos de interacciones:
- Mensajes de texto
- Respuestas de botones
- Listas de opciones
- Respuestas a listas
- Mensajes con plantillas
- Mensajes de ubicación
- Mensajes multimedia (imagen, documento, audio, video)
- Flujos de conversación

Uso:
    python whatsapp_simulator.py [--url URL] [--phone PHONE] [--name NAME] [--mode MODE]

Argumentos:
    --url URL      URL del webhook (por defecto: http://localhost:8001/api/v1/webhook/)
    --phone PHONE  Número de teléfono del remitente (por defecto: 5491112345678)
    --name NAME    Nombre del remitente (por defecto: Usuario de Prueba)
    --mode MODE    Modo de operación: interactive (por defecto), script, flows o verify

Ejemplos:
    python whatsapp_simulator.py
    python whatsapp_simulator.py --mode verify
    python whatsapp_simulator.py --mode flows
    python whatsapp_simulator.py --phone 5491199887766 --name "Juan Pérez"
"""

import argparse
import json
import random
import time
import uuid

import requests


def generate_message_id():
    """Genera un ID único para los mensajes"""
    return f"wamid.{uuid.uuid4().hex[:8]}"


def simulate_verification(url, token="test_verify_token"):
    """Simula la verificación del webhook por parte de WhatsApp"""
    challenge = "challenge_" + str(random.randint(10000, 99999))

    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": token,
        "hub.challenge": challenge,
    }

    print("\n🔍 Simulando verificación del webhook...")
    print(f"URL: {url}")
    print(f"Token: {token}")
    print(f"Challenge: {challenge}")

    try:
        response = requests.get(url, params=params)

        if response.status_code == 200 and response.text == challenge:
            print(
                "\n✅ Verificación exitosa! "
                "El webhook respondió correctamente al desafío."
            )
        else:
            print(
                f"\n❌ Error de verificación. Código de estado: {response.status_code}"
            )
            print(f"Respuesta: {response.text}")

    except requests.RequestException as e:
        print(f"\n❌ Error de conexión: {e}")


def send_text_message(url, phone_number, name, text):
    """Envía un mensaje de texto simulado al webhook"""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {"profile": {"name": name}, "wa_id": phone_number}
                            ],
                            "messages": [
                                {
                                    "from": phone_number,
                                    "id": generate_message_id(),
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=dummy_signature",  # Firma simulada
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        print(f"\n📤 Mensaje enviado: '{text}'")
        print(f"Estado: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Respuesta: {json.dumps(result, indent=2)}")
                return True
            except json.JSONDecodeError:
                print(f"Respuesta (no JSON): {response.text}")
                return True
        else:
            print(f"Error: {response.text}")
            return False

    except requests.RequestException as e:
        print(f"\n❌ Error de conexión: {e}")
        return False


def send_button_reply(url, phone_number, name, button_id, button_title):
    """Envía una respuesta de botón simulada al webhook"""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {"profile": {"name": name}, "wa_id": phone_number}
                            ],
                            "messages": [
                                {
                                    "from": phone_number,
                                    "id": generate_message_id(),
                                    "timestamp": str(int(time.time())),
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": button_id,
                                            "title": button_title,
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

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=dummy_signature",  # Firma simulada
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        print(f"\n📤 Botón seleccionado: '{button_title}' (ID: {button_id})")
        print(f"Estado: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Respuesta: {json.dumps(result, indent=2)}")
                return True
            except json.JSONDecodeError:
                print(f"Respuesta (no JSON): {response.text}")
                return True
        else:
            print(f"Error: {response.text}")
            return False

    except requests.RequestException as e:
        print(f"\n❌ Error de conexión: {e}")
        return False


def send_list_reply(url, phone_number, name, list_id, list_title, list_description=""):
    """Envía una respuesta de selección de lista simulada al webhook"""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {"profile": {"name": name}, "wa_id": phone_number}
                            ],
                            "messages": [
                                {
                                    "from": phone_number,
                                    "id": generate_message_id(),
                                    "timestamp": str(int(time.time())),
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list_reply",
                                        "list_reply": {
                                            "id": list_id,
                                            "title": list_title,
                                            "description": list_description,
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

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=dummy_signature",  # Firma simulada
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        print(f"\n📤 Opción de lista seleccionada: '{list_title}' (ID: {list_id})")
        if list_description:
            print(f"Descripción: {list_description}")
        print(f"Estado: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Respuesta: {json.dumps(result, indent=2)}")
                return True
            except json.JSONDecodeError:
                print(f"Respuesta (no JSON): {response.text}")
                return True
        else:
            print(f"Error: {response.text}")
            return False

    except requests.RequestException as e:
        print(f"\n❌ Error de conexión: {e}")
        return False


def send_location(
    url, phone_number, name, latitude, longitude, name_location="", address=""
):
    """Envía una ubicación simulada al webhook"""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {"profile": {"name": name}, "wa_id": phone_number}
                            ],
                            "messages": [
                                {
                                    "from": phone_number,
                                    "id": generate_message_id(),
                                    "timestamp": str(int(time.time())),
                                    "type": "location",
                                    "location": {
                                        "latitude": latitude,
                                        "longitude": longitude,
                                        "name": name_location,
                                        "address": address,
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

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=dummy_signature",  # Firma simulada
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        print(f"\n📤 Ubicación enviada: {latitude}, {longitude}")
        if name_location:
            print(f"Lugar: {name_location}")
        if address:
            print(f"Dirección: {address}")
        print(f"Estado: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Respuesta: {json.dumps(result, indent=2)}")
                return True
            except json.JSONDecodeError:
                print(f"Respuesta (no JSON): {response.text}")
                return True
        else:
            print(f"Error: {response.text}")
            return False

    except requests.RequestException as e:
        print(f"\n❌ Error de conexión: {e}")
        return False


def send_media_message(
    url, phone_number, name, media_type, media_id=None, media_url=None, caption=None
):
    """
    Envía un mensaje multimedia simulado al webhook

    Args:
        url: URL del webhook
        phone_number: Número de teléfono del remitente
        name: Nombre del remitente
        media_type: Tipo de medio ('image', 'audio', 'document', 'video', 'sticker')
        media_id: ID del medio (opcional)
        media_url: URL del medio (opcional)
        caption: Texto opcional para acompañar el medio (no aplicable para audio)
    """

    # Si no se proporciona ni ID ni URL, usamos valores simulados
    if not media_id and not media_url:
        media_id = f"media_id_{uuid.uuid4().hex[:10]}"
        media_url = f"https://example.com/media/{media_type}/{media_id}.{get_extension_for_type(media_type)}"

    media_obj = {}

    if media_id:
        media_obj["id"] = media_id

    if media_url:
        media_obj["url"] = media_url

    if caption and media_type != "audio":  # Audio no admite caption
        media_obj["caption"] = caption

    # Ajustes específicos por tipo de medio
    if media_type == "document":
        if "filename" not in media_obj:
            media_obj["filename"] = f"document_{int(time.time())}.pdf"

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {"profile": {"name": name}, "wa_id": phone_number}
                            ],
                            "messages": [
                                {
                                    "from": phone_number,
                                    "id": generate_message_id(),
                                    "timestamp": str(int(time.time())),
                                    "type": media_type,
                                    media_type: media_obj,
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=dummy_signature",  # Firma simulada
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        print(f"\n📤 Mensaje tipo {media_type.upper()} enviado")
        if media_url:
            print(f"URL: {media_url}")
        if caption:
            print(f"Texto: {caption}")
        print(f"Estado: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Respuesta: {json.dumps(result, indent=2)}")
                return True
            except json.JSONDecodeError:
                print(f"Respuesta (no JSON): {response.text}")
                return True
        else:
            print(f"Error: {response.text}")
            return False

    except requests.RequestException as e:
        print(f"\n❌ Error de conexión: {e}")
        return False


def send_template_message_reply(
    url, phone_number, name, template_name, template_id, parameters=None
):
    """
    Envía una respuesta a un mensaje de plantilla simulada al webhook

    Args:
        url: URL del webhook
        phone_number: Número de teléfono del remitente
        name: Nombre del remitente
        template_name: Nombre de la plantilla seleccionada
        template_id: ID de la plantilla seleccionada
        parameters: Parámetros adicionales de la plantilla (opcional)
    """

    if not parameters:
        parameters = {}

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {"profile": {"name": name}, "wa_id": phone_number}
                            ],
                            "messages": [
                                {
                                    "from": phone_number,
                                    "id": generate_message_id(),
                                    "timestamp": str(int(time.time())),
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": template_id,
                                            "title": template_name,
                                        },
                                    },
                                    "context": {
                                        # Número de teléfono del chatbot
                                        "from": "1234567890",
                                        # ID del mensaje de plantilla original
                                        "id": f"wamid.template_{uuid.uuid4().hex[:8]}",
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

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=dummy_signature",  # Firma simulada
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        print(f"\n📤 Respuesta a plantilla: '{template_name}' (ID: {template_id})")
        print(f"Estado: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Respuesta: {json.dumps(result, indent=2)}")
                return True
            except json.JSONDecodeError:
                print(f"Respuesta (no JSON): {response.text}")
                return True
        else:
            print(f"Error: {response.text}")
            return False

    except requests.RequestException as e:
        print(f"\n❌ Error de conexión: {e}")
        return False


def get_extension_for_type(media_type):
    """Devuelve una extensión de archivo apropiada para el tipo de medio"""
    extensions = {
        "image": "jpg",
        "audio": "mp3",
        "document": "pdf",
        "video": "mp4",
        "sticker": "webp",
    }
    return extensions.get(media_type, "bin")


def send_referral_message(
    url, phone_number, name, source_url, source_type="ad", source_id=None
):
    """
    Envía un mensaje de referencia simulado al webhook (simulando un clic en un anuncio)

    Args:
        url: URL del webhook
        phone_number: Número de teléfono del remitente
        name: Nombre del remitente
        source_url: URL de origen de la referencia
        source_type: Tipo de origen ('ad', 'post', etc.)
        source_id: ID del origen (opcional)
    """

    if not source_id:
        source_id = f"source_{uuid.uuid4().hex[:10]}"

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {"profile": {"name": name}, "wa_id": phone_number}
                            ],
                            "messages": [
                                {
                                    "from": phone_number,
                                    "id": generate_message_id(),
                                    "timestamp": str(int(time.time())),
                                    "referral": {
                                        "source_url": source_url,
                                        "source_type": source_type,
                                        "source_id": source_id,
                                        "headline": "Anuncio de ejemplo",
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

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=dummy_signature",  # Firma simulada
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        print("\n📤 Mensaje de referencia enviado")
        print(f"Origen: {source_type} - {source_url}")
        print(f"Estado: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Respuesta: {json.dumps(result, indent=2)}")
                return True
            except json.JSONDecodeError:
                print(f"Respuesta (no JSON): {response.text}")
                return True
        else:
            print(f"Error: {response.text}")
            return False

    except requests.RequestException as e:
        print(f"\n❌ Error de conexión: {e}")
        return False


def send_voice_message(url, phone_number, name, voice_id=None, voice_url=None):
    """Envía un mensaje de voz (nota de voz) simulado al webhook"""
    return send_media_message(url, phone_number, name, "audio", voice_id, voice_url)


def interactive_mode(url, phone_number, name):
    """Ejecuta el simulador en modo interactivo con soporte para comandos avanzados"""
    print("\n🤖 Simulador de WhatsApp - Modo Interactivo Avanzado")
    print(f"URL del webhook: {url}")
    print(f"Número de teléfono: {phone_number}")
    print(f"Nombre: {name}")
    print("\nEscriba los mensajes y presione Enter para enviarlos.")
    print("Comandos especiales:")
    print("  /quit       - Salir del simulador")
    print("  /verify     - Simular verificación del webhook")
    print("  /button:id:texto - Enviar una respuesta de botón")
    print("  /list:id:título:descripción - Enviar una respuesta de lista")
    print("  /location:lat:lon:nombre:dirección - Enviar ubicación")
    print("  /image:url:caption - Enviar imagen")
    print("  /audio      - Enviar nota de voz")
    print("  /document:url:nombre - Enviar documento")
    print("  /video:url:caption - Enviar video")
    print("  /template:nombre:id - Responder a una plantilla")
    print("  /referral:url:tipo - Simular entrada por referencia/anuncio")
    print("  /flow:nombre - Ejecutar un flujo predefinido")
    print("  /help       - Mostrar esta ayuda")

    while True:
        try:
            text = input("\n📱 > ")

            if text.lower() == "/quit":
                print("👋 Saliendo del simulador...")
                break

            elif text.lower() == "/verify":
                simulate_verification(url)

            elif text.lower() == "/help":
                print("\nComandos disponibles:")
                print("  /quit       - Salir del simulador")
                print("  /verify     - Simular verificación del webhook")
                print("  /button:id:texto - Enviar una respuesta de botón")
                print("  /list:id:título:descripción - Enviar una respuesta de lista")
                print("  /location:lat:lon:nombre:dirección - Enviar ubicación")
                print("  /image:url:caption - Enviar imagen")
                print("  /audio      - Enviar nota de voz")
                print("  /document:url:nombre - Enviar documento")
                print("  /video:url:caption - Enviar video")
                print("  /template:nombre:id - Responder a una plantilla")
                print("  /referral:url:tipo - Simular entrada por referencia/anuncio")
                print("  /flow:nombre - Ejecutar un flujo predefinido")
                print("  /help       - Mostrar esta ayuda")

            elif text.lower() == "/audio":
                send_voice_message(url, phone_number, name)

            elif text.lower().startswith("/button:"):
                # Formato: /button:id:texto
                parts = text.split(":", 2)
                if len(parts) == 3:
                    button_id = parts[1]
                    button_title = parts[2]
                    send_button_reply(url, phone_number, name, button_id, button_title)
                else:
                    print("❌ Formato incorrecto. Use: /button:id:texto")

            elif text.lower().startswith("/list:"):
                # Formato: /list:id:título:descripción (descripción opcional)
                parts = text.split(":", 3)
                if len(parts) >= 3:
                    list_id = parts[1]
                    list_title = parts[2]
                    list_description = parts[3] if len(parts) > 3 else ""
                    send_list_reply(
                        url, phone_number, name, list_id, list_title, list_description
                    )
                else:
                    print("❌ Formato incorrecto. Use: /list:id:título:descripción")

            elif text.lower().startswith("/location:"):
                # Formato: /location:lat:lon:nombre:dirección
                parts = text.split(":", 4)
                if len(parts) >= 3:
                    try:
                        lat = float(parts[1])
                        lon = float(parts[2])
                        place_name = parts[3] if len(parts) > 3 else ""
                        address = parts[4] if len(parts) > 4 else ""
                        send_location(
                            url, phone_number, name, lat, lon, place_name, address
                        )
                    except ValueError:
                        print("❌ Las coordenadas deben ser números válidos.")
                else:
                    print(
                        "❌ Formato incorrecto. Use: /location:lat:lon:nombre:dirección"
                    )

            elif text.lower().startswith("/image:"):
                # Formato: /image:url:caption
                parts = text.split(":", 2)
                if len(parts) >= 2:
                    image_url = parts[1]
                    caption = parts[2] if len(parts) > 2 else None
                    send_media_message(
                        url, phone_number, name, "image", None, image_url, caption
                    )
                else:
                    print("❌ Formato incorrecto. Use: /image:url:caption")

            elif text.lower().startswith("/document:"):
                # Formato: /document:url:nombre
                parts = text.split(":", 3)
                if len(parts) >= 2:
                    doc_url = parts[1]
                    filename = (
                        parts[2]
                        if len(parts) > 2
                        else f"documento_{int(time.time())}.pdf"
                    )
                    send_media_message(
                        url, phone_number, name, "document", None, doc_url, filename
                    )
                else:
                    print("❌ Formato incorrecto. Use: /document:url:nombre")

            elif text.lower().startswith("/video:"):
                # Formato: /video:url:caption
                parts = text.split(":", 2)
                if len(parts) >= 2:
                    video_url = parts[1]
                    caption = parts[2] if len(parts) > 2 else None
                    send_media_message(
                        url, phone_number, name, "video", None, video_url, caption
                    )
                else:
                    print("❌ Formato incorrecto. Use: /video:url:caption")

            elif text.lower().startswith("/template:"):
                # Formato: /template:nombre:id
                parts = text.split(":", 2)
                if len(parts) >= 3:
                    template_name = parts[1]
                    template_id = parts[2]
                    send_template_message_reply(
                        url, phone_number, name, template_name, template_id
                    )
                else:
                    print("❌ Formato incorrecto. Use: /template:nombre:id")

            elif text.lower().startswith("/referral:"):
                # Formato: /referral:url:tipo
                parts = text.split(":", 2)
                if len(parts) >= 2:
                    ref_url = parts[1]
                    ref_type = parts[2] if len(parts) > 2 else "ad"
                    send_referral_message(url, phone_number, name, ref_url, ref_type)
                else:
                    print("❌ Formato incorrecto. Use: /referral:url:tipo")

            elif text.lower().startswith("/flow:"):
                # Ejecutar un flujo predefinido de conversación
                flow_name = text.split(":", 1)[1] if ":" in text else ""
                if flow_name:
                    execute_flow(url, phone_number, name, flow_name)
                else:
                    print("❌ Formato incorrecto. Use: /flow:nombre")
                    print(
                        "Flujos disponibles: consulta_deuda,"
                        "tramite_documento, ayuda_general"
                    )

            else:
                send_text_message(url, phone_number, name, text)

        except KeyboardInterrupt:
            print("\n👋 Simulador interrumpido. Saliendo...")
            break

        except Exception as e:
            print(f"\n❌ Error: {e}")


def execute_flow(url, phone_number, name, flow_name):
    """Ejecuta un flujo predefinido de conversación"""
    flows = {
        "consulta_deuda": [
            ("text", "Hola, quiero consultar mi deuda municipal"),
            ("wait", 2),
            ("button", "consulta_deuda", "Consultar deuda"),
            ("wait", 3),
            ("text", "Mi número de documento es 30123456"),
            ("wait", 3),
            ("button", "confirmar_deuda", "Confirmar"),
            ("wait", 3),
            ("text", "Gracias por la información"),
        ],
        "tramite_documento": [
            ("text", "Necesito hacer un trámite para obtener un documento"),
            ("wait", 2),
            (
                "list",
                "tramites",
                "Certificado de residencia",
                "Para realizar trámites municipales",
            ),
            ("wait", 3),
            ("button", "presencial", "Atención presencial"),
            ("wait", 2),
            (
                "location",
                -34.6037,
                -58.3816,
                "Mi ubicación actual",
                "Buenos Aires, Argentina",
            ),
            ("wait", 3),
            ("text", "¿Cuándo puedo ir a la oficina?"),
        ],
        "ayuda_general": [
            ("text", "Hola, necesito ayuda"),
            ("wait", 2),
            ("list", "menu_principal", "Ver opciones", ""),
            ("wait", 3),
            ("button", "informacion", "Información general"),
            ("wait", 3),
            ("text", "¿Cómo puedo contactar con un asesor?"),
            ("wait", 2),
            ("referral", "https://municipio.gob.ar/contacto", "website"),
        ],
    }

    if flow_name not in flows:
        print(f"❌ Flujo '{flow_name}' no encontrado.")
        print("Flujos disponibles: " + ", ".join(flows.keys()))
        return

    print(f"\n▶️ Ejecutando flujo: {flow_name}")
    for step in flows[flow_name]:
        try:
            step_type = step[0]

            if step_type == "wait":
                seconds = step[1]
                print(f"⏱️ Esperando {seconds} segundos...")
                time.sleep(seconds)

            elif step_type == "text":
                message = step[1]
                send_text_message(url, phone_number, name, message)

            elif step_type == "button":
                button_id = step[1]
                button_title = step[2]
                send_button_reply(url, phone_number, name, button_id, button_title)

            elif step_type == "list":
                list_id = step[1]
                list_title = step[2]
                list_description = step[3] if len(step) > 3 else ""
                send_list_reply(
                    url, phone_number, name, list_id, list_title, list_description
                )

            elif step_type == "location":
                lat, lon = step[1], step[2]
                place_name = step[3] if len(step) > 3 else ""
                address = step[4] if len(step) > 4 else ""
                send_location(url, phone_number, name, lat, lon, place_name, address)

            elif step_type == "referral":
                ref_url = step[1]
                ref_type = step[2] if len(step) > 2 else "ad"
                send_referral_message(url, phone_number, name, ref_url, ref_type)

            elif step_type == "media":
                media_type = step[1]
                media_url = step[2] if len(step) > 2 else None
                caption = step[3] if len(step) > 3 else None
                send_media_message(
                    url, phone_number, name, media_type, None, media_url, caption
                )

            elif step_type == "template":
                template_name = step[1]
                template_id = step[2]
                send_template_message_reply(
                    url, phone_number, name, template_name, template_id
                )

        except Exception as e:
            print(f"❌ Error en paso '{step_type}': {e}")
            break

    print(f"✅ Flujo '{flow_name}' completado.")


def script_mode(url, phone_number, name):
    """Ejecuta el simulador con un script predefinido de mensajes"""
    print("\n🤖 Simulador de WhatsApp - Modo Script")
    print(f"URL del webhook: {url}")
    print(f"Número de teléfono: {phone_number}")
    print(f"Nombre: {name}")
    print("\nEjecutando script de prueba...")

    # Simulación de verificación inicial
    simulate_verification(url)
    time.sleep(1)

    # Script de mensajes predefinidos
    # Este script prueba varios tipos de mensajes para simular una conversación completa
    script = [
        {
            "type": "text",
            "content": "Hola, necesito información sobre trámites municipales",
        },
        {"type": "wait", "seconds": 3},
        {"type": "button", "id": "menu_principal", "title": "Ver menú principal"},
        {"type": "wait", "seconds": 3},
        {
            "type": "list",
            "id": "tramites",
            "title": "Trámites personales",
            "description": "DNI, certificados y más",
        },
        {"type": "wait", "seconds": 3},
        {"type": "text", "content": "Necesito un certificado de residencia"},
        {"type": "wait", "seconds": 3},
        {
            "type": "location",
            "lat": -34.6037,
            "lon": -58.3816,
            "name": "Mi ubicación",
            "address": "Av. Corrientes 1000, Buenos Aires",
        },
        {"type": "wait", "seconds": 3},
        {"type": "text", "content": "¿Qué documentación necesito llevar?"},
        {"type": "wait", "seconds": 3},
        {"type": "button", "id": "finalizar", "title": "Gracias por la información"},
    ]

    for item in script:
        try:
            if item["type"] == "wait":
                print(f"\n⏱️ Esperando {item['seconds']} segundos...")
                time.sleep(item["seconds"])

            elif item["type"] == "text":
                send_text_message(url, phone_number, name, item["content"])

            elif item["type"] == "button":
                send_button_reply(url, phone_number, name, item["id"], item["title"])

            elif item["type"] == "list":
                description = item.get("description", "")
                send_list_reply(
                    url, phone_number, name, item["id"], item["title"], description
                )

            elif item["type"] == "location":
                place_name = item.get("name", "")
                address = item.get("address", "")
                send_location(
                    url,
                    phone_number,
                    name,
                    item["lat"],
                    item["lon"],
                    place_name,
                    address,
                )

            elif item["type"] == "media":
                media_type = item["media_type"]
                media_url = item.get("url")
                caption = item.get("caption")
                send_media_message(
                    url, phone_number, name, media_type, None, media_url, caption
                )

        except Exception as e:
            print(f"\n❌ Error en script: {e}")
            break

    print("\n✅ Script completado.")


def flows_mode(url, phone_number, name):
    """Modo específico para probar flujos de conversación"""
    print("\n🤖 Simulador de WhatsApp - Modo Flujos")
    print(f"URL del webhook: {url}")
    print(f"Número de teléfono: {phone_number}")
    print(f"Nombre: {name}")

    flows = {
        "1": {"name": "consulta_deuda", "description": "Consulta de deuda municipal"},
        "2": {"name": "tramite_documento", "description": "Trámite de documento"},
        "3": {"name": "ayuda_general", "description": "Menú de ayuda general"},
        "4": {"name": "verificar", "description": "Verificar el webhook"},
        "0": {"name": "salir", "description": "Salir del modo flujos"},
    }

    while True:
        print("\nFlujos disponibles:")
        for key, flow in flows.items():
            print(f"  {key}. {flow['description']}")

        choice = input("\nSeleccione un flujo (0-4): ")

        if choice == "0":
            print("👋 Saliendo del modo flujos...")
            break

        elif choice == "4":
            simulate_verification(url)

        elif choice in flows:
            flow_name = flows[choice]["name"]
            execute_flow(url, phone_number, name, flow_name)

        else:
            print("❌ Opción no válida. Intente de nuevo.")


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Simulador avanzado de mensajes de WhatsApppara pruebas del webhook"
    )

    parser.add_argument(
        "--url",
        default="http://localhost:8001/api/v1/webhook/",
        help="URL del webhook (por defecto: http://localhost:8001/api/v1/webhook/)",
    )
    parser.add_argument(
        "--phone",
        default="5492644472542",
        help="Número de teléfono del remitente (por defecto: 5492644472542)",
    )
    parser.add_argument(
        "--name",
        default="Usuario de Prueba",
        help="Nombre del remitente (por defecto: Usuario de Prueba)",
    )
    parser.add_argument(
        "--mode",
        default="interactive",
        choices=["interactive", "script", "flows", "verify"],
        help="Modo de operación: interactive (por defecto), script, flows o verify",
    )

    args = parser.parse_args()

    if args.mode == "verify":
        simulate_verification(args.url)
    elif args.mode == "script":
        script_mode(args.url, args.phone, args.name)
    elif args.mode == "flows":
        flows_mode(args.url, args.phone, args.name)
    else:  # interactive
        interactive_mode(args.url, args.phone, args.name)


if __name__ == "__main__":
    main()
