"""
Schemas for LLM Response Analyzer structured output.

Uses Pydantic models for type-safe LLM responses with structured output.
These schemas define the expected format for LLM analysis of agent responses.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResponseQuality(str, Enum):
    """Quality classification for agent response."""

    EXCELLENT = "excellent"  # Score 0.9-1.0: Complete, accurate, helpful
    GOOD = "good"  # Score 0.7-0.9: Mostly complete, minor issues
    PARTIAL = "partial"  # Score 0.5-0.7: Some info missing or unclear
    INSUFFICIENT = "insufficient"  # Score 0.3-0.5: Major gaps or issues
    FALLBACK = "fallback"  # Score 0.0-0.3: Generic/unhelpful response


class RecommendedAction(str, Enum):
    """Recommended action based on analysis."""

    ACCEPT = "accept"  # Response is good enough, complete conversation
    ENHANCE = "enhance"  # Response needs polishing, use ResponseEnhancer
    REROUTE = "reroute"  # Try different agent
    CLARIFY = "clarify"  # Ask user for clarification
    ESCALATE = "escalate"  # Human handoff needed


class HallucinationRisk(str, Enum):
    """Risk level for hallucinated/invented information."""

    NONE = "none"  # No signs of hallucination
    LOW = "low"  # Minor unsupported claims
    MEDIUM = "medium"  # Some statements lack grounding
    HIGH = "high"  # Likely invented information


class QuestionAnswerAlignment(BaseModel):
    """Analysis of how well the response answers the user's question."""

    answers_question: bool = Field(
        default=True,
        description="Whether the response directly addresses what the user asked",
    )
    alignment_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Score 0-1 indicating how well the response aligns with the question",
    )
    missing_aspects: list[str] = Field(
        default_factory=list,
        description="Aspects of the question that weren't addressed",
    )
    extra_information: bool = Field(
        default=False,
        description="Whether response includes unrequested but helpful information",
    )


class CompletenessAnalysis(BaseModel):
    """Analysis of response completeness."""

    is_complete: bool = Field(
        default=True,
        description="Whether the response provides complete information",
    )
    completeness_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Score 0-1 indicating completeness level",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Specific information that should have been included",
    )
    has_specific_data: bool = Field(
        default=True,
        description="Whether response contains specific data (names, numbers, dates)",
    )


class HallucinationAnalysis(BaseModel):
    """Analysis of potential hallucinations or invented information."""

    risk_level: HallucinationRisk = Field(
        default=HallucinationRisk.NONE,
        description="Overall hallucination risk level",
    )
    suspicious_claims: list[str] = Field(
        default_factory=list,
        description="Statements that appear potentially invented",
    )
    grounded_claims: list[str] = Field(
        default_factory=list,
        description="Statements that appear well-grounded in context",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in hallucination assessment",
    )


class LLMResponseAnalysis(BaseModel):
    """Complete structured output from LLM Response Analyzer."""

    # Overall assessment
    quality: ResponseQuality = Field(
        default=ResponseQuality.GOOD,
        description="Overall quality classification",
    )
    overall_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Overall quality score combining all factors",
    )
    recommended_action: RecommendedAction = Field(
        default=RecommendedAction.ACCEPT,
        description="Recommended next action",
    )

    # Detailed analysis
    question_answer_alignment: QuestionAnswerAlignment = Field(
        default_factory=QuestionAnswerAlignment,
        description="Analysis of question-answer alignment",
    )
    completeness: CompletenessAnalysis = Field(
        default_factory=CompletenessAnalysis,
        description="Analysis of response completeness",
    )
    hallucination: HallucinationAnalysis = Field(
        default_factory=HallucinationAnalysis,
        description="Analysis of potential hallucinations",
    )

    # Context awareness
    uses_conversation_context: bool = Field(
        default=True,
        description="Whether response leverages previous conversation context",
    )
    appropriate_for_agent: bool = Field(
        default=True,
        description="Whether the agent that responded was appropriate for this query",
    )

    # Reasoning
    reasoning: str = Field(
        default="Analysis completed",
        description="Brief explanation of the analysis and recommendation",
    )

    # Metadata
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in overall analysis",
    )

    @property
    def needs_action(self) -> bool:
        """Check if response requires action beyond accepting."""
        return self.recommended_action != RecommendedAction.ACCEPT

    @property
    def is_acceptable(self) -> bool:
        """Check if response is acceptable quality."""
        return self.quality in (ResponseQuality.EXCELLENT, ResponseQuality.GOOD)

    @property
    def has_hallucination_concerns(self) -> bool:
        """Check if there are hallucination concerns."""
        return self.hallucination.risk_level in (
            HallucinationRisk.MEDIUM,
            HallucinationRisk.HIGH,
        )

    def to_evaluation_dict(self) -> dict[str, Any]:
        """Convert to dictionary format compatible with supervisor evaluation."""
        return {
            "llm_quality": self.quality.value,
            "llm_score": self.overall_score,
            "llm_recommended_action": self.recommended_action.value,
            "llm_reasoning": self.reasoning,
            "llm_confidence": self.confidence,
            "hallucination_risk": self.hallucination.risk_level.value,
            "question_answered": self.question_answer_alignment.answers_question,
            "is_complete": self.completeness.is_complete,
            "has_specific_data": self.completeness.has_specific_data,
            "appropriate_for_agent": self.appropriate_for_agent,
        }


class AnalyzerFallbackResult(BaseModel):
    """Fallback result when LLM analysis fails."""

    used_fallback: bool = Field(
        default=True,
        description="Indicates this is a fallback result",
    )
    reason: str = Field(
        description="Reason why LLM analysis failed or was skipped",
    )
    heuristic_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Score from heuristic evaluation",
    )
    recommended_action: RecommendedAction = Field(
        default=RecommendedAction.ACCEPT,
        description="Fallback recommended action",
    )

    def to_evaluation_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for supervisor evaluation."""
        return {
            "llm_analysis_status": "fallback",
            "llm_fallback_reason": self.reason,
            "heuristic_score": self.heuristic_score,
        }
