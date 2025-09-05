from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IntentInfo(BaseModel):
    """Información de intención detectada"""

    primary_intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    requires_handoff: bool = False
    target_agent: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.now)

    def is_confident(self, threshold: float = 0.7) -> bool:
        """Verifica si la detección tiene confianza suficiente"""
        return self.confidence >= threshold

    def get_entity(self, key: str, default: Any = None) -> Any:
        """Obtiene una entidad extraída"""
        return self.entities.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para compatibilidad con TypedDict"""
        return {
            "primary_intent": self.primary_intent,
            "confidence": self.confidence,
            "entities": self.entities,
            "requires_handoff": self.requires_handoff,
            "target_agent": self.target_agent,
            "detected_at": self.detected_at.isoformat(),
        }


class IntentPattern(BaseModel):
    """Patrón para detección de intenciones"""

    intent: str
    keywords: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)
    confidence_boost: float = 0.0

    def matches(self, text: str) -> bool:
        """Verifica si el patrón coincide con el texto"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.keywords)
