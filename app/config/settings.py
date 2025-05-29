from typing import Any, Optional

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración de la aplicación utilizando Pydantic BaseSettings.
    Carga automáticamente las variables de entorno.
    """

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "WhatsApp Chatbot API"
    PROJECT_DESCRIPTION: str = "API para integración con WhatsApp Business API"
    VERSION: str = "0.1.0"

    # WhatsApp API settings
    WHATSAPP_API_BASE: str = Field("https://graph.facebook.com", description="URL base para la API de WhatsApp")
    WHATSAPP_API_VERSION: str = Field("v22.0", description="Versión de la API de WhatsApp")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(..., description="ID del número de teléfono de WhatsApp")
    WHATSAPP_VERIFY_TOKEN: str = Field(..., description="Token de verificación para el webhook de WhatsApp")
    WHATSAPP_ACCESS_TOKEN: str = Field(..., description="Token de acceso permanente para la API de WhatsApp")
    META_APP_ID: str = Field(..., description="ID de la aplicación de Facebook")
    META_APP_SECRET: str = Field(..., description="Secreto de la aplicación de Facebook")

    # PostgreSQL Database Settings
    DB_HOST: str = Field("localhost", description="Host de PostgreSQL")
    DB_PORT: int = Field(5432, description="Puerto de PostgreSQL")
    DB_NAME: str = Field("conversashop", description="Nombre de la base de datos")
    DB_USER: str = Field("enzo", description="Usuario de PostgreSQL")
    DB_PASSWORD: Optional[str] = Field(None, description="Contraseña de PostgreSQL")
    DB_ECHO: bool = Field(False, description="Log SQL queries (solo para debug)")

    # Database connection pool settings
    DB_POOL_SIZE: int = Field(20, description="Tamaño del pool de conexiones")
    DB_MAX_OVERFLOW: int = Field(30, description="Máximo overflow del pool")
    DB_POOL_RECYCLE: int = Field(3600, description="Reciclar conexiones cada X segundos")
    DB_POOL_TIMEOUT: int = Field(30, description="Timeout para obtener conexión del pool")

    # Redis Settings
    REDIS_HOST: str = Field("localhost", description="Host de Redis")
    REDIS_PORT: int = Field(6379, description="Puerto de Redis")
    REDIS_DB: int = Field(0, description="Base de datos de Redis")
    REDIS_PASSWORD: Optional[str] = Field(None, description="Contraseña de Redis")

    # File Upload Settings
    MAX_FILE_SIZE: int = Field(10 * 1024 * 1024, description="Tamaño máximo de archivo en bytes (10MB)")
    ALLOWED_EXTENSIONS: list[str] = Field(
        default=["jpg", "jpeg", "png", "pdf", "doc", "docx"], description="Extensiones de archivo permitidas"
    )

    # AI Service Settings
    OLLAMA_API_MODEL: str = Field("llama3.1", description="Modelo de ollama a usar")
    OLLAMA_API_URL: str = Field("http://localhost:11434", description="URL del servicio Ollama")

    # JWT Settings
    JWT_SECRET_KEY: str = Field(..., description="Clave secreta para JWT")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, description="Tiempo de expiración del token de acceso en minutos")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(7, description="Tiempo de expiración del token de actualización en días")

    # Application Settings
    DEBUG: bool = Field(False, description="Modo de depuración")
    ENVIRONMENT: str = Field("production", description="Entorno de ejecución")

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignorar campos extras en lugar de generar un error
    )

    def __init__(self, **data: Any):
        super().__init__(**data)

    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_allowed_extensions(cls, value):
        if isinstance(value, str):
            return [ext.strip() for ext in value.split(",")]
        return value

    @field_validator("DB_POOL_SIZE")
    @classmethod
    def validate_pool_size(cls, v):
        if v < 1:
            raise ValueError("DB_POOL_SIZE must be at least 1")
        if v > 100:
            raise ValueError("DB_POOL_SIZE should not exceed 100")
        return v

    @field_validator("DB_MAX_OVERFLOW")
    @classmethod
    def validate_max_overflow(cls, v):
        if v < 0:
            raise ValueError("DB_MAX_OVERFLOW must be 0 or greater")
        if v > 200:
            raise ValueError("DB_MAX_OVERFLOW should not exceed 200")
        return v

    @computed_field
    @property
    def database_url(self) -> str:
        """Construye la URL de conexión a PostgreSQL"""
        if self.DB_PASSWORD:
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return f"postgresql://{self.DB_USER}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @computed_field
    @property
    def redis_url(self) -> str:
        """Construye la URL de conexión a Redis"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @computed_field
    @property
    def is_development(self) -> bool:
        """Determina si está en modo desarrollo"""
        return self.DEBUG or self.ENVIRONMENT.lower() in ["development", "dev", "local"]

    @computed_field
    @property
    def database_config(self) -> dict:
        """Configuración optimizada para la base de datos según el entorno"""
        base_config = {
            "echo": self.DB_ECHO,
            "future": True,
            "pool_pre_ping": True,
        }

        if self.is_development:
            # Configuración para desarrollo
            return {
                **base_config,
                "poolclass": "NullPool",
            }
        else:
            # Configuración para producción
            return {
                **base_config,
                "poolclass": "QueuePool",
                "pool_size": self.DB_POOL_SIZE,
                "max_overflow": self.DB_MAX_OVERFLOW,
                "pool_recycle": self.DB_POOL_RECYCLE,
                "pool_timeout": self.DB_POOL_TIMEOUT,
            }


# Singleton para configuración
_settings_instance = None


def get_settings() -> Settings:
    """
    Retorna una instancia cacheada de la configuración.
    Esto evita cargar las variables de entorno múltiples veces.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
