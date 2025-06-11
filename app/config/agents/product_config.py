from .agent_config import AgentConfig


class ProductAgentConfig(AgentConfig):
    """Configuración específica para el agente de productos"""

    max_products_shown: int = 10
    show_stock: bool = True
    show_prices: bool = True
    enable_recommendations: bool = True
