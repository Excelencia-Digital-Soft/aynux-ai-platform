"""
Configuración específica para el sistema LangGraph multi-agente
"""

import os
from typing import Any, Dict

from pydantic import BaseModel, Field

from app.core.tenancy.agent_factory import TenantAgentFactory

from .agents import (
    AgentConfig,
    IntegrationConfig,
    InvoiceAgentConfig,
    MonitoringConfig,
    ProductAgentConfig,
    PromotionsAgentConfig,
    RouterConfig,
    SecurityConfig,
    SupervisorConfig,
    SupportAgentConfig,
    TrackingAgentConfig,
)


class LangGraphConfig(BaseModel):
    """Configuración principal del sistema LangGraph"""

    # Configuraciones de agentes
    agents: Dict[str, AgentConfig] = Field(
        default_factory=lambda: {
            "product": ProductAgentConfig(),
            "promotions": PromotionsAgentConfig(),
            "tracking": TrackingAgentConfig(),
            "support": SupportAgentConfig(),
            "invoice": InvoiceAgentConfig(),
        }
    )

    # Configuraciones del sistema
    router: RouterConfig = Field(default_factory=RouterConfig)
    supervisor: SupervisorConfig = Field(default_factory=SupervisorConfig)
    integrations: IntegrationConfig = Field(default_factory=IntegrationConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

    # Configuraciones generales
    environment: str = Field(default="development")
    debug_mode: bool = Field(default=False)
    use_checkpointing: bool = Field(default=True)
    max_conversation_length: int = Field(default=50)

    # Agent enablement configuration
    # Note: product_agent, tracking_agent, promotions_agent, invoice_agent are now
    # internal nodes of ecommerce_agent subgraph - they should NOT be listed here
    enabled_agents: list[str] = Field(
        default_factory=lambda: [
            # Always available (domain_key=None)
            "greeting_agent",
            "support_agent",
            "fallback_agent",
            "farewell_agent",
            # E-commerce domain - DISABLED by default
            # "ecommerce_agent",
            # Excelencia domain
            "excelencia_agent",
            "excelencia_invoice_agent",
            "excelencia_promotions_agent",
            "data_insights_agent",
        ],
        description="List of enabled top-level agent names. Orchestrator and Supervisor always enabled.",
    )

    @classmethod
    def from_env(cls) -> "LangGraphConfig":
        """Crea configuración desde variables de entorno"""
        return cls(
            environment=os.getenv("ENVIRONMENT", "development"),
            debug_mode=os.getenv("DEBUG", "false").lower() == "true",
            use_checkpointing=os.getenv("USE_CHECKPOINTING", "true").lower() == "true",
            # Get enabled agents from database cache (core.agents table)
            # Falls back to hardcoded defaults if cache is empty
            enabled_agents=TenantAgentFactory().global_enabled_agents or [
                "greeting_agent",
                "support_agent",
                "fallback_agent",
                "farewell_agent",
                "excelencia_agent",
                "excelencia_invoice_agent",
                "excelencia_promotions_agent",
                "data_insights_agent",
            ],
            integrations=IntegrationConfig(
                ollama_url=os.getenv("OLLAMA_API_URL", "http://localhost:11434"),
                ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
                postgres_pool_size=int(os.getenv("POSTGRES_POOL_SIZE", "5")),
                redis_ttl=int(os.getenv("REDIS_TTL", "86400")),
            ),
            security=SecurityConfig(
                rate_limit_messages=int(os.getenv("RATE_LIMIT_MESSAGES", "20")),
                rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
                max_message_length=int(os.getenv("MAX_MESSAGE_LENGTH", "1000")),
            ),
        )

    def update_config(self, updates: Dict[str, Any]):
        """Actualiza configuración dinámicamente"""
        for key, value in updates.items():
            if hasattr(self, key):
                if isinstance(getattr(self, key), BaseModel):
                    # Para modelos anidados, actualizar campos específicos
                    current_config = getattr(self, key)
                    for sub_key, sub_value in value.items():
                        if hasattr(current_config, sub_key):
                            setattr(current_config, sub_key, sub_value)
                else:
                    setattr(self, key, value)


def get_langgraph_config() -> LangGraphConfig:
    """
    Obtiene la configuración de LangGraph.

    Returns:
        Configuración completa del sistema
    """
    return LangGraphConfig.from_env()
