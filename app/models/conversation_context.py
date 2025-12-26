"""
Pydantic models for conversation context management.

These models are used for:
- Redis cache serialization/deserialization
- API request/response schemas
- Graph state context injection
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConversationMessageModel(BaseModel):
    """Model for individual conversation message."""

    sender_type: Literal["user", "assistant", "system"]
    content: str
    agent_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ConversationContextModel(BaseModel):
    """
    Model for persistent conversation context.

    This model holds the rolling summary and metadata for a conversation,
    enabling context injection across all agents in the graph.
    """

    conversation_id: str
    organization_id: str | None = None
    user_phone: str | None = None

    # Context data
    rolling_summary: str = ""
    topic_history: list[str] = Field(default_factory=list)
    key_entities: dict[str, Any] = Field(default_factory=dict)

    # Tracking
    total_turns: int = 0
    last_user_message: str | None = None
    last_bot_response: str | None = None
    last_agent: str | None = None  # Agent that processed last message (for flow continuity)

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def to_prompt_context(self) -> str:
        """
        Generate a string for injection into YAML prompts.

        Returns:
            Formatted context string or empty string if no summary exists.
        """
        if not self.rolling_summary:
            return ""
        return f"## Contexto de conversación anterior:\n{self.rolling_summary}"

    def get_display_name(self) -> str:
        """
        Generate a display name for UI selection.

        Returns:
            Human-readable conversation identifier.
        """
        if self.user_phone:
            return f"Chat {self.user_phone[-4:]} - {self.last_activity_at.strftime('%d/%m %H:%M')}"
        return f"Chat {self.conversation_id[:8]} - {self.last_activity_at.strftime('%d/%m %H:%M')}"

    def update_from_exchange(self, user_message: str, bot_response: str) -> None:
        """
        Update context with a new exchange.

        Args:
            user_message: The user's message
            bot_response: The assistant's response
        """
        self.total_turns += 1
        self.last_user_message = user_message
        self.last_bot_response = bot_response
        self.updated_at = datetime.now(UTC)
        self.last_activity_at = datetime.now(UTC)


class ConversationContextResponse(BaseModel):
    """API response model for conversation context."""

    conversation_id: str
    summary: str
    topic_history: list[str]
    total_turns: int
    last_activity: str


class MessageListResponse(BaseModel):
    """API response model for message list."""

    conversation_id: str
    messages: list[ConversationMessageModel]
    limit: int
    offset: int
    total: int | None = None


class ConversationListResponse(BaseModel):
    """API response model for list of conversations."""

    conversations: list[ConversationContextResponse]
    total: int


class SummaryResponse(BaseModel):
    """API response model for summary regeneration."""

    conversation_id: str
    new_summary: str
    total_turns: int
