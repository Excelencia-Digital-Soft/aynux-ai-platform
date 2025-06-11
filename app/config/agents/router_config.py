from pydantic import BaseModel


class RouterConfig(BaseModel):
    """Configuración para el router de intenciones"""

    confidence_threshold: float = 0.75
    enable_fallback: bool = True
    fallback_agent: str = "support_agent"
    intent_cache_ttl: int = 300  # 5 minutos
