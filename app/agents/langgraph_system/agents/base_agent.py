"""
Agente base para todos los agentes especializados
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List

from app.agents.langgraph_system.models import AgentResponse, SharedState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Clase base para todos los agentes especializados"""
    
    def __init__(self, name: str, tools: List[Any] = None):
        self.name = name
        self.tools = tools or []
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    async def process(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa el estado y genera una respuesta"""
        start_time = datetime.now()
        
        try:
            # Log inicio de procesamiento
            self.logger.info(f"Processing request in {self.name}")
            
            # Validar estado
            if not self._validate_state_dict(state_dict):
                raise ValueError("Invalid state for processing")
            
            # Procesar con el agente específico
            response = await self._process_internal(state_dict)
            
            # Crear respuesta del agente
            agent_response = {
                "agent_name": self.name,
                "response_text": response.get("text", ""),
                "data_retrieved": response.get("data", {}),
                "tools_used": response.get("tools_used", []),
                "success": True,
                "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "created_at": datetime.now().isoformat()
            }
            
            # Añadir respuesta al estado
            if "agent_responses" not in state_dict:
                state_dict["agent_responses"] = []
            state_dict["agent_responses"].append(agent_response)
            
            # Actualizar tiempo total de procesamiento
            processing_time = agent_response["processing_time_ms"]
            current_total = state_dict.get("total_processing_time_ms", 0)
            state_dict["total_processing_time_ms"] = current_total + processing_time
            
            # Log éxito
            self.logger.info(
                f"Successfully processed in {processing_time:.2f}ms"
            )
            
            return state_dict
            
        except Exception as e:
            # Log error
            self.logger.error(f"Error processing in {self.name}: {str(e)}")
            
            # Incrementar contador de errores
            error_count = state_dict.get("error_count", 0) + 1
            state_dict["error_count"] = error_count
            
            # Crear respuesta de error
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            agent_response = {
                "agent_name": self.name,
                "response_text": self._get_error_message(),
                "success": False,
                "error": str(e),
                "processing_time_ms": processing_time,
                "created_at": datetime.now().isoformat()
            }
            
            # Añadir respuesta de error al estado
            if "agent_responses" not in state_dict:
                state_dict["agent_responses"] = []
            state_dict["agent_responses"].append(agent_response)
            
            return state_dict
    
    @abstractmethod
    async def _process_internal(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Implementación interna del procesamiento del agente"""
        pass
    
    def _validate_state_dict(self, state_dict: Dict[str, Any]) -> bool:
        """Valida que el estado sea válido para procesamiento"""
        if not state_dict.get("customer"):
            self.logger.error("No customer context in state")
            return False
        
        if not state_dict.get("messages"):
            self.logger.error("No messages in state")
            return False
        
        return True
    
    def _get_error_message(self) -> str:
        """Obtiene mensaje de error genérico para el usuario"""
        return (
            "Disculpa, tuve un problema procesando tu solicitud. "
            "¿Podrías reformular tu pregunta o intentar de nuevo?"
        )
    
    def _format_price(self, price: float) -> str:
        """Formatea un precio para mostrar"""
        return f"${price:,.2f}"
    
    def _truncate_text(self, text: str, max_length: int = 100) -> str:
        """Trunca texto largo"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
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
            if hasattr(tool, '__name__') and tool.__name__ == name:
                return tool
            if hasattr(tool, 'name') and tool.name == name:
                return tool
        return None