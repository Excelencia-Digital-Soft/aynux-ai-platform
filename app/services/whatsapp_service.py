import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config.settings import get_settings
from app.services.phone_normalizer_pydantic import get_normalized_number_only

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Servicio para interactuar con la API de WhatsApp
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.WHATSAPP_API_BASE
        self.version = self.settings.WHATSAPP_API_VERSION
        self.phone_number_id = self.settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = self.settings.WHATSAPP_ACCESS_TOKEN

        # Logging de configuración (sin exponer el token completo)
        logger.info("WhatsApp Service initialized:")
        logger.info(f"  Base URL: {self.base_url}")
        logger.info(f"  Version: {self.version}")
        logger.info(f"  Phone ID: {self.phone_number_id}")
        logger.info(f"  Token: ***{self.access_token[-8:] if len(self.access_token) > 8 else '***'}")

    def _get_headers(self) -> Dict[str, str]:
        """Genera headers estándar para las requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _get_message_url(self) -> str:
        """Construye la URL correcta para enviar mensajes"""
        # La URL debe ser: https://graph.facebook.com/v22.0/{phone_number_id}/messages
        return f"{self.base_url}/{self.version}/{self.phone_number_id}/messages"

    async def _make_request(self, payload: Dict[str, Any], endpoint: str = "messages") -> Dict[str, Any]:
        """
        Realiza una request HTTP con manejo robusto de errores
        """
        url = self._get_message_url() if endpoint == "messages" else f"{self.base_url}/{self.version}/{endpoint}"
        headers = self._get_headers()

        try:
            logger.debug(f"Enviando request a: {url}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Payload: {payload}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)

                logger.info(f"WhatsApp API Response: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Mensaje enviado exitosamente: {result}")
                    return {"success": True, "data": result}
                else:
                    error_detail = response.text
                    logger.error(f"Error {response.status_code} de WhatsApp API: {error_detail}")

                    # Parsear error si es JSON
                    try:
                        error_json = response.json()
                        error_message = error_json.get("error", {}).get("message", error_detail)
                    except Exception as error_msg:
                        error_message = error_detail or error_msg

                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {error_message}",
                        "status_code": response.status_code,
                    }

        except httpx.TimeoutException:
            error_msg = "Timeout al comunicarse con WhatsApp API"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except httpx.ConnectError:
            error_msg = "Error de conexión con WhatsApp API"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def enviar_mensaje_texto(self, numero: str, mensaje: str) -> Dict[str, Any]:
        """
        Envía un mensaje de texto a través de WhatsApp

        Args:
            numero: Número de teléfono del destinatario
            mensaje: Contenido del mensaje

        Returns:
            Respuesta de la API de WhatsApp
        """

        # Validar entrada
        if not numero or not mensaje:
            return {"success": False, "error": "Número y mensaje son requeridos"}

        # NORMALIZACIÓN AUTOMÁTICA DEL NÚMERO
        original_number = numero

        # Determinar si estamos en modo de prueba
        test_mode = self.settings.is_development

        # Normalizar el número usando el normalizador Pydantic
        numero_normalizado = get_normalized_number_only(numero, test_mode=test_mode)

        if numero_normalizado:
            # Log de la transformación
            if original_number != numero_normalizado:
                logger.info(f"Número normalizado: {original_number} -> {numero_normalizado}")
            
            # Usar el número normalizado
            numero = numero_normalizado
        else:
            logger.warning(f"No se pudo normalizar el número {original_number}")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "text",
            "text": {"body": mensaje},
        }

        return await self._make_request(payload)

    async def enviar_documento(
        self, numero: str, nombre: str, document_url: str, caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envía un documento a través de WhatsApp

        Args:
            numero: Número de teléfono del destinatario
            nombre: Nombre del documento
            document_url: URL del documento
            caption: Descripción opcional del documento

        Returns:
            Respuesta de la API de WhatsApp
        """

        if not numero or not nombre or not document_url:
            return {"success": False, "error": "Número, nombre y URL del documento son requeridos"}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "document",
            "document": {"link": document_url, "filename": nombre},
        }

        # Añadir caption si es proporcionado
        if caption:
            payload["document"]["caption"] = caption

        return await self._make_request(payload)

    async def enviar_ubicacion(
        self, numero: str, latitud: float, longitud: float, nombre: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envía una ubicación a través de WhatsApp

        Args:
            numero: Número de teléfono del destinatario
            latitud: Latitud de la ubicación
            longitud: Longitud de la ubicación
            nombre: Nombre opcional de la ubicación

        Returns:
            Respuesta de la API de WhatsApp
        """
        if not numero or latitud is None or longitud is None:
            return {"success": False, "error": "Número, latitud y longitud son requeridos"}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "location",
            "location": {"latitude": latitud, "longitude": longitud},
        }

        # Añadir nombre si es proporcionado
        if nombre:
            payload["location"]["name"] = nombre

        return await self._make_request(payload)

    async def enviar_lista_opciones(
        self, numero: str, titulo: str, cuerpo: str, opciones: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Envía una lista de opciones interactivas a través de WhatsApp

        Args:
            numero: Número de teléfono del destinatario
            titulo: Título del mensaje
            cuerpo: Contenido del mensaje
            opciones: Lista de opciones disponibles

        Returns:
            Respuesta de la API de WhatsApp
        """
        if not numero or not titulo or not cuerpo or not opciones:
            return {"success": False, "error": "Todos los parámetros son requeridos"}

        # Preparar las secciones para la lista
        rows = []
        for opcion in opciones:
            rows.append(
                {
                    "id": opcion.get("id", ""),
                    "title": opcion.get("titulo", ""),
                    "description": opcion.get("descripcion", ""),
                }
            )

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": titulo},
                "body": {"text": cuerpo},
                "action": {
                    "button": "Ver opciones",
                    "sections": [{"title": "Opciones disponibles", "rows": rows}],
                },
            },
        }

        return await self._make_request(payload)

    async def enviar_botones(
        self, numero: str, titulo: str, cuerpo: str, botones: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Envía botones interactivos a través de WhatsApp

        Args:
            numero: Número de teléfono del destinatario
            titulo: Título del mensaje
            cuerpo: Contenido del mensaje
            botones: Lista de botones disponibles

        Returns:
            Respuesta de la API de WhatsApp
        """
        if not numero or not titulo or not cuerpo or not botones:
            return {"success": False, "error": "Todos los parámetros son requeridos"}

        # Preparar los botones
        buttons = []
        for boton in botones:
            buttons.append(
                {
                    "type": "reply",
                    "reply": {
                        "id": boton.get("id", ""),
                        "title": boton.get("titulo", ""),
                    },
                }
            )

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": titulo},
                "body": {"text": cuerpo},
                "action": {"buttons": buttons},
            },
        }

        return await self._make_request(payload)

    async def verificar_configuracion(self) -> Dict[str, Any]:
        """
        Verifica la configuración de WhatsApp API
        """
        issues = []

        if not self.access_token:
            issues.append("Token de acceso no configurado")
        elif len(self.access_token) < 50:
            issues.append("Token de acceso parece inválido (muy corto)")

        if not self.phone_number_id:
            issues.append("Phone Number ID no configurado")
        elif not self.phone_number_id.isdigit():
            issues.append("Phone Number ID debe ser numérico")

        if not self.base_url.startswith("https://"):
            issues.append("Base URL debe usar HTTPS")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "config": {
                "base_url": self.base_url,
                "version": self.version,
                "phone_id": self.phone_number_id,
                "token_length": len(self.access_token) if self.access_token else 0,
            },
        }
