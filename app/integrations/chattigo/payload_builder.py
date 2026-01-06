# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Builder para construir payloads de mensajes WhatsApp Cloud API.
#              Formato estándar de WhatsApp Business Cloud API.
# ============================================================================
"""
WhatsApp Cloud API Payload Builder.

Single Responsibility: Build properly formatted payloads for WhatsApp Cloud API
via Chattigo BSP endpoint.

API Reference:
- POST /v15.0/{did}/messages
- See: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
"""


class ChattigoPayloadBuilder:
    """
    Builder for WhatsApp Cloud API message payloads.

    Single Responsibility: Construct payloads for different message types.

    Message Format:
    {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "<phone_number>",
        "type": "<message_type>",
        "<message_type>": { ... }
    }
    """

    @staticmethod
    def build_text_payload(
        to: str,
        message: str,
        preview_url: bool = False,
    ) -> dict:
        """
        Build text message payload.

        Args:
            to: Recipient phone number (e.g., "5492644036998")
            message: Text content
            preview_url: Whether to enable URL preview

        Returns:
            Formatted payload dict for WhatsApp Cloud API
        """
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": message,
            },
        }

    @staticmethod
    def build_document_payload(
        to: str,
        document_url: str,
        filename: str,
        caption: str | None = None,
    ) -> dict:
        """
        Build document message payload.

        Args:
            to: Recipient phone number
            document_url: Public URL of the document
            filename: Document filename
            caption: Optional document caption

        Returns:
            Formatted payload dict for WhatsApp Cloud API
        """
        document_data: dict = {
            "link": document_url,
            "filename": filename,
        }
        if caption:
            document_data["caption"] = caption

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": document_data,
        }

    @staticmethod
    def build_image_payload(
        to: str,
        image_url: str,
        caption: str | None = None,
    ) -> dict:
        """
        Build image message payload.

        Args:
            to: Recipient phone number
            image_url: Public URL of the image
            caption: Optional image caption

        Returns:
            Formatted payload dict for WhatsApp Cloud API
        """
        image_data: dict = {
            "link": image_url,
        }
        if caption:
            image_data["caption"] = caption

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": image_data,
        }

    @staticmethod
    def build_template_payload(
        to: str,
        template_name: str,
        language_code: str = "es",
        components: list[dict] | None = None,
    ) -> dict:
        """
        Build template message payload.

        Args:
            to: Recipient phone number
            template_name: Name of the pre-approved template
            language_code: Template language code
            components: Optional template components (header, body, buttons)

        Returns:
            Formatted payload dict for WhatsApp Cloud API
        """
        template_data: dict = {
            "name": template_name,
            "language": {
                "code": language_code,
            },
        }
        if components:
            template_data["components"] = components

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template_data,
        }
