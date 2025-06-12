from typing import Optional

from models.database import Conversation
from sqlalchemy.orm import Session


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_conversation(self, user_phone: str) -> Conversation:
        session_id = f"session_{user_phone}"
        conversation = self.db.query(Conversation).filter(Conversation.session_id == session_id).first()

        if not conversation:
            conversation = Conversation(session_id=session_id, user_phone=user_phone, context_data={})
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)

        return conversation

    def update_context(self, session_id: str, context_data: dict) -> Optional[Conversation]:
        conversation = self.db.query(Conversation).filter(Conversation.session_id == session_id).first()
        if conversation:
            conversation.context_data = context_data
            self.db.commit()
            self.db.refresh(conversation)
        return conversation
