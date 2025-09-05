"""
Agente base para todos los agentes especializados
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.config.langsmith_config import get_tracer

from ..schemas import AgentResponse
from ..utils.tracing import AgentTracer, trace_async_method

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Clase base para todos los agentes especializados"""

    def __init__(self, name: str, config: Dict[str, Any], **integrations):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{name}")

        # Integraciones (Ollama, PostgreSQL, ChromaDB, etc.)
        self.integrations = integrations
        self.tools = []

        # Métricas del agente
        self.metrics = {"total_requests": 0, "successful_requests": 0, "average_response_time": 0.0}

        # Initialize LangSmith tracing
        self.tracer = get_tracer()
        self.agent_tracer = AgentTracer(name, "specialized_agent")

    @abstractmethod
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa un mensaje internamente. Cada agente debe implementar esto.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        pass

    def get_traced_process_method(self):
        """Returns the process method decorated with tracing."""
        return self.agent_tracer.trace_process()(self._process_internal)

    def _create_response(
        self,
        response_text: str,
        success: bool = True,
        data_retrieved: Optional[Dict[str, Any]] = None,
        tools_used: Optional[List[str]] = None,
        error: Optional[str] = None,
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

    def _validate_input(self, message: str, state_dict: Dict[str, Any]) -> bool:
        """Valida la entrada del agente."""
        if not message or not message.strip():
            self.logger.warning("Empty message received", state_dict)
            return False
        return True

    def _update_metrics(self, success: bool, response_time_ms: float):
        """Actualiza métricas del agente"""
        self.metrics["total_requests"] += 1
        if success:
            self.metrics["successful_requests"] += 1

        # Actualizar tiempo promedio de respuesta
        current_avg = self.metrics["average_response_time"]
        total_requests = self.metrics["total_requests"]
        new_avg = ((current_avg * (total_requests - 1)) + response_time_ms) / total_requests
        self.metrics["average_response_time"] = new_avg

    def _get_error_message(self) -> str:
        """Obtiene mensaje de error genérico para el usuario"""
        return (
            "Disculpa, tuve un problema procesando tu solicitud. ¿Podrías reformular tu pregunta o intentar de nuevo?"
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

    def _extract_user_id(self, state_dict: Dict[str, Any]) -> Optional[str]:
        """Extrae el ID del usuario del estado."""
        return state_dict.get("user_id") or state_dict.get("customer_id") or state_dict.get("phone_number")

    def get_agent_metrics(self) -> Dict[str, Any]:
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
