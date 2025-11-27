"""
Evaluation Models.

Shared models for the evaluators system.
"""

from typing import Any

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """Standard evaluation result structure."""

    score: float = Field(
        ..., description="Evaluation score (0.0 to 1.0)", ge=0.0, le=1.0
    )
    explanation: str = Field(
        ..., description="Human-readable explanation of the score"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional evaluation metadata"
    )
    category: str = Field(
        ..., description="Evaluation category (quality, accuracy, business, etc.)"
    )
