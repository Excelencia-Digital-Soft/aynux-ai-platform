from typing import Any, ClassVar, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    """Modelo para historial de conversación"""

    id: str
    timestamp: str
    sender_id: str
    sender_name: str
    role: Literal["user", "assistant", "system"]
    content: str


class BotResponse(BaseModel):
    """Modelo para respuestas del bot"""

    status: Literal["success", "failure"]
    message: str


class TextMessage(BaseModel):
    """Modelo para mensajes de texto"""

    body: str


class ButtonReply(BaseModel):
    """Modelo para respuestas de botones"""

    id: str
    title: str


class ListReply(BaseModel):
    """Modelo para respuestas de listas"""

    id: str
    title: str
    description: Optional[str] = None


class InteractiveContent(BaseModel):
    """Modelo para contenido interactivo"""

    type: Literal["button_reply", "list_reply"]
    button_reply: Optional[ButtonReply] = None
    list_reply: Optional[ListReply] = None


class WhatsAppMessage(BaseModel):
    """Modelo para mensajes de WhatsApp"""

    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    type: Literal["text", "interactive", "image", "document", "location"]
    text: Optional[TextMessage] = None
    interactive: Optional[InteractiveContent] = None

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="ignore")


class Contact(BaseModel):
    """Modelo para contactos de WhatsApp"""

    wa_id: str
    profile: Dict[str, str]


class Change(BaseModel):
    """Modelo para cambios en el webhook"""

    value: Dict[str, Any]
    field: Literal["messages"]


class Entry(BaseModel):
    """Modelo para entradas en el webhook"""

    id: str
    changes: List[Change]


class WhatsAppWebhookRequest(BaseModel):
    """Modelo para solicitudes de webhook de WhatsApp"""

    object: str
    entry: List[Entry]

    def get_message(self) -> Optional[WhatsAppMessage]:
        """Extrae el mensaje de WhatsApp de la solicitud del webhook"""
        try:
            messages = self.entry[0].changes[0].value.get("messages", [])
            if messages:
                # Convertir el dict a un modelo WhatsAppMessage
                return WhatsAppMessage.model_validate(messages[0])
            return None
        except (IndexError, KeyError):
            return None

    def get_contact(self) -> Optional[Contact]:
        """Extrae el contacto de la solicitud del webhook"""
        try:
            contacts = self.entry[0].changes[0].value.get("contacts", [])
            if contacts:
                # Convertir el dict a un modelo Contact
                return Contact.model_validate(contacts[0])
            return None
        except (IndexError, KeyError):
            return None
