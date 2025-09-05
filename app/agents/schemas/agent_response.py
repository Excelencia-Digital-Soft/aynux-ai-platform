from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """Respuesta generada por un agente"""

    agent_name: str
    response_text: str
    data_retrieved: Dict[str, Any] = Field(default_factory=dict)
    tools_used: List[str] = Field(default_factory=list)
    processing_time_ms: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    def add_tool_used(self, tool_name: str):
        """Añade una herramienta usada"""
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)

    def set_processing_time(self, start_time: datetime):
        """Calcula y establece el tiempo de procesamiento"""
        self.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para compatibilidad con TypedDict"""
        return {
            "agent_name": self.agent_name,
            "response_text": self.response_text,
            "data_retrieved": self.data_retrieved,
            "tools_used": self.tools_used,
            "processing_time_ms": self.processing_time_ms,
            "success": self.success,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }
