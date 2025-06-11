from .agent_config import AgentConfig


class SupportAgentConfig(AgentConfig):
    """Configuración específica para el agente de soporte"""

    escalate_threshold: int = 3
    knowledge_base_enabled: bool = True
    human_handoff_enabled: bool = True
