"""
WhatsApp Messenger.

Single Responsibility: Build and send WhatsApp messages of various types.
"""

import logging
from typing import Any

from app.core.shared.utils import get_normalized_number_only
from app.integrations.whatsapp.http_client import WhatsAppHttpClient
from app.models.whatsapp_advanced import (
    MessageFactory,
    WhatsAppApiResponse,
)

logger = logging.getLogger(__name__)


class WhatsAppMessenger:
    """
    Message sender for WhatsApp.

    Single Responsibility: Build and send messages of different types.
    """

    def __init__(
        self,
        http_client: WhatsAppHttpClient,
        catalog_id: str,
        is_development: bool = False,
    ):
        """
        Initialize messenger.

        Args:
            http_client: HTTP client for API calls
            catalog_id: Default catalog ID
            is_development: Whether running in development mode
        """
        self._client = http_client
        self._catalog_id = catalog_id
        self._is_development = is_development

    def _normalize_number(self, numero: str) -> str:
        """Normalize phone number."""
        normalized = get_normalized_number_only(numero, test_mode=self._is_development)
        if normalized and normalized != numero:
            logger.info(f"Number normalized: {numero} -> {normalized}")
        return normalized or numero

    async def send_text(self, numero: str, mensaje: str) -> dict[str, Any]:
        """Send text message."""
        if not numero or not mensaje:
            return {"success": False, "error": "Number and message required"}

        numero = self._normalize_number(numero)

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "text",
            "text": {"body": mensaje},
        }

        return await self._client.post(payload)

    async def send_document(
        self,
        numero: str,
        nombre: str,
        document_url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Send document."""
        if not numero or not nombre or not document_url:
            return {"success": False, "error": "Number, name and URL required"}

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "document",
            "document": {"link": document_url, "filename": nombre},
        }

        if caption:
            payload["document"]["caption"] = caption

        return await self._client.post(payload)

    async def send_location(
        self,
        numero: str,
        latitud: float,
        longitud: float,
        nombre: str | None = None,
    ) -> dict[str, Any]:
        """Send location."""
        if not numero or latitud is None or longitud is None:
            return {"success": False, "error": "Number, latitude and longitude required"}

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "location",
            "location": {"latitude": latitud, "longitude": longitud},
        }

        if nombre:
            payload["location"]["name"] = nombre

        return await self._client.post(payload)

    async def send_list(
        self,
        numero: str,
        titulo: str,
        cuerpo: str,
        opciones: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send interactive list."""
        if not numero or not titulo or not cuerpo or not opciones:
            return {"success": False, "error": "All parameters required"}

        rows = [
            {
                "id": opt.get("id", ""),
                "title": opt.get("titulo", ""),
                "description": opt.get("descripcion", ""),
            }
            for opt in opciones
        ]

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

        return await self._client.post(payload)

    async def send_buttons(
        self,
        numero: str,
        titulo: str,
        cuerpo: str,
        botones: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send interactive buttons."""
        if not numero or not titulo or not cuerpo or not botones:
            return {"success": False, "error": "All parameters required"}

        buttons = [
            {"type": "reply", "reply": {"id": btn.get("id", ""), "title": btn.get("titulo", "")}}
            for btn in botones
        ]

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

        return await self._client.post(payload)

    async def send_product_list(
        self,
        numero: str,
        body_text: str,
        header_text: str | None = None,
        product_retailer_id: str | None = None,
        catalog_id: str | None = None,
    ) -> WhatsAppApiResponse:
        """Send product catalog list."""
        if not numero or not body_text:
            return WhatsAppApiResponse(success=False, error="Number and body required")

        numero = self._normalize_number(numero)
        used_catalog_id = catalog_id or self._catalog_id

        try:
            message = MessageFactory.create_product_list_message(
                to=numero,
                catalog_id=used_catalog_id,
                body_text=body_text,
                header_text=header_text,
                product_retailer_id=product_retailer_id,
            )

            payload = message.model_dump(exclude_none=True)
            logger.info(f"Sending product list from catalog {used_catalog_id} to {numero}")
            response = await self._client.post(payload)

            return WhatsAppApiResponse(
                success=response.get("success", False),
                data=response.get("data"),
                error=response.get("error"),
                status_code=response.get("status_code"),
            )

        except Exception as e:
            logger.error(f"Error creating catalog message: {e}")
            return WhatsAppApiResponse(success=False, error=str(e))

    async def send_flow(
        self,
        numero: str,
        flow_id: str,
        flow_cta: str,
        body_text: str | None = None,
        header_text: str | None = None,
        flow_token: str | None = None,
        flow_data: dict[str, Any] | None = None,
    ) -> WhatsAppApiResponse:
        """Send WhatsApp Flow message."""
        if not numero or not flow_id or not flow_cta:
            return WhatsAppApiResponse(success=False, error="Number, flow_id and flow_cta required")

        numero = self._normalize_number(numero)

        try:
            message = MessageFactory.create_flow_message(
                to=numero,
                flow_id=flow_id,
                flow_cta=flow_cta,
                body_text=body_text,
                header_text=header_text,
                flow_token=flow_token,
                flow_action_payload=flow_data,
            )

            payload = message.model_dump(exclude_none=True)
            logger.info(f"Sending Flow {flow_id} to {numero}")
            response = await self._client.post(payload)

            return WhatsAppApiResponse(
                success=response.get("success", False),
                data=response.get("data"),
                error=response.get("error"),
                status_code=response.get("status_code"),
            )

        except Exception as e:
            logger.error(f"Error creating Flow message: {e}")
            return WhatsAppApiResponse(success=False, error=str(e))

    async def send_template(
        self,
        numero: str,
        template_name: str,
        language_code: str = "es",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Send a WhatsApp template message (HSM - Highly Structured Message).

        Template messages must be pre-approved in Meta Business Manager.
        Supports headers (document, image, video), body parameters, and buttons.

        Args:
            numero: Recipient phone number
            template_name: Name of the pre-approved template
            language_code: Template language code (default: "es")
            components: Template components (header, body, button parameters)
                       Example for document header + body params:
                       [
                           {
                               "type": "header",
                               "parameters": [{
                                   "type": "document",
                                   "document": {
                                       "link": "https://example.com/doc.pdf",
                                       "filename": "Receipt.pdf"
                                   }
                               }]
                           },
                           {
                               "type": "body",
                               "parameters": [
                                   {"type": "text", "text": "value1"},
                                   {"type": "text", "text": "value2"}
                               ]
                           }
                       ]

        Returns:
            API response dict with success status and data
        """
        if not numero or not template_name:
            return {"success": False, "error": "Number and template name required"}

        numero = self._normalize_number(numero)

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }

        # Add components if provided (header, body, buttons)
        if components:
            payload["template"]["components"] = components

        logger.info(f"Sending template '{template_name}' to {numero}")
        return await self._client.post(payload)

    async def send_template_with_document(
        self,
        numero: str,
        template_name: str,
        document_url: str,
        document_filename: str,
        body_params: list[str] | None = None,
        language_code: str = "es",
    ) -> dict[str, Any]:
        """
        Send a template message with a document header and optional body parameters.

        Convenience method for common receipt/invoice templates.

        Args:
            numero: Recipient phone number
            template_name: Name of the pre-approved template
            document_url: Public URL of the document (PDF)
            document_filename: Filename to show to recipient
            body_params: List of body parameter values ({{1}}, {{2}}, etc.)
            language_code: Template language code (default: "es")

        Returns:
            API response dict with success status and data
        """
        components: list[dict[str, Any]] = [
            {
                "type": "header",
                "parameters": [
                    {
                        "type": "document",
                        "document": {
                            "link": document_url,
                            "filename": document_filename,
                        },
                    }
                ],
            }
        ]

        # Add body parameters if provided
        if body_params:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": param} for param in body_params],
                }
            )

        return await self.send_template(
            numero=numero,
            template_name=template_name,
            language_code=language_code,
            components=components,
        )
