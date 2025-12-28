"""
Pharmacy Intent Result

Data model for pharmacy intent analysis results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PharmacyIntentResult:
    """Result of pharmacy intent analysis."""

    intent: str
    confidence: float
    is_out_of_scope: bool = False
    suggested_response: str | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    method: str = "hybrid"
    analysis: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PharmacyIntentResult:
        """Create instance from dictionary."""
        return cls(
            intent=data.get("intent", "unknown"),
            confidence=float(data.get("confidence", 0.0)),
            is_out_of_scope=bool(data.get("is_out_of_scope", False)),
            suggested_response=data.get("suggested_response"),
            entities=data.get("entities", {}),
            method=data.get("method", "hybrid"),
            analysis=data.get("analysis", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "is_out_of_scope": self.is_out_of_scope,
            "suggested_response": self.suggested_response,
            "entities": self.entities,
            "method": self.method,
            "analysis": self.analysis,
        }
