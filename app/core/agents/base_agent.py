# ============================================================================
# SCOPE: GLOBAL
# Description: Clase base abstracta para todos los agentes especializados.
#              Soporta modo dual: global (defaults) y multi-tenant (config de DB).
# Tenant-Aware: Yes - via apply_tenant_config() puede recibir config por tenant.
# ============================================================================
"""
Agente base para todos los agentes especializados

Supports dual-mode operation:
- Global mode (no tenant): Uses hardcoded Python defaults
- Multi-tenant mode (with token): Loads configuration from database

The apply_tenant_config() method allows runtime configuration updates
when processing requests in multi-tenant mode.
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.config.langsmith_config import get_tracer
from app.core.schemas import AgentResponse
from app.core.utils.tracing import AgentTracer, trace_async_method

if TYPE_CHECKING:
    from app.core.schemas.tenant_agent_config import AgentConfig

logger = logging.getLogger(__name__)


# Default agent configuration values (used in global mode)
DEFAULT_AGENT_CONFIG = {
    "model": "llama3.1",
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 30,
}


class BaseAgent(ABC):
    """
    Base class for all specialized agents.

    Supports dual-mode operation:
    - Global mode: Uses DEFAULT_AGENT_CONFIG values
    - Multi-tenant mode: Applies tenant-specific config via apply_tenant_config()

    Attributes:
        name: Agent identifier
        config: Current configuration (global defaults or tenant-specific)
        model: LLM model to use (can be overridden by tenant config)
        temperature: LLM temperature (can be overridden by tenant config)
        _tenant_config_applied: Flag indicating if tenant config was applied
    """

    def __init__(self, name: str, config: dict[str, Any], **integrations):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{name}")

        # Integraciones (Ollama, PostgreSQL, pgvector, etc.)
        self.integrations = integrations
        self.tools = []

        # Default LLM configuration (can be overridden by tenant config)
        self.model: str = config.get("model", DEFAULT_AGENT_CONFIG["model"])
        self.temperature: float = config.get("temperature", DEFAULT_AGENT_CONFIG["temperature"])
        self.max_tokens: int = config.get("max_tokens", DEFAULT_AGENT_CONFIG["max_tokens"])
        self.timeout: int = config.get("timeout", DEFAULT_AGENT_CONFIG["timeout"])

        # Track if tenant config has been applied
        self._tenant_config_applied: bool = False
        self._applied_config_keys: list[str] = []

        # Metricas del agente
        self.metrics = {"total_requests": 0, "successful_requests": 0, "average_response_time": 0.0}

        # Initialize LangSmith tracing
        self.tracer = get_tracer()
        self.agent_tracer = AgentTracer(name, "chain")

    @abstractmethod
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Procesa un mensaje internamente. Cada agente debe implementar esto.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        pass

    async def process(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Public interface for processing messages.

        Template Method pattern: wraps _process_internal with metrics and error handling.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            Dictionary with state updates
        """
        start_time = time.time()
        success = False

        try:
            if not self._validate_input(message, state_dict):
                return {
                    "messages": [{"role": "assistant", "content": self._get_error_message()}],
                    "error_count": state_dict.get("error_count", 0) + 1,
                }

            result = await self._process_internal(message, state_dict)
            success = True
            return result

        except Exception as e:
            self.logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                "messages": [{"role": "assistant", "content": self._get_error_message()}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "error": str(e),
            }

        finally:
            response_time_ms = (time.time() - start_time) * 1000
            self._update_metrics(success, response_time_ms)

    def get_traced_process_method(self):
        """Returns the process method decorated with tracing."""
        return self.agent_tracer.trace_process()(self._process_internal)

    def _create_response(
        self,
        response_text: str,
        success: bool = True,
        data_retrieved: dict[str, Any] | None = None,
        tools_used: list[str] | None = None,
        error: str | None = None,
    ) -> AgentResponse:
        """Crea una respuesta estructurada del agente."""
        return AgentResponse(
            agent_name=self.name,
            response_text=response_text,
            data_retrieved=data_retrieved or {},
            tools_used=tools_used or [],
            success=success,
            error=error,
        )

    def _validate_input(self, message: str, state_dict: dict[str, Any]) -> bool:
        """Valida la entrada del agente."""
        if not message or not message.strip():
            self.logger.warning("Empty message received", state_dict)
            return False
        return True

    def _update_metrics(self, success: bool, response_time_ms: float):
        """Actualiza metricas del agente"""
        self.metrics["total_requests"] += 1
        if success:
            self.metrics["successful_requests"] += 1

        # Actualizar tiempo promedio de respuesta
        current_avg = self.metrics["average_response_time"]
        total_requests = self.metrics["total_requests"]
        new_avg = ((current_avg * (total_requests - 1)) + response_time_ms) / total_requests
        self.metrics["average_response_time"] = new_avg

    def _get_error_message(self) -> str:
        """Obtiene mensaje de error generico para el usuario"""
        return (
            "Disculpa, tuve un problema procesando tu solicitud. "
            "Podrias reformular tu pregunta o intentar de nuevo?"
        )

    def _format_price(self, price: float) -> str:
        """Formatea un precio para mostrar"""
        return f"${price:,.2f}"

    def _truncate_text(self, text: str, max_length: int = 100) -> str:
        """Trunca texto largo"""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    @trace_async_method(name="use_tool", run_type="tool", metadata={"component": "base_agent"})
    async def _use_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """Usa una herramienta y registra su uso"""
        tool = self._get_tool_by_name(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")

        self.logger.debug(f"Using tool: {tool_name}")

        # Add tool metadata to trace
        start_time = time.time()

        try:
            result = await tool(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            self.logger.debug(f"Tool {tool_name} completed in {duration_ms:.2f}ms")
            return result
        except Exception as e:
            self.logger.error(f"Tool {tool_name} failed: {e}")
            raise

    def _get_tool_by_name(self, name: str) -> Any:
        """Obtiene una herramienta por nombre"""
        for tool in self.tools:
            if hasattr(tool, "__name__") and tool.__name__ == name:
                return tool
            if hasattr(tool, "name") and tool.name == name:
                return tool
        return None

    def _extract_user_id(self, state_dict: dict[str, Any]) -> str | None:
        """Extrae el ID del usuario del estado."""
        return state_dict.get("user_id") or state_dict.get("customer_id") or state_dict.get("phone_number")

    def get_agent_metrics(self) -> dict[str, Any]:
        """
        Get comprehensive agent metrics including tracing data.

        Returns:
            Dictionary with agent performance metrics
        """
        base_metrics = self.metrics.copy()
        tracing_metrics = self.agent_tracer.get_metrics()

        return {
            **base_metrics,
            "tracing_metrics": tracing_metrics,
            "agent_name": self.name,
            "config": {
                "tools_count": len(self.tools),
                "integrations": list(self.integrations.keys()),
            },
        }

    def get_current_timestamp(self) -> str:
        """
        Get current timestamp in ISO format.

        Returns:
            Current timestamp as ISO formatted string
        """
        return datetime.now(UTC).isoformat()

    # =========================================================================
    # Dual-Mode Configuration Methods (Global vs Multi-Tenant)
    # =========================================================================

    def apply_tenant_config(self, agent_config: "AgentConfig") -> None:
        """
        Apply tenant-specific configuration to this agent.

        Called when processing requests in multi-tenant mode. Updates agent
        configuration from database values, overriding global defaults.

        Args:
            agent_config: AgentConfig loaded from database for this tenant

        Example:
            >>> # In multi-tenant mode
            >>> agent = GreetingAgent(...)
            >>> tenant_config = registry.get_agent("greeting_agent")
            >>> agent.apply_tenant_config(tenant_config)
            >>> # Agent now uses tenant-specific model, temperature, etc.
        """
        if not agent_config:
            self.logger.debug(f"No tenant config provided for {self.name}, using defaults")
            return

        # Get the agent's custom config from database
        config = agent_config.config or {}
        applied_keys: list[str] = []

        # Apply LLM configuration overrides
        if "model" in config:
            self.model = config["model"]
            applied_keys.append("model")

        if "temperature" in config:
            self.temperature = float(config["temperature"])
            applied_keys.append("temperature")

        if "max_tokens" in config:
            self.max_tokens = int(config["max_tokens"])
            applied_keys.append("max_tokens")

        if "timeout" in config:
            self.timeout = int(config["timeout"])
            applied_keys.append("timeout")

        # Merge any additional config values
        for key, value in config.items():
            if key not in ("model", "temperature", "max_tokens", "timeout"):
                self.config[key] = value
                applied_keys.append(key)

        # Track that tenant config was applied
        self._tenant_config_applied = True
        self._applied_config_keys = applied_keys

        if applied_keys:
            self.logger.info(
                f"Applied tenant config to {self.name}: {applied_keys}"
            )
            self.logger.debug(
                f"Using model: {self.model}, temperature: {self.temperature}"
            )

    def reset_to_defaults(self) -> None:
        """
        Reset agent configuration to global defaults.

        Called when switching from multi-tenant mode back to global mode,
        or when cleaning up after a request.
        """
        self.model = self.config.get("model", DEFAULT_AGENT_CONFIG["model"])
        self.temperature = self.config.get("temperature", DEFAULT_AGENT_CONFIG["temperature"])
        self.max_tokens = self.config.get("max_tokens", DEFAULT_AGENT_CONFIG["max_tokens"])
        self.timeout = self.config.get("timeout", DEFAULT_AGENT_CONFIG["timeout"])

        self._tenant_config_applied = False
        self._applied_config_keys = []

        self.logger.debug(f"Reset {self.name} to default configuration")

    def is_tenant_config_applied(self) -> bool:
        """Check if tenant-specific configuration is currently applied."""
        return self._tenant_config_applied

    def get_applied_config_keys(self) -> list[str]:
        """Get list of configuration keys that were applied from tenant config."""
        return self._applied_config_keys.copy()

    def get_effective_config(self) -> dict[str, Any]:
        """
        Get the currently effective configuration.

        Returns:
            Dict with all effective configuration values (defaults + tenant overrides)
        """
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "tenant_config_applied": self._tenant_config_applied,
            "applied_keys": self._applied_config_keys,
            **{k: v for k, v in self.config.items() if k not in ("model", "temperature", "max_tokens", "timeout")},
        }
