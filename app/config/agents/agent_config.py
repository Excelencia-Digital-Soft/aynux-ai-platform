from pydantic import BaseModel


class AgentConfig(BaseModel):
    """Configuración base para agentes"""

    max_retries: int = 3
    timeout_seconds: int = 30
    cache_enabled: bool = True
    logging_level: str = "INFO"
