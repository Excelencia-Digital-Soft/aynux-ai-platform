"""
LLM Response Analyzer.

Uses COMPLEX model tier (gemma2) to evaluate agent responses with semantic understanding.
Provides analysis of completeness, accuracy, hallucinations, and helpfulness.

This component complements the heuristic-based ResponseQualityEvaluator by adding
LLM-powered semantic analysis for cases where heuristics are insufficient.

Performance optimizations:
- Uses COMPLEX tier instead of REASONING for faster response (~10s vs ~100s)
- Enforces timeout with asyncio.wait_for() to prevent hanging
- Skip LLM analysis when heuristic score >= 0.90
"""

import asyncio
import json
import logging
import re
from typing import Any

from app.core.graph.agents.supervisor.schemas.analyzer_schemas import (
    AnalyzerFallbackResult,
    CompletenessAnalysis,
    HallucinationAnalysis,
    HallucinationRisk,
    LLMResponseAnalysis,
    QuestionAnswerAlignment,
    RecommendedAction,
    ResponseQuality,
)
from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class LLMResponseAnalyzer:
    """
    Analyzes agent responses using COMPLEX model tier (gemma2).

    Responsibilities:
    - Semantic evaluation of response completeness
    - Question-answer alignment verification
    - Hallucination detection (prioritized feature)
    - Context relevance assessment
    - Action recommendation (accept, reroute, escalate)

    Uses COMPLEX model tier (gemma2) for fast analysis (~10-15s).
    Falls back to heuristic scores on LLM failure or timeout.

    Configuration:
    - enable_llm_analysis: Enable/disable LLM analysis (default: True)
    - llm_timeout: Timeout in seconds for LLM calls (default: 15)
    - skip_llm_threshold: Skip LLM if heuristic score >= this value (default: 0.90)
    """

    DEFAULT_TIMEOUT_SECONDS = 60
    SKIP_LLM_THRESHOLD = 0.75

    def __init__(
        self,
        ollama=None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the LLM Response Analyzer.

        Args:
            ollama: Ollama LLM instance (OllamaLLM class from integrations)
            config: Configuration dictionary with optional keys:
                - enable_llm_analysis: bool (default: True)
                - llm_timeout: int (default: 15)
                - skip_llm_threshold: float (default: 0.90)
        """
        self.ollama = ollama
        self.config = config or {}
        self.prompt_manager = PromptManager()

        # Configuration
        self.enabled = self.config.get("enable_llm_analysis", True)
        self.timeout = self.config.get("llm_timeout", self.DEFAULT_TIMEOUT_SECONDS)
        self.skip_threshold = self.config.get("skip_llm_threshold", self.SKIP_LLM_THRESHOLD)

        logger.info(
            f"LLMResponseAnalyzer initialized (enabled={self.enabled}, "
            f"timeout={self.timeout}s, threshold={self.skip_threshold})"
        )

    async def analyze(
        self,
        user_message: str,
        agent_response: str,
        agent_name: str,
        conversation_context: dict[str, Any],
        heuristic_score: float | None = None,
    ) -> LLMResponseAnalysis | AnalyzerFallbackResult:
        """
        Analyze agent response using reasoning LLM.

        Args:
            user_message: User's original question
            agent_response: Agent's response to evaluate
            agent_name: Name of the agent that responded
            conversation_context: Full conversation context including:
                - messages: Conversation history
                - rag_context: Retrieved RAG context (if any)
                - rag_metrics: RAG retrieval metrics
            heuristic_score: Optional pre-computed heuristic score from
                ResponseQualityEvaluator

        Returns:
            LLMResponseAnalysis with detailed evaluation, or
            AnalyzerFallbackResult if LLM unavailable/fails
        """
        # Guard: Check if analyzer is enabled
        if not self.enabled:
            logger.debug("LLM analysis disabled in config")
            return AnalyzerFallbackResult(
                reason="LLM analysis disabled in config",
                heuristic_score=heuristic_score or 0.5,
            )

        # Guard: Check if LLM instance available
        if not self.ollama:
            logger.warning("No LLM instance available for analysis")
            return AnalyzerFallbackResult(
                reason="No LLM instance available",
                heuristic_score=heuristic_score or 0.5,
            )

        # Optimization: Skip LLM if heuristic score is very high
        if heuristic_score is not None and heuristic_score >= self.skip_threshold:
            logger.info(
                f"[SKIP_LLM] Skipping LLM analysis - score={heuristic_score:.2f} >= threshold={self.skip_threshold}"
            )
            return self._create_high_quality_result(heuristic_score)

        # Log when NOT skipping for debugging
        logger.info(
            f"[LLM_CALL] Proceeding with LLM analysis - heuristic={heuristic_score}, threshold={self.skip_threshold}"
        )

        try:
            # Build analysis prompt
            prompt = await self._build_analysis_prompt(
                user_message=user_message,
                agent_response=agent_response,
                agent_name=agent_name,
                conversation_context=conversation_context,
            )

            # Call COMPLEX LLM (gemma2) - faster than REASONING
            logger.info("Calling COMPLEX LLM for response analysis...")
            llm = self.ollama.get_llm(
                complexity=ModelComplexity.COMPLEX,
                temperature=0.1,  # Low temperature for consistent analysis
            )

            # Enforce timeout to prevent hanging on slow LLM responses
            try:
                response = await asyncio.wait_for(
                    llm.ainvoke(prompt),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"LLM analysis timeout after {self.timeout}s")
                return AnalyzerFallbackResult(
                    reason=f"LLM timeout after {self.timeout}s",
                    heuristic_score=heuristic_score or 0.5,
                )

            raw_response = response.content if response else ""

            # Clean any <think> tags if present (defensive, COMPLEX shouldn't have them)
            raw_response = self._clean_think_tags(raw_response)

            # Parse structured output
            analysis = self._parse_response(raw_response)

            logger.info(
                f"LLM analysis complete: quality={analysis.quality.value}, "
                f"score={analysis.overall_score:.2f}, "
                f"action={analysis.recommended_action.value}, "
                f"hallucination_risk={analysis.hallucination.risk_level.value}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error in LLM response analysis: {e}")
            return AnalyzerFallbackResult(
                reason=f"LLM analysis failed: {str(e)}",
                heuristic_score=heuristic_score or 0.5,
            )

    async def _build_analysis_prompt(
        self,
        user_message: str,
        agent_response: str,
        agent_name: str,
        conversation_context: dict[str, Any],
    ) -> str:
        """Build the analysis prompt for the reasoning LLM."""
        # Extract conversation summary
        messages = conversation_context.get("messages", [])
        conversation_summary = self._build_conversation_summary(messages)

        # Extract RAG context if available
        rag_context = conversation_context.get("rag_context", "")
        rag_metrics = conversation_context.get("rag_metrics", {})
        rag_had_results = rag_metrics.get("has_results", False) if rag_metrics else False

        return await self.prompt_manager.get_prompt(
            PromptRegistry.AGENTS_SUPERVISOR_ANALYSIS,
            variables={
                "user_message": user_message,
                "agent_response": agent_response,
                "agent_name": agent_name,
                "conversation_summary": conversation_summary,
                "rag_context": rag_context[:1000] if rag_context else "No RAG context available",
                "rag_had_results": str(rag_had_results),
            },
        )

    def _build_conversation_summary(self, messages: list[dict[str, Any]]) -> str:
        """Build summary of recent conversation for context."""
        if not messages or len(messages) <= 2:
            return "This is the beginning of the conversation."

        # Take last 6 messages for context (excluding the response being evaluated)
        recent = messages[-6:] if len(messages) > 6 else messages
        summary_parts = []

        for msg in recent[:-1]:  # Exclude the response being evaluated
            role = msg.get("role", "unknown") if isinstance(msg, dict) else getattr(msg, "role", "unknown")
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if role and content:
                # Truncate long messages
                content = content[:150] + "..." if len(content) > 150 else content
                summary_parts.append(f"{role}: {content}")

        return "\n".join(summary_parts) if summary_parts else "No prior conversation."

    def _clean_think_tags(self, response: str | None) -> str:
        """Remove deepseek-r1 <think> tags from response.

        Args:
            response: Raw response string (may be None)

        Returns:
            Cleaned string with <think> tags removed, or empty string if None
        """
        if not response:
            return ""  # Return empty string instead of None to prevent downstream errors
        # Remove <think>...</think> blocks (reasoning traces)
        cleaned = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
        return cleaned.strip()

    def _parse_response(self, raw_response: str) -> LLMResponseAnalysis:
        """Parse LLM response into structured analysis."""
        # Try to extract JSON from response
        try:
            # Look for JSON block in response
            json_match = re.search(r"\{[\s\S]*\}", raw_response)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return self._validate_and_create_analysis(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse JSON response: {e}")

        # Fallback: Parse text response heuristically
        return self._parse_text_response(raw_response)

    def _validate_and_create_analysis(self, data: dict[str, Any]) -> LLMResponseAnalysis:
        """Validate parsed JSON and create LLMResponseAnalysis.

        Supports both the simplified prompt format (v2.0) and legacy nested format.
        """
        # Map string values to enums
        quality_str = data.get("quality", "good").lower()
        quality_map = {
            "excellent": ResponseQuality.EXCELLENT,
            "good": ResponseQuality.GOOD,
            "partial": ResponseQuality.PARTIAL,
            "insufficient": ResponseQuality.INSUFFICIENT,
            "fallback": ResponseQuality.FALLBACK,
        }
        quality = quality_map.get(quality_str, ResponseQuality.GOOD)

        action_str = data.get("recommended_action", "accept").lower()
        action_map = {
            "accept": RecommendedAction.ACCEPT,
            "enhance": RecommendedAction.ENHANCE,
            "reroute": RecommendedAction.REROUTE,
            "re_route": RecommendedAction.REROUTE,
            "clarify": RecommendedAction.CLARIFY,
            "escalate": RecommendedAction.ESCALATE,
        }
        action = action_map.get(action_str, RecommendedAction.ACCEPT)

        overall_score = float(data.get("overall_score", 0.7))

        # Support both simplified format (v2.0) and legacy nested format
        # Simplified format has answers_question and hallucination_risk at top level
        # Legacy format has nested question_answer_alignment and hallucination objects
        qa_data = data.get("question_answer_alignment", {})
        hallucination_data = data.get("hallucination", {})
        completeness_data = data.get("completeness", {})

        # Parse answers_question (simplified or nested)
        answers_question = data.get("answers_question")
        if answers_question is None:
            answers_question = qa_data.get("answers_question", True)

        # Parse hallucination risk (simplified or nested)
        risk_str = data.get("hallucination_risk")
        if risk_str is None:
            risk_str = hallucination_data.get("risk_level", "none")
        risk_str = str(risk_str).lower()

        risk_map = {
            "none": HallucinationRisk.NONE,
            "low": HallucinationRisk.LOW,
            "medium": HallucinationRisk.MEDIUM,
            "high": HallucinationRisk.HIGH,
        }
        hallucination_risk = risk_map.get(risk_str, HallucinationRisk.NONE)

        return LLMResponseAnalysis(
            quality=quality,
            overall_score=overall_score,
            recommended_action=action,
            question_answer_alignment=QuestionAnswerAlignment(
                answers_question=bool(answers_question),
                alignment_score=float(qa_data.get("alignment_score", overall_score)),
                missing_aspects=qa_data.get("missing_aspects", []),
                extra_information=qa_data.get("extra_information", False),
            ),
            completeness=CompletenessAnalysis(
                is_complete=completeness_data.get("is_complete", overall_score >= 0.7),
                completeness_score=float(completeness_data.get("completeness_score", overall_score)),
                missing_information=completeness_data.get("missing_information", []),
                has_specific_data=completeness_data.get("has_specific_data", True),
            ),
            hallucination=HallucinationAnalysis(
                risk_level=hallucination_risk,
                suspicious_claims=hallucination_data.get("suspicious_claims", []),
                grounded_claims=hallucination_data.get("grounded_claims", []),
                confidence=float(hallucination_data.get("confidence", 0.8)),
            ),
            uses_conversation_context=data.get("uses_conversation_context", True),
            appropriate_for_agent=data.get("appropriate_for_agent", True),
            reasoning=data.get("reasoning", "Analysis completed"),
            confidence=float(data.get("confidence", 0.8)),
        )

    def _parse_text_response(self, text: str) -> LLMResponseAnalysis:
        """Parse unstructured text response into analysis (fallback).

        Note: Keyword priority matters! We check negative/lower quality patterns FIRST
        to avoid substring issues like:
        - "incomplete" containing "complete" → would incorrectly match EXCELLENT
        - "inadequate" containing "good" → would incorrectly match GOOD
        """
        text_lower = text.lower() if text else ""

        # Determine quality from text keywords
        # IMPORTANT: Check negative patterns FIRST to avoid substring matching issues
        if any(w in text_lower for w in ["insufficient", "poor", "fails", "inadequate"]):
            quality = ResponseQuality.INSUFFICIENT
            score = 0.3
        elif any(w in text_lower for w in ["partial", "incomplete", "missing"]):
            quality = ResponseQuality.PARTIAL
            score = 0.5
        elif any(w in text_lower for w in ["good", "mostly", "adequate", "satisfactory"]):
            quality = ResponseQuality.GOOD
            score = 0.75
        elif any(w in text_lower for w in ["excellent", "complete", "fully answers", "perfect"]):
            quality = ResponseQuality.EXCELLENT
            score = 0.9
        else:
            quality = ResponseQuality.PARTIAL
            score = 0.6

        # Determine action from text
        if any(w in text_lower for w in ["reroute", "different agent", "re-route", "wrong agent"]):
            action = RecommendedAction.REROUTE
        elif any(w in text_lower for w in ["escalate", "human", "handoff", "supervisor"]):
            action = RecommendedAction.ESCALATE
        elif any(w in text_lower for w in ["enhance", "improve", "polish", "refine"]):
            action = RecommendedAction.ENHANCE
        elif any(w in text_lower for w in ["clarify", "unclear", "ambiguous", "vague"]):
            action = RecommendedAction.CLARIFY
        else:
            action = RecommendedAction.ACCEPT if score >= 0.7 else RecommendedAction.ENHANCE

        # Determine hallucination risk from text
        hallucination_risk = HallucinationRisk.NONE
        if any(w in text_lower for w in ["hallucination", "invented", "fabricated", "made up"]):
            if any(w in text_lower for w in ["high", "significant", "severe"]):
                hallucination_risk = HallucinationRisk.HIGH
            elif any(w in text_lower for w in ["medium", "moderate", "some"]):
                hallucination_risk = HallucinationRisk.MEDIUM
            else:
                hallucination_risk = HallucinationRisk.LOW

        return LLMResponseAnalysis(
            quality=quality,
            overall_score=score,
            recommended_action=action,
            question_answer_alignment=QuestionAnswerAlignment(
                answers_question=score >= 0.6,
                alignment_score=score,
            ),
            completeness=CompletenessAnalysis(
                is_complete=score >= 0.7,
                completeness_score=score,
                has_specific_data=True,
            ),
            hallucination=HallucinationAnalysis(
                risk_level=hallucination_risk,
                confidence=0.5,  # Lower confidence for text parsing
            ),
            uses_conversation_context=True,
            appropriate_for_agent=True,
            reasoning=text[:300] if text else "Analysis completed via text parsing",
            confidence=0.6,  # Lower confidence for text parsing
        )

    def _create_high_quality_result(self, score: float) -> LLMResponseAnalysis:
        """Create analysis result for high-quality responses that skip LLM."""
        return LLMResponseAnalysis(
            quality=ResponseQuality.EXCELLENT,
            overall_score=score,
            recommended_action=RecommendedAction.ACCEPT,
            question_answer_alignment=QuestionAnswerAlignment(
                answers_question=True,
                alignment_score=score,
            ),
            completeness=CompletenessAnalysis(
                is_complete=True,
                completeness_score=score,
                has_specific_data=True,
            ),
            hallucination=HallucinationAnalysis(
                risk_level=HallucinationRisk.NONE,
                confidence=0.9,
            ),
            uses_conversation_context=True,
            appropriate_for_agent=True,
            reasoning="High heuristic score, LLM analysis skipped for efficiency",
            confidence=0.9,
        )
