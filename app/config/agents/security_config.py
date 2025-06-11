from pydantic import BaseModel, Field


class SecurityConfig(BaseModel):
    """Configuración de seguridad"""

    rate_limit_messages: int = 20
    rate_limit_window: int = 60  # 1 minuto
    max_message_length: int = 1000
    blocked_words: list = Field(default_factory=list)
