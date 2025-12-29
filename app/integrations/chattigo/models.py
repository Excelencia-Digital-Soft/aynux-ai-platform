# ============================================================================
# SCOPE: GLOBAL
# Description: Modelos Pydantic para integración con Chattigo.
#              Chattigo actúa como intermediario entre WhatsApp y la aplicación.
# Tenant-Aware: No - Chattigo maneja autenticación por ISV.
# ============================================================================
"""
Chattigo Integration Models.

Based on DECSA implementation. Chattigo is a WhatsApp Business API intermediary
that handles Meta verification and forwards messages to the application.

Models:
- ChattigoLoginRequest/Response: Authentication with Chattigo API
- ChattigoWebhookPayload: Incoming webhook payload from Chattigo
- ChattigoMessage: Outbound message structure
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class ChattigoLoginRequest(BaseModel):
    """Request for Chattigo API authentication."""

    username: str
    password: str


class ChattigoLoginResponse(BaseModel):
    """Response from Chattigo API authentication."""

    access_token: str
    expires_in: int | None = None  # Seconds until token expires


class ChattigoWebhookPayload(BaseModel):
    """
    Incoming webhook payload from Chattigo.

    Chattigo sends this payload when a WhatsApp message is received.
    All fields are optional to handle various message types.
    """

    id: str | None = None
    msisdn: str | None = None  # User's phone number (sender)
    did: str | None = None  # Destination phone number (bot's number)
    idChat: int | None = None  # Chat/conversation ID
    content: str | None = ""  # Message content (text)
    name: str | None = None  # User's name
    chatType: str | None = None  # INBOUND or OUTBOUND
    channel: str | None = None  # WHATSAPP, etc.
    channelId: int | None = None
    channelProvider: str | None = None  # APICLOUDBSP, etc.
    idCampaign: str | None = None
    isAttachment: bool | None = False
    stateAgent: str | None = None  # BOT, AGENT, etc.
    abiStatus: str | None = None
    type: str | None = "Text"  # Text, Audio, Image, Document, Location, etc.
    attachment: dict[str, Any] | None = None  # Attachment data if any

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields without failing
        validate_assignment=True,
    )

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, v: Any) -> str:
        """Allow empty content for attachments."""
        if v is None:
            return ""
        return str(v)

    @field_validator("idChat", mode="before")
    @classmethod
    def validate_id_chat(cls, v: Any) -> int | None:
        """Convert idChat to int if possible."""
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("channelId", mode="before")
    @classmethod
    def validate_channel_id(cls, v: Any) -> int | None:
        """Convert channelId to int if possible."""
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    def is_text_message(self) -> bool:
        """Check if this is a text message."""
        return self.type == "Text" and bool(self.content)

    def is_attachment(self) -> bool:
        """Check if this is an attachment message."""
        return self.isAttachment is True or self.type in (
            "Audio",
            "Image",
            "Document",
            "Video",
        )


class ChattigoOutboundMessage(BaseModel):
    """
    Outbound message structure for Chattigo API.

    Used when sending messages back to users via Chattigo.
    """

    id: str  # Unique message ID
    idChat: int  # Chat/conversation ID
    chatType: str = "OUTBOUND"
    did: str  # Bot's phone number
    msisdn: str  # User's phone number
    type: str = "Text"  # Text, Image, Document, etc.
    channel: str = "WHATSAPP"
    channelId: int
    channelProvider: str = "APICLOUDBSP"
    content: str  # Message content
    name: str = "Aynux"  # Bot name
    idCampaign: str
    isAttachment: bool = False
    stateAgent: str = "BOT"


class ChattigoAttachmentMessage(BaseModel):
    """
    Outbound attachment message for Chattigo API.

    Used when sending documents, images, etc. via Chattigo.
    """

    id: str
    idChat: int
    chatType: str = "OUTBOUND"
    did: str
    msisdn: str
    type: str  # Image, Document, Audio, Video
    channel: str = "WHATSAPP"
    channelId: int
    channelProvider: str = "APICLOUDBSP"
    content: str = ""  # Caption or empty
    name: str = "Aynux"
    idCampaign: str
    isAttachment: bool = True
    stateAgent: str = "BOT"
    attachment: dict[str, Any]  # URL, filename, mimetype, etc.
