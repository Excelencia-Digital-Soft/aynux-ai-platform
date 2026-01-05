"""
Supervisor Agent.

Main orchestrator that evaluates responses and manages conversation quality.
Uses extracted components for SRP compliance.

Components:
- ResponseQualityEvaluator: Fast heuristic-based evaluation
- LLMResponseAnalyzer: Deep semantic analysis with LLM (deepseek-r1)
- ConversationFlowController: Flow decision logic
- ResponseEnhancer: Optional response enhancement
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.agents import BaseAgent
from app.core.graph.agents.supervisor.conversation_flow_controller import (
    ConversationFlowController,
)
from app.core.graph.agents.supervisor.llm_response_analyzer import LLMResponseAnalyzer
from app.core.graph.agents.supervisor.response_enhancer import ResponseEnhancer
from app.core.graph.agents.supervisor.response_quality_evaluator import (
    ResponseQualityEvaluator,
)
from app.core.graph.agents.supervisor.schemas.analyzer_schemas import (
    AnalyzerFallbackResult,
    LLMResponseAnalysis,
    RecommendedAction,
)
from app.core.utils.tracing import trace_async_method
from app.utils.language_detector import LanguageDetector

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that evaluates response quality and manages conversation flow.

    This agent orchestrates the evaluation process using extracted components:
    - ResponseQualityEvaluator: Fast heuristic-based evaluation
    - LLMResponseAnalyzer: Deep semantic analysis with LLM (deepseek-r1)
    - ConversationFlowController: Manages flow decisions
    - ResponseEnhancer: Enhances responses with LLM

    The evaluation flow is:
    1. Heuristic evaluation (fast, ~5ms)
    2. LLM analysis if score < 0.90 (fast COMPLEX model, ~10-15s)
    3. Combine scores (50% heuristic, 50% LLM)
    4. Flow decision based on combined evaluation

    Follows SRP: Orchestration responsibility only.
    """

    # Weight for combining heuristic and LLM scores
    # Balanced 50/50 - heuristic detects data, LLM detects semantic alignment
    HEURISTIC_WEIGHT = 0.5
    LLM_WEIGHT = 0.5

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        """
        Initialize supervisor agent.

        Args:
            ollama: Ollama LLM instance
            config: Configuration dictionary with optional keys:
                - enable_llm_analysis: Enable LLM analysis (default: True)
                - llm_analysis_timeout: LLM timeout in seconds (default: 15)
                - skip_llm_threshold: Skip LLM if heuristic >= this (default: 0.90)
                - llm_weight: Weight of LLM score in combined (default: 0.5)
        """
        super().__init__("supervisor", config or {}, ollama=ollama)

        # Configuration
        self.max_retries = self.config.get("max_retries", 2)
        self.quality_threshold = self.config.get("quality_threshold", 0.65)
        self.enable_human_handoff = self.config.get("enable_human_handoff", True)
        self.enable_re_routing = self.config.get("enable_re_routing", True)
        # Disable enhancement by default for faster responses
        self.enable_response_enhancement = self.config.get("enable_response_enhancement", False)

        # LLM Analysis configuration (PERFORMANCE OPTIMIZED)
        self.enable_llm_analysis = self.config.get("enable_llm_analysis", True)
        # Increased from 15 to 60 to avoid premature timeouts with slow local LLMs
        self.llm_analysis_timeout = self.config.get("llm_analysis_timeout", 60)
        # Lowered from 0.90 to 0.75 to avoid LLM timeout loops on good heuristic scores
        self.skip_llm_threshold = self.config.get("skip_llm_threshold", 0.75)
        self.llm_weight = self.config.get("llm_weight", self.LLM_WEIGHT)
        self.heuristic_weight = 1.0 - self.llm_weight

        # Quality thresholds
        self.quality_thresholds = {
            "response_completeness": self.config.get("completeness_threshold", 0.6),
            "response_relevance": self.config.get("relevance_threshold", 0.7),
            "task_completion": self.config.get("task_completion_threshold", 0.8),
        }

        # Initialize components (SRP - each handles single responsibility)
        self.quality_evaluator = ResponseQualityEvaluator(thresholds=self.quality_thresholds)
        self.flow_controller = ConversationFlowController(
            quality_threshold=self.quality_threshold,
            max_retries=self.max_retries,
            enable_human_handoff=self.enable_human_handoff,
            enable_re_routing=self.enable_re_routing,
        )
        self.response_enhancer = ResponseEnhancer(ollama=ollama)

        # Initialize LLM Response Analyzer (NEW)
        self.llm_analyzer = LLMResponseAnalyzer(
            ollama=ollama,
            config={
                "enable_llm_analysis": self.enable_llm_analysis,
                "llm_timeout": self.llm_analysis_timeout,
                "skip_llm_threshold": self.skip_llm_threshold,
            },
        )

        # Language detector
        self.language_detector = LanguageDetector(
            config={"default_language": "es", "supported_languages": ["es", "en", "pt"]}
        )

        # Store ollama reference
        self.ollama = ollama

        logger.info(
            f"SupervisorAgent initialized (llm_analysis={self.enable_llm_analysis}, "
            f"threshold={self.skip_llm_threshold}, weight={self.llm_weight})"
        )

    @trace_async_method(
        name="supervisor_agent_process",
        run_type="chain",
        metadata={"agent_type": "supervisor", "role": "response_evaluation"},
        extract_state=True,
    )
    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate the previous agent's response and determine conversation flow.

        Evaluation flow:
        1. Heuristic evaluation (fast, ~5ms)
        2. LLM analysis if heuristic score < 0.90 (COMPLEX model, ~10-15s)
        3. Combine scores (50% heuristic, 50% LLM)
        4. Flow decision based on combined evaluation

        Args:
            message: User message (for context)
            state_dict: Current conversation state including agent response

        Returns:
            Dictionary with quality evaluation and flow decision
        """
        try:
            conversation_history = state_dict.get("messages", [])
            current_agent = state_dict.get("current_agent")

            # Extract last agent response
            last_response = self._extract_last_agent_response(conversation_history)

            if not last_response:
                return self._handle_missing_response()

            # Step 1: Heuristic evaluation (fast)
            quality_evaluation = await self.quality_evaluator.evaluate(
                user_message=message,
                agent_response=last_response,
                agent_name=current_agent or "unknown",
                conversation_context=state_dict,
            )

            heuristic_score = quality_evaluation.get("overall_score", 0.0)

            # Step 2: LLM analysis (if enabled and score suggests it's needed)
            llm_analysis = None
            if self.enable_llm_analysis:
                llm_analysis = await self.llm_analyzer.analyze(
                    user_message=message,
                    agent_response=last_response,
                    agent_name=current_agent or "unknown",
                    conversation_context=state_dict,
                    heuristic_score=heuristic_score,
                )

            # Step 3: Combine heuristic + LLM evaluations
            combined_evaluation = self._combine_evaluations(
                quality_evaluation, llm_analysis
            )

            # Step 4: Determine conversation flow using combined evaluation
            flow_decision = self.flow_controller.determine_flow(combined_evaluation, state_dict)

            # Determine if should provide final response
            should_provide_final = self.flow_controller.should_provide_final_response(
                combined_evaluation, state_dict
            )

            # Enhance response if needed (use combined score)
            enhanced_response = None
            combined_score = combined_evaluation.get("overall_score", 0.0)
            should_enhance = combined_score < 0.8

            if (
                (flow_decision.get("should_end") or should_provide_final)
                and not flow_decision.get("needs_human_handoff")
            ):
                if self.enable_response_enhancement and self.ollama and should_enhance:
                    # Detect user language
                    language_info = self.language_detector.detect_language(message)
                    detected_language = language_info.get("language", "es")

                    logger.info(
                        f"Enhancing response - Quality: {combined_score:.2f}, "
                        f"Language: {detected_language}"
                    )

                    # Enhance response using enhancer component
                    enhanced_response = await self.response_enhancer.enhance(
                        original_response=last_response,
                        user_message=message,
                        language=detected_language,
                        context=state_dict,
                    )

                    if enhanced_response:
                        flow_decision["should_end"] = True
                        flow_decision["decision_type"] = "enhanced_response_complete"
                        logger.info("Response enhanced, marking conversation as complete")

            # Determine next_agent for re-routing
            next_agent_value = None
            if flow_decision.get("needs_re_routing") and not flow_decision.get("should_end"):
                next_agent_value = "orchestrator"
                logger.info("Supervisor: Setting next_agent to orchestrator for re-routing")

            return {
                "supervisor_evaluation": combined_evaluation,
                "llm_analysis": self._serialize_llm_analysis(llm_analysis),
                "conversation_flow": flow_decision,
                "is_complete": flow_decision.get("should_end", False),
                "needs_re_routing": flow_decision.get("needs_re_routing", False),
                "human_handoff_requested": flow_decision.get("needs_human_handoff", False),
                "enhanced_response": enhanced_response,
                "next_agent": next_agent_value,  # Propagate next_agent for routing
                "supervisor_analysis": {
                    "current_agent": current_agent,
                    "quality_score": combined_score,
                    "heuristic_score": heuristic_score,
                    "llm_analysis_used": llm_analysis is not None and not isinstance(
                        llm_analysis, AnalyzerFallbackResult
                    ),
                    "evaluation_timestamp": self._get_current_timestamp(),
                    "flow_decision": flow_decision["decision_type"],
                    "response_enhanced": enhanced_response is not None,
                },
            }

        except Exception as e:
            logger.error(f"Error in supervisor evaluation: {str(e)}")
            return self._handle_evaluation_error(str(e), state_dict)

    def _extract_last_agent_response(
        self,
        conversation_history: list[dict[str, Any]],
    ) -> str | None:
        """Extract the last agent response from conversation history."""
        if not conversation_history:
            return None

        for message in reversed(conversation_history):
            if isinstance(message, dict) and message.get("role") == "assistant":
                return message.get("content", "")
            elif hasattr(message, "content") and hasattr(message, "role"):
                if getattr(message, "role", None) == "assistant":
                    return getattr(message, "content", "")

        return None

    def _handle_missing_response(self) -> dict[str, Any]:
        """Handle case where no agent response found."""
        return {
            "supervisor_evaluation": {
                "overall_score": 0.0,
                "error": "No agent response found",
            },
            "conversation_flow": {
                "decision_type": "error_fallback",
                "should_end": False,
                "needs_re_routing": True,
            },
            "needs_re_routing": True,
            "supervisor_analysis": {
                "error": "Missing agent response",
                "evaluation_timestamp": self._get_current_timestamp(),
            },
        }

    def _handle_evaluation_error(
        self,
        error_message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle errors during evaluation."""
        return {
            "supervisor_evaluation": {
                "overall_score": 0.0,
                "error": error_message,
            },
            "conversation_flow": {
                "decision_type": "error_end",
                "should_end": True,
            },
            "is_complete": True,
            "error_count": state_dict.get("error_count", 0) + 1,
            "supervisor_analysis": {
                "error": error_message,
                "evaluation_timestamp": self._get_current_timestamp(),
            },
        }

    def _get_current_timestamp(self) -> str:
        """Get current UTC timestamp."""
        return datetime.now(UTC).isoformat()

    def _combine_evaluations(
        self,
        heuristic: dict[str, Any],
        llm_analysis: LLMResponseAnalysis | AnalyzerFallbackResult | None,
    ) -> dict[str, Any]:
        """
        Combine heuristic and LLM evaluations into unified result.

        Weights: 40% heuristic, 60% LLM (configurable via llm_weight)

        Args:
            heuristic: Heuristic evaluation from ResponseQualityEvaluator
            llm_analysis: LLM analysis result or fallback

        Returns:
            Combined evaluation dictionary
        """
        combined = dict(heuristic)

        if llm_analysis is None:
            combined["llm_analysis_status"] = "disabled"
            return combined

        if isinstance(llm_analysis, AnalyzerFallbackResult):
            # LLM failed or was skipped, use heuristic only
            combined["llm_analysis_status"] = "fallback"
            combined["llm_fallback_reason"] = llm_analysis.reason
            return combined

        # LLM analysis succeeded - blend scores
        heuristic_score = heuristic.get("overall_score", 0.0)
        llm_score = llm_analysis.overall_score

        combined_score = (heuristic_score * self.heuristic_weight) + (llm_score * self.llm_weight)

        # Update combined evaluation with LLM insights
        combined.update({
            "overall_score": combined_score,
            "llm_analysis_status": "success",
            "llm_quality": llm_analysis.quality.value,
            "llm_score": llm_score,
            "llm_recommended_action": llm_analysis.recommended_action.value,
            "llm_reasoning": llm_analysis.reasoning,
            "llm_confidence": llm_analysis.confidence,
            # Override suggested_action if LLM has strong opinion
            "suggested_action": self._resolve_action(
                heuristic.get("suggested_action", "accept"),
                llm_analysis.recommended_action,
                llm_analysis.confidence,
            ),
            # Hallucination detection (priority feature)
            "hallucination_risk": llm_analysis.hallucination.risk_level.value,
            "hallucination_suspicious_claims": llm_analysis.hallucination.suspicious_claims,
            # Question-answer alignment
            "question_answered": llm_analysis.question_answer_alignment.answers_question,
            "alignment_score": llm_analysis.question_answer_alignment.alignment_score,
            "missing_aspects": llm_analysis.question_answer_alignment.missing_aspects,
            # Completeness
            "is_complete": llm_analysis.completeness.is_complete,
            "has_specific_data": llm_analysis.completeness.has_specific_data,
        })

        logger.info(
            f"Combined evaluation: heuristic={heuristic_score:.2f}, "
            f"llm={llm_score:.2f}, combined={combined_score:.2f}, "
            f"hallucination_risk={llm_analysis.hallucination.risk_level.value}"
        )

        return combined

    def _resolve_action(
        self,
        heuristic_action: str,
        llm_action: RecommendedAction,
        llm_confidence: float,
    ) -> str:
        """
        Resolve final action from heuristic and LLM recommendations.

        If LLM is highly confident (>=0.8), prefer its recommendation.
        Otherwise, prefer the more conservative action (higher priority).

        Args:
            heuristic_action: Action from heuristic evaluation
            llm_action: Action from LLM analysis
            llm_confidence: Confidence of LLM analysis

        Returns:
            Final action string
        """
        # If LLM is highly confident, prefer its recommendation
        if llm_confidence >= 0.8:
            return llm_action.value

        # Map actions to priority (higher = more conservative)
        action_priority = {
            "escalate": 5,  # Highest priority (most conservative)
            "reroute": 4,
            "re_route": 4,
            "clarify": 3,
            "enhance": 2,
            "accept": 1,
            "stop_retry": 1,
        }

        h_priority = action_priority.get(heuristic_action, 1)
        l_priority = action_priority.get(llm_action.value, 1)

        # Prefer higher priority action (more conservative)
        if l_priority > h_priority:
            return llm_action.value
        return heuristic_action

    def _serialize_llm_analysis(
        self,
        analysis: LLMResponseAnalysis | AnalyzerFallbackResult | None,
    ) -> dict[str, Any] | None:
        """
        Serialize LLM analysis for response.

        Args:
            analysis: LLM analysis result or None

        Returns:
            Serialized dictionary or None
        """
        if analysis is None:
            return None

        if isinstance(analysis, AnalyzerFallbackResult):
            return {
                "status": "fallback",
                "reason": analysis.reason,
                "heuristic_score": analysis.heuristic_score,
            }

        return {
            "status": "success",
            "quality": analysis.quality.value,
            "score": analysis.overall_score,
            "action": analysis.recommended_action.value,
            "reasoning": analysis.reasoning,
            "confidence": analysis.confidence,
            "hallucination_risk": analysis.hallucination.risk_level.value,
            "suspicious_claims": analysis.hallucination.suspicious_claims,
            "question_answered": analysis.question_answer_alignment.answers_question,
            "is_complete": analysis.completeness.is_complete,
        }

    def get_supervisor_metrics(self) -> dict[str, Any]:
        """
        Get supervisor metrics.

        Returns:
            Dictionary with evaluation metrics including LLM analysis config
        """
        base_metrics = self.get_agent_metrics()

        return {
            **base_metrics,
            "supervisor_metrics": {
                "quality_threshold": self.quality_threshold,
                "max_retries": self.max_retries,
                "human_handoff_enabled": self.enable_human_handoff,
                "re_routing_enabled": self.enable_re_routing,
                "quality_thresholds": self.quality_thresholds,
                # LLM Analysis metrics
                "llm_analysis_enabled": self.enable_llm_analysis,
                "llm_analysis_timeout": self.llm_analysis_timeout,
                "skip_llm_threshold": self.skip_llm_threshold,
                "llm_weight": self.llm_weight,
                "heuristic_weight": self.heuristic_weight,
            },
        }
