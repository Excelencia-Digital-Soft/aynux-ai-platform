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

    @staticmethod
    def build_interactive_buttons_payload(
        to: str,
        body: str,
        buttons: list[dict],
        header: str | None = None,
        footer: str | None = None,
    ) -> dict:
        """
        Build interactive buttons message payload.

        Args:
            to: Recipient phone number
            body: Message body text
            buttons: List of button dicts with "id" and "title" keys (max 3)
            header: Optional header text
            footer: Optional footer text

        Returns:
            Formatted payload dict for WhatsApp Cloud API

        Example buttons:
            [{"id": "btn_1", "title": "Option 1"}, {"id": "btn_2", "title": "Option 2"}]
        """
        action_buttons = [
            {"type": "reply", "reply": {"id": btn["id"], "title": btn["title"][:20]}}
            for btn in buttons[:3]  # WhatsApp allows max 3 buttons
        ]

        interactive_data: dict = {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": action_buttons},
        }

        if header:
            interactive_data["header"] = {"type": "text", "text": header}
        if footer:
            interactive_data["footer"] = {"text": footer}

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive_data,
        }

    @staticmethod
    def build_interactive_list_payload(
        to: str,
        body: str,
        button_text: str,
        sections: list[dict],
        header: str | None = None,
        footer: str | None = None,
    ) -> dict:
        """
        Build interactive list message payload.

        Args:
            to: Recipient phone number
            body: Message body text
            button_text: Text for the list button (max 20 chars)
            sections: List of section dicts with "title" and "rows" keys
            header: Optional header text
            footer: Optional footer text

        Returns:
            Formatted payload dict for WhatsApp Cloud API

        Example sections:
            [{
                "title": "Section 1",
                "rows": [
                    {"id": "row_1", "title": "Row 1", "description": "Desc 1"},
                    {"id": "row_2", "title": "Row 2", "description": "Desc 2"}
                ]
            }]
        """
        interactive_data: dict = {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text[:20],
                "sections": sections,
            },
        }

        if header:
            interactive_data["header"] = {"type": "text", "text": header}
        if footer:
            interactive_data["footer"] = {"text": footer}

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive_data,
        }

    @staticmethod
    def build_interactive_flow_payload(
        to: str,
        body: str,
        flow_id: str,
        flow_cta: str,
        screen: str,
        header: str | None = None,
        footer: str | None = None,
        flow_action: str = "navigate",
    ) -> dict:
        """
        Build WhatsApp Flow message payload.

        Args:
            to: Recipient phone number
            body: Message body text
            flow_id: WhatsApp Flow ID
            flow_cta: Call-to-action button text (max 20 chars)
            screen: Initial screen to navigate to
            header: Optional header text
            footer: Optional footer text
            flow_action: Flow action type (default: "navigate")

        Returns:
            Formatted payload dict for WhatsApp Cloud API
        """
        interactive_data: dict = {
            "type": "flow",
            "body": {"text": body},
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_action": flow_action,
                    "flow_token": "unused",
                    "flow_id": flow_id,
                    "flow_cta": flow_cta[:20],
                    "flow_action_payload": {"screen": screen},
                },
            },
        }

        if header:
            interactive_data["header"] = {"type": "text", "text": header}
        if footer:
            interactive_data["footer"] = {"text": footer}

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive_data,
        }
