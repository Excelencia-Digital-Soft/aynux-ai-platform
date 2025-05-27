from typing import Any, Dict, List, Optional

import httpx

from app.config.settings import get_settings


class WhatsAppService:
    """
    Servicio para interactuar con la API de WhatsApp
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.WHATSAPP_API_BASE
        self.version = self.settings.WHATSAPP_API_VERSION
        self.phone_number_id = self.settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = self.settings.WHATSAPP_VERIFY_TOKEN

    async def enviar_mensaje_texto(self, numero: str, mensaje: str) -> Dict[str, Any]:
        """
        Envía un mensaje de texto a través de WhatsApp

        Args:
            numero: Número de teléfono del destinatario
            mensaje: Contenido del mensaje

        Returns:
            Respuesta de la API de WhatsApp
        """
        url = f"{self.base_url}/{self.version}/{self.phone_number_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "text",
            "text": {"body": mensaje},
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def enviar_documento(self, numero: str, nombre: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un documento a través de WhatsApp

        Args:
            numero: Número de teléfono del destinatario
            archivo: Bytes del archivo a enviar
            nombre: Nombre del documento
            caption: Descripción opcional del documento

        Returns:
            Respuesta de la API de WhatsApp
        """

        url = f"{self.base_url}/{self.version}/{self.phone_number_id}/messages"

        document_url = "https://example.com/documents/sample.pdf"  # Placeholder

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

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

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
        url = f"{self.base_url}/{self.version}/{self.phone_number_id}/messages"

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

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

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
        url = f"{self.base_url}/{self.version}/{self.phone_number_id}/messages"

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

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

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
        url = f"{self.base_url}/{self.version}/{self.phone_number_id}/messages"

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

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
