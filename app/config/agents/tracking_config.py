from .agent_config import AgentConfig


class TrackingAgentConfig(AgentConfig):
    """Configuración específica para el agente de seguimiento"""

    show_detailed_status: bool = True
    estimate_delivery: bool = True
    send_notifications: bool = True
