import json
from typing import Annotated, Any

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def parse_str_list(value: Any) -> list[str]:
    """Parse a list from JSON array or comma-separated string."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        if value.startswith("["):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if v]
            except json.JSONDecodeError:
                # Invalid JSON, salvage comma-separated inside brackets
                inner = value.strip("[]")
                return [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def parse_int_list(value: Any) -> list[int]:
    """Parse a list of integers from JSON array or comma-separated string."""
    if isinstance(value, list):
        return [int(v) for v in value]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        if value.startswith("["):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [int(v) for v in parsed]
            except (json.JSONDecodeError, ValueError):
                inner = value.strip("[]")
                return [int(v.strip()) for v in inner.split(",") if v.strip()]
        return [int(v.strip()) for v in value.split(",") if v.strip()]
    return []


class Settings(BaseSettings):
    """
    Configuración de la aplicación utilizando Pydantic BaseSettings.
    Carga automáticamente las variables de entorno.
    """

    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "WhatsApp Chatbot API"
    PROJECT_DESCRIPTION: str = "API para integración con WhatsApp Business API"
    VERSION: str = "0.1.0"

    # Chattigo Integration Settings (ISV mode)
    # Chattigo is a WhatsApp Business API intermediary that handles Meta verification
    # ISV mode: Chattigo manages credentials, we only need endpoint configuration
    CHATTIGO_ENABLED: bool = Field(True, description="Enable Chattigo integration")
    CHATTIGO_LOGIN_URL: str = Field(
        "https://channels.chattigo.com/bsp-cloud-chattigo-isv/login",
        description="Chattigo login endpoint",
    )
    CHATTIGO_MESSAGE_URL: str = Field(
        "https://channels.chattigo.com/bsp-cloud-chattigo-isv/webhooks/inbound",
        description="Chattigo message sending endpoint",
    )
    # Chattigo credentials (username, password, bot_name, channel_id, campaign_id) are now stored
    # in the database with encryption. Configure via Admin API: POST /api/v1/admin/chattigo-credentials
    CHATTIGO_DID: str = Field("5492644710400", description="Default WhatsApp Business number (Device ID)")
    CHATTIGO_BASE_URL: str = Field(
        "https://channels.chattigo.com/bsp-cloud-chattigo-isv",
        description="Chattigo API base URL (for webhook registration)",
    )

    # PostgreSQL Database Settings
    DB_HOST: str = Field("localhost", description="Host de PostgreSQL")
    DB_PORT: int = Field(5432, description="Puerto de PostgreSQL")
    DB_NAME: str = Field("aynux", description="Nombre de la base de datos")
    DB_USER: str = Field("enzo", description="Usuario de PostgreSQL")
    DB_PASSWORD: str | None = Field(None, description="Contraseña de PostgreSQL")
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
    REDIS_PASSWORD: str | None = Field(None, description="Contraseña de Redis")

    # File Upload Settings
    MAX_FILE_SIZE: int = Field(10 * 1024 * 1024, description="Tamaño máximo de archivo en bytes (10MB)")
    # NoDecode prevents pydantic-settings from trying json.loads() - we parse manually
    ALLOWED_EXTENSIONS: Annotated[list[str], NoDecode] = Field(
        default=["jpg", "jpeg", "png", "pdf", "doc", "docx"],
        description="Extensiones de archivo permitidas",
    )

    # AI Service Settings - Model Tiers
    # SIMPLE: Fast model for intent analysis, classification
    # COMPLEX: Powerful model for complex responses
    # REASONING: Deep reasoning model for complex analysis
    # SUMMARY: Fast non-reasoning model for conversation summarization
    #
    # When EXTERNAL_LLM_ENABLED=true:
    #   - COMPLEX/REASONING → External API (DeepSeek, KIMI, etc.)
    #   - SIMPLE/SUMMARY → Ollama local
    # When EXTERNAL_LLM_ENABLED=false (default):
    #   - All tiers → Ollama local

    # Ollama models (used for SIMPLE/SUMMARY tiers, and as fallback)
    OLLAMA_API_MODEL_SIMPLE: str = Field("gemma3", description="Modelo rápido para tareas simples (intent analysis)")
    OLLAMA_API_MODEL_COMPLEX: str = Field(
        "gemma2", description="Modelo potente para respuestas complejas (usado si EXTERNAL_LLM_ENABLED=false)"
    )
    OLLAMA_API_MODEL_REASONING: str = Field(
        "deepseek-r1:8b", description="Modelo para razonamiento profundo (usado si EXTERNAL_LLM_ENABLED=false)"
    )
    OLLAMA_API_MODEL_SUMMARY: str = Field(
        "llama3.2", description="Modelo rápido para resumen de conversación (evitar modelos reasoning)"
    )

    # External LLM API Configuration (DeepSeek, KIMI, OpenAI-compatible)
    # When enabled, COMPLEX and REASONING tiers use the external API
    EXTERNAL_LLM_ENABLED: bool = Field(
        False, description="Enable external API for COMPLEX/REASONING tiers (DeepSeek, KIMI, etc.)"
    )
    EXTERNAL_LLM_PROVIDER: str = Field("deepseek", description="External LLM provider: deepseek, kimi, openai")
    EXTERNAL_LLM_API_KEY: str | None = Field(None, description="API key for external LLM provider")
    EXTERNAL_LLM_BASE_URL: str | None = Field(
        None, description="Base URL override (auto-detected for known providers if not set)"
    )
    EXTERNAL_LLM_MODEL_COMPLEX: str = Field("deepseek-chat", description="Model for COMPLEX tier on external API")
    EXTERNAL_LLM_MODEL_REASONING: str = Field(
        "deepseek-reasoner", description="Model for REASONING tier on external API"
    )
    EXTERNAL_LLM_TIMEOUT: int = Field(120, description="Timeout for external API calls in seconds")
    EXTERNAL_LLM_MAX_RETRIES: int = Field(3, description="Max retries for external API calls")
    EXTERNAL_LLM_FALLBACK_MODEL: str = Field(
        "llama3.1:8b", description="Ollama model to use as fallback when external API fails"
    )

    OLLAMA_API_URL: str = Field("http://localhost:11434", description="URL del servicio Ollama")
    OLLAMA_API_MODEL_EMBEDDING: str = Field(
        "nomic-embedtext", description="Embedding del modelo de ollama (768 dimensions)"
    )

    # Ollama Performance Settings
    OLLAMA_KEEP_ALIVE: str = Field("30m", description="Tiempo que el modelo permanece en memoria")
    OLLAMA_NUM_THREAD: int = Field(8, description="Número de threads para inferencia")
    OLLAMA_WARMUP_ON_STARTUP: bool = Field(True, description="Pre-cargar modelo LLM en startup")
    OLLAMA_REQUEST_TIMEOUT: int = Field(60, description="Timeout para requests al LLM en segundos")

    # LLM Streaming Configuration
    LLM_STREAMING_ENABLED: bool = Field(False, description="Enable streaming for web responses")
    LLM_STREAMING_FOR_WEBHOOK: bool = Field(False, description="Enable streaming for webhook (usually False)")

    # Vector Search Configuration (pgvector only)
    PGVECTOR_SIMILARITY_THRESHOLD: float = Field(
        0.6, description="Minimum similarity threshold for pgvector search (0.0-1.0)"
    )

    # Knowledge Base Configuration
    KNOWLEDGE_BASE_ENABLED: bool = Field(True, description="Enable company knowledge base with RAG")
    # Note: Knowledge base uses OLLAMA_API_MODEL_EMBEDDING for embeddings
    # and PGVECTOR_SIMILARITY_THRESHOLD for similarity matching

    # JWT Settings
    JWT_SECRET_KEY: str = Field(..., description="Clave secreta para JWT")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, description="Tiempo de expiración del token de acceso en minutos")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(7, description="Tiempo de expiración del token de actualización en días")

    # Application Settings
    DEBUG: bool = Field(False, description="Modo de depuración")
    ENVIRONMENT: str = Field("production", description="Entorno de ejecución")

    # Multi-Tenant Settings
    MULTI_TENANT_MODE: bool = Field(False, description="Enable multi-tenant mode for organization isolation")
    TENANT_HEADER: str = Field("X-Tenant-ID", description="Header name for tenant ID in requests")

    # Sentry Configuration
    SENTRY_DSN: str | None = Field(
        default="https://d44f9586fda96f0cb06a8e8bda42a3bb@o4509520816963584.ingest.us.sentry.io/4509520843243520",
        description="Sentry DSN for error tracking",
    )

    # External Service - DUX ERP Integration
    DUX_API_BASE_URL: str = Field("https://erp.duxsoftware.com.ar/WSERP/rest/services", description="URL base de Dux")
    DUX_API_KEY: str | None = Field(None, description="Clave de la aplicación de Dux")
    DUX_API_TIMEOUT: int = Field(30, description="Timeout para requests a la API de Dux en segundos")
    DUX_API_RATE_LIMIT_SECONDS: int = Field(5, description="Límite de rate limiting para la API de Dux")
    DUX_SYNC_BATCH_SIZE: int = Field(50, description="Tamaño del lote para sincronización de productos DUX")

    # DUX Synchronization Configuration (controls both background sync and ProductAgent)
    # When disabled: background sync does NOT start and ProductAgent is automatically excluded
    DUX_SYNC_ENABLED: bool = Field(False, description="Habilitar integración DUX (sync + ProductAgent)")
    # NoDecode prevents pydantic-settings from trying json.loads() - we parse manually
    DUX_SYNC_HOURS: Annotated[list[int], NoDecode] = Field(
        default=[2, 14],
        description="Horas del día para sincronización automática (0-23)",
    )
    DUX_FORCE_SYNC_THRESHOLD_HOURS: int = Field(24, description="Forzar sync si datos > X horas antiguos")

    # External Service - Plex ERP Integration (Pharmacy)
    # Connection: Local network, requires VPN
    # Auth: HTTP Basic Auth
    PLEX_API_BASE_URL: str = Field(
        "http://192.168.100.10:8081/wsplex", description="Base URL for Plex ERP API (local network, requires VPN)"
    )
    PLEX_API_USER: str = Field("fciacuyo", description="HTTP Basic Auth username for Plex API")
    PLEX_API_PASS: str = Field("cuyo202$", description="HTTP Basic Auth password for Plex API")
    PLEX_API_TIMEOUT: int = Field(30, description="Timeout for Plex API requests in seconds")

    # Receipt Generation Settings
    # Note: Mercado Pago and pharmacy info are now stored per-organization in the database
    # See: PharmacyMerchantConfig table and PharmacyConfigService
    RECEIPT_STORAGE_PATH: str = Field("app/static/receipts", description="Directory path for storing PDF receipts")
    RECEIPT_CLEANUP_DAYS: int = Field(30, description="Number of days to keep receipts before cleanup")

    # WhatsApp Template Settings for Payment Notifications
    WA_PAYMENT_RECEIPT_TEMPLATE: str = Field(
        "payment_receipt", description="WhatsApp template name for payment receipts"
    )
    WA_PAYMENT_RECEIPT_LANGUAGE: str = Field("es", description="Language code for payment receipt template")

    # ProductAgent Configuration (always uses PostgreSQL only)
    PRODUCT_AGENT_DATA_SOURCE: str = Field("database", description="ProductAgent siempre usa 'database' (PostgreSQL)")

    # Agent Enablement Configuration
    # NOTE: Agents are now managed via database (core.agents table)
    # Use the Admin API: /api/v1/admin/agents for CRUD operations
    # The old ENABLED_AGENTS env var has been removed - run migration to seed agents

    # LangSmith Configuration
    LANGSMITH_TRACING: bool = Field(False, description="Enable LangSmith tracing")
    LANGSMITH_ENDPOINT: str = Field("https://api.smith.langchain.com", description="LangSmith API endpoint")
    LANGSMITH_API_KEY: str | None = Field(None, description="LangSmith API key")
    LANGSMITH_PROJECT: str = Field("aynux-production", description="LangSmith project name")
    LANGSMITH_VERBOSE: bool = Field(False, description="Enable verbose LangSmith logging")
    LANGSMITH_SAMPLE_RATE: float = Field(1.0, description="Trace sampling rate (0.0-1.0)")
    LANGSMITH_AUTO_EVAL: bool = Field(False, description="Enable automatic evaluation of traces")
    LANGSMITH_METRICS_ENABLED: bool = Field(True, description="Enable metrics collection")
    LANGSMITH_DATASET_NAME: str = Field("aynux-evals", description="Dataset name for evaluations")

    # Credential Encryption (pgcrypto)
    CREDENTIAL_ENCRYPTION_KEY: str | None = Field(
        None,
        description="32-byte key for encrypting credentials at rest (generate with secrets.token_urlsafe(32))",
    )

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignorar campos extras en lugar de generar un error
    )

    def __init__(self, **data: Any):
        super().__init__(**data)


    @field_validator("PRODUCT_AGENT_DATA_SOURCE")
    @classmethod
    def validate_data_source(cls, v):
        if v != "database":
            raise ValueError("PRODUCT_AGENT_DATA_SOURCE must be 'database' (always uses PostgreSQL)")
        return v

    # Validators for NoDecode fields - parse from string (env var) to list
    # mode='before' runs before pydantic-settings tries any parsing

    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_allowed_extensions(cls, v: Any) -> list[str]:
        """Parse ALLOWED_EXTENSIONS from JSON array or comma-separated string."""
        return parse_str_list(v)

    @field_validator("DUX_SYNC_HOURS", mode="before")
    @classmethod
    def parse_dux_sync_hours(cls, v: Any) -> list[int]:
        """Parse DUX_SYNC_HOURS from JSON array or comma-separated string."""
        hours = parse_int_list(v)
        for hour in hours:
            if not 0 <= hour <= 23:
                raise ValueError(f"DUX sync hour {hour} must be between 0 and 23")
        return hours

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
    def external_llm_base_url_resolved(self) -> str:
        """
        Resuelve la base URL para el LLM externo.

        Si EXTERNAL_LLM_BASE_URL está configurado, lo usa directamente.
        Si no, detecta automáticamente según el provider:
        - deepseek: https://api.deepseek.com/v1
        - kimi: https://api.moonshot.ai/v1
        - openai: https://api.openai.com/v1
        """
        if self.EXTERNAL_LLM_BASE_URL:
            return self.EXTERNAL_LLM_BASE_URL
        provider_urls = {
            "deepseek": "https://api.deepseek.com/v1",
            "kimi": "https://api.moonshot.ai/v1",
            "openai": "https://api.openai.com/v1",
        }
        return provider_urls.get(self.EXTERNAL_LLM_PROVIDER, "https://api.deepseek.com/v1")

    @computed_field
    @property
    def database_config(self) -> dict:
        """Configuración optimizada para la base de datos según el entorno.

        Note: No especificamos poolclass para async engines - SQLAlchemy
        automáticamente usa AsyncAdaptedQueuePool para producción.
        """
        base_config = {
            "echo": self.DB_ECHO,
            "future": True,
            "pool_pre_ping": True,
        }

        if self.is_development:
            # Desarrollo: sin pool (NullPool se importa donde se use)
            return base_config
        else:
            # Producción: pool completo (SQLAlchemy elige AsyncAdaptedQueuePool)
            return {
                **base_config,
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
