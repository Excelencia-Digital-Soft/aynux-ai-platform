from pydantic import BaseModel


class IntegrationConfig(BaseModel):
    """Configuración para integraciones externas"""

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    chromadb_path: str = "./data/chromadb"
    postgres_pool_size: int = 5
    redis_ttl: int = 86400  # 24 horas
