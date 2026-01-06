from pydantic import BaseModel


class IntegrationConfig(BaseModel):
    """Configuración para integraciones externas"""

    vllm_url: str = "http://localhost:8090/v1"
    vllm_model: str = "qwen-3b"
    postgres_pool_size: int = 5
    redis_ttl: int = 86400  # 24 horas
