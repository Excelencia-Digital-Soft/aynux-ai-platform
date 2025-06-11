from pydantic import BaseModel


class SupervisorConfig(BaseModel):
    """Configuración para el supervisor"""

    max_agent_switches: int = 5
    conversation_timeout: int = 1800  # 30 minutos
    enable_handoff_detection: bool = True
