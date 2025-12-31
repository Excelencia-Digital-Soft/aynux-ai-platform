# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Builder para construir payloads de mensajes Chattigo.
# ============================================================================
"""
Chattigo Payload Builder.

Single Responsibility: Build properly formatted payloads for Chattigo API.
"""

import time


class ChattigoPayloadBuilder:
    """
    Builder for Chattigo API message payloads.

    Single Responsibility: Construct payloads for different message types.
    """

    @staticmethod
    def _generate_message_id() -> str:
        """Generate unique message ID based on timestamp."""
        return str(int(time.time() * 1000))

    @staticmethod
    def build_text_payload(
        did: str,
        msisdn: str,
        message: str,
        sender_name: str,
    ) -> dict:
        """
        Build text message payload.

        Args:
            did: WhatsApp Business DID
            msisdn: Recipient phone number
            message: Text content
            sender_name: Sender display name

        Returns:
            Formatted payload dict for Chattigo API
        """
        return {
            "id": ChattigoPayloadBuilder._generate_message_id(),
            "did": did,
            "msisdn": msisdn,
            "type": "text",
            "channel": "WHATSAPP",
            "chatType": "OUTBOUND",
            "content": message,
            "name": sender_name,
            "isAttachment": False,
        }

    @staticmethod
    def build_document_payload(
        did: str,
        msisdn: str,
        document_url: str,
        filename: str,
        mime_type: str,
        caption: str,
        sender_name: str,
    ) -> dict:
        """
        Build document message payload.

        Args:
            did: WhatsApp Business DID
            msisdn: Recipient phone number
            document_url: Public URL of the document
            filename: Document filename
            mime_type: MIME type (e.g., application/pdf)
            caption: Document caption
            sender_name: Sender display name

        Returns:
            Formatted payload dict for Chattigo API
        """
        return {
            "id": ChattigoPayloadBuilder._generate_message_id(),
            "did": did,
            "msisdn": msisdn,
            "type": "media",
            "channel": "WHATSAPP",
            "chatType": "OUTBOUND",
            "content": caption,
            "name": sender_name,
            "isAttachment": True,
            "attachment": {
                "mediaUrl": document_url,
                "mimeType": mime_type,
                "fileName": filename,
            },
        }

    @staticmethod
    def build_image_payload(
        did: str,
        msisdn: str,
        image_url: str,
        caption: str,
        mime_type: str,
        sender_name: str,
    ) -> dict:
        """
        Build image message payload.

        Args:
            did: WhatsApp Business DID
            msisdn: Recipient phone number
            image_url: Public URL of the image
            caption: Image caption
            mime_type: MIME type (e.g., image/jpeg)
            sender_name: Sender display name

        Returns:
            Formatted payload dict for Chattigo API
        """
        return {
            "id": ChattigoPayloadBuilder._generate_message_id(),
            "did": did,
            "msisdn": msisdn,
            "type": "media",
            "channel": "WHATSAPP",
            "chatType": "OUTBOUND",
            "content": caption,
            "name": sender_name,
            "isAttachment": True,
            "attachment": {
                "mediaUrl": image_url,
                "mimeType": mime_type,
            },
        }
