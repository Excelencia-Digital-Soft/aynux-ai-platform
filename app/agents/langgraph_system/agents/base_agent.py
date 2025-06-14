"""
Agente base para todos los agentes especializados
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..models import AgentResponse

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

    async def _use_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """Usa una herramienta y registra su uso"""
        tool = self._get_tool_by_name(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")

        self.logger.debug(f"Using tool: {tool_name}")
        result = await tool(*args, **kwargs)

        return result

    def _get_tool_by_name(self, name: str) -> Any:
        """Obtiene una herramienta por nombre"""
        for tool in self.tools:
            if hasattr(tool, "__name__") and tool.__name__ == name:
                return tool
            if hasattr(tool, "name") and tool.name == name:
                return tool
        return None
