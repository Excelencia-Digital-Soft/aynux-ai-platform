from .agent_config import AgentConfig


class PromotionsAgentConfig(AgentConfig):
    """Configuración específica para el agente de promociones"""

    max_promotions_shown: int = 5
    check_eligibility: bool = True
    personalize_offers: bool = True
