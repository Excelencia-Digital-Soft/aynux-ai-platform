"""
Supervisor Agent.

Main orchestrator that evaluates responses and manages conversation quality.
Uses extracted components for SRP compliance.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.agents import BaseAgent
from app.core.graph.agents.supervisor.conversation_flow_controller import (
    ConversationFlowController,
)
from app.core.graph.agents.supervisor.response_enhancer import ResponseEnhancer
from app.core.graph.agents.supervisor.response_quality_evaluator import (
    ResponseQualityEvaluator,
)
from app.core.utils.tracing import trace_async_method
from app.utils.language_detector import LanguageDetector

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that evaluates response quality and manages conversation flow.

    This agent orchestrates the evaluation process using extracted components:
    - ResponseQualityEvaluator: Evaluates response quality
    - ConversationFlowController: Manages flow decisions
    - ResponseEnhancer: Enhances responses with LLM

    Follows SRP: Orchestration responsibility only.
    """

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        """
        Initialize supervisor agent.

        Args:
            ollama: Ollama LLM instance
            config: Configuration dictionary
        """
        super().__init__("supervisor", config or {}, ollama=ollama)

        # Configuration
        self.max_retries = self.config.get("max_retries", 2)
        self.quality_threshold = self.config.get("quality_threshold", 0.7)
        self.enable_human_handoff = self.config.get("enable_human_handoff", True)
        self.enable_re_routing = self.config.get("enable_re_routing", True)
        # Disable enhancement by default for faster responses
        self.enable_response_enhancement = self.config.get("enable_response_enhancement", False)

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

        # Language detector
        self.language_detector = LanguageDetector(
            config={"default_language": "es", "supported_languages": ["es", "en", "pt"]}
        )

        # Store ollama reference
        self.ollama = ollama

        logger.info("SupervisorAgent initialized for response evaluation and quality control")

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

            # Evaluate response quality using evaluator component
            quality_evaluation = await self.quality_evaluator.evaluate(
                user_message=message,
                agent_response=last_response,
                agent_name=current_agent or "unknown",
                conversation_context=state_dict,
            )

            # Determine conversation flow using flow controller
            flow_decision = self.flow_controller.determine_flow(quality_evaluation, state_dict)

            # Determine if should provide final response
            should_provide_final = self.flow_controller.should_provide_final_response(
                quality_evaluation, state_dict
            )

            # Enhance response if needed
            enhanced_response = None
            should_enhance = quality_evaluation.get("overall_score", 0.0) < 0.8

            if (
                (flow_decision.get("should_end") or should_provide_final)
                and not flow_decision.get("needs_human_handoff")
            ):
                if self.enable_response_enhancement and self.ollama and should_enhance:
                    # Detect user language
                    language_info = self.language_detector.detect_language(message)
                    detected_language = language_info.get("language", "es")

                    logger.info(
                        f"Enhancing response - Quality: {quality_evaluation.get('overall_score', 0):.2f}, "
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

            return {
                "supervisor_evaluation": quality_evaluation,
                "conversation_flow": flow_decision,
                "is_complete": flow_decision.get("should_end", False),
                "needs_re_routing": flow_decision.get("needs_re_routing", False),
                "human_handoff_requested": flow_decision.get("needs_human_handoff", False),
                "enhanced_response": enhanced_response,
                "supervisor_analysis": {
                    "current_agent": current_agent,
                    "quality_score": quality_evaluation.get("overall_score", 0.0),
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

    def get_supervisor_metrics(self) -> dict[str, Any]:
        """
        Get supervisor metrics.

        Returns:
            Dictionary with evaluation metrics
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
            },
        }
