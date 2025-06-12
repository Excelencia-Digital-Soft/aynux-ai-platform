from typing import List, Optional

from models.database import Message
from models.webhook import MessageStatus, WhatsAppMessage
from sqlalchemy.orm import Session


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_message(self, message: WhatsAppMessage) -> Message:
        db_message = Message(
            id=message.id,
            user_phone=message.from_number,
            message_type=message.message_type.value,
            content=message.content,
            metadata=message.metadata,
        )
        self.db.add(db_message)
        self.db.commit()
        self.db.refresh(db_message)
        return db_message

    def update_message_response(self, message_id: str, response: str, status: MessageStatus) -> Optional[Message]:
        message = self.db.query(Message).filter(Message.id == message_id).first()
        if message:
            message.response = response
            message.status = status.value
            self.db.commit()
            self.db.refresh(message)
        return message

    def get_user_message_history(self, user_phone: str, limit: int = 10) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.user_phone == user_phone)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
