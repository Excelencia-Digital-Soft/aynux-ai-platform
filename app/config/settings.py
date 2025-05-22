from functools import lru_cache
from typing import Any, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


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
    ACCESS_TOKEN: str = Field(
        ..., description="Token de acceso para la API de WhatsApp"
    )
    PHONE_NUMBER_ID: str = Field(
        ..., description="ID del número de teléfono de WhatsApp"
    )
    APP_ID: str = Field(..., description="ID de la aplicación de Facebook")
    APP_SECRET: str = Field(..., description="Secreto de la aplicación de Facebook")
    VERIFY_TOKEN: str = Field(
        ..., description="Token de verificación para el webhook de WhatsApp"
    )
    WHATSAPP_API_VERSION: str = Field(
        "v18.0", description="Versión de la API de WhatsApp"
    )

    # API Base URLs
    MUNICIPIO_API_BASE: str = Field(
        "https://excelencia.myiphost.com:86/apimunicipios/api/v1",
        description="URL base para la API de Municipalidades",
    )
    MUNICIPIO_API_KEY: str = Field(
        ..., description="API Key para la API de Municipalidades"
    )
    # Credenciales para autenticación en la API de Municipalidades
    MUNICIPIO_API_USERNAME: str = Field(
        "excelencia", description="Usuario para la API de Municipalidades"
    )
    MUNICIPIO_API_PASSWORD: str = Field(
        "Password123!", description="Contraseña para la API de Municipalidades"
    )
    WHATSAPP_API_BASE: str = Field(
        "https://graph.facebook.com", description="URL base para la API de WhatsApp"
    )

    # Redis Settings
    REDIS_HOST: str = Field("localhost", description="Host de Redis")
    REDIS_PORT: int = Field(6379, description="Puerto de Redis")
    REDIS_DB: int = Field(0, description="Base de datos de Redis")
    REDIS_PASSWORD: Optional[str] = Field(None, description="Contraseña de Redis")

    # AI Service Settings
    OLLAMA_API_MODEL: str = Field("llama3.1", description="Modelo de ollama a usar")

    # JWT Settings
    JWT_SECRET_KEY: str = Field(..., description="Clave secreta para JWT")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        30, description="Tiempo de expiración del token de acceso en minutos"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        7, description="Tiempo de expiración del token de actualización en días"
    )

    # Application Settings
    DEBUG: bool = Field(False, description="Modo de depuración")
    ENVIRONMENT: str = Field("production", description="Entorno de ejecución")

    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # Ignorar campos extras en lugar de generar un error
    }

    def __init__(self, **data: Any):
        super().__init__(**data)


# @lru_cache()
def get_settings() -> Settings:
    """
    Retorna una instancia cacheada de la configuración.
    Esto evita cargar las variables de entorno múltiples veces.
    """
    return Settings()
