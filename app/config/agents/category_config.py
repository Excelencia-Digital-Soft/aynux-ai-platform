from .agent_config import AgentConfig


class CategoryAgentConfig(AgentConfig):
    """Configuración específica para el agente de categorías"""

    max_categories_shown: int = 8
    use_vector_search: bool = True
    similarity_threshold: float = 0.7
