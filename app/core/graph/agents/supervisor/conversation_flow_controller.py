"""
Conversation Flow Controller.

Manages conversation flow decisions based on quality evaluations.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConversationFlowController:
    """
    Controls conversation flow based on quality evaluations.

    Responsibilities:
    - Determine if conversation should continue
    - Decide if re-routing is needed
    - Detect need for human handoff
    - Detect user frustration
    """

    def __init__(
        self,
        quality_threshold: float = 0.7,
        max_retries: int = 2,
        enable_human_handoff: bool = True,
        enable_re_routing: bool = True,
    ):
        """
        Initialize the flow controller.

        Args:
            quality_threshold: Minimum quality score to pass
            max_retries: Maximum number of retries before escalation
            enable_human_handoff: Whether to enable human handoff
            enable_re_routing: Whether to enable re-routing
        """
        self.quality_threshold = quality_threshold
        self.max_retries = max_retries
        self.enable_human_handoff = enable_human_handoff
        self.enable_re_routing = enable_re_routing

    def determine_flow(
        self,
        quality_evaluation: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Determine the next step in conversation flow.

        Uses intelligent evaluation from ResponseQualityEvaluator including:
        - suggested_action: "accept", "re_route", or "stop_retry"
        - category: Response category (complete_with_data, fallback, etc.)
        - rag_had_results: Whether RAG returned any results

        Args:
            quality_evaluation: Quality evaluation results
            state_dict: Current conversation state

        Returns:
            Dictionary with flow decision
        """
        overall_score = quality_evaluation.get("overall_score", 0.0)
        suggested_action = quality_evaluation.get("suggested_action", "accept")
        category = quality_evaluation.get("category", "partial_info")
        rag_had_results = quality_evaluation.get("rag_had_results", True)

        # Check if needs human handoff first
        if self._needs_human_handoff(quality_evaluation, state_dict):
            return {
                "decision_type": "human_handoff",
                "should_end": True,
                "needs_human_handoff": True,
                "reason": "Response quality below threshold or user frustration detected",
            }

        # Use suggested action from intelligent evaluator
        # Note: "enhance" is treated as "accept" when score >= 0.65 because:
        # 1. Enhancement feature is disabled by default
        # 2. A score of 0.65+ indicates a reasonably good response
        # 3. Prevents unnecessary loops when LLM suggests enhancement
        if suggested_action in ("accept", "stop_retry", "enhance"):
            reason = f"Category: {category}, Action: {suggested_action}, Score: {overall_score:.2f}"
            if suggested_action == "stop_retry":
                reason += " (re-routing would not help)"
            if suggested_action == "enhance":
                reason += " (treated as accept - enhancement disabled)"
            logger.info(f"Flow decision: complete - {reason}")
            return {
                "decision_type": "conversation_complete",
                "should_end": True,
                "reason": reason,
            }

        if suggested_action == "re_route":
            # Double-check that re-routing makes sense
            if not self._should_reroute(state_dict, rag_had_results):
                logger.info("Flow decision: skipping re-route (would not help)")
                return {
                    "decision_type": "conversation_complete",
                    "should_end": True,
                    "reason": f"Re-routing would not help (category: {category})",
                }

            logger.info(f"Flow decision: re-route - category: {category}, score: {overall_score:.2f}")
            return {
                "decision_type": "re_route",
                "should_end": False,
                "needs_re_routing": True,
                "reason": f"Low quality ({category}), attempting re-route",
            }

        # Fallback to legacy logic for high quality responses
        if overall_score >= self.quality_threshold:
            return {
                "decision_type": "conversation_complete",
                "should_end": True,
                "reason": f"High quality response (score: {overall_score:.2f})",
            }

        # Default: end conversation
        return {
            "decision_type": "conversation_end",
            "should_end": True,
            "reason": f"Default end (score: {overall_score:.2f}, category: {category})",
        }

    def _should_reroute(
        self,
        state_dict: dict[str, Any],
        rag_had_results: bool,
    ) -> bool:
        """
        Check if re-routing would actually help.

        Re-routing is useless when:
        - RAG returned no results (can't create data magically)
        - Same agent already tried multiple times (agent loop)
        """
        # RAG empty → re-routing won't create data
        if not rag_had_results:
            logger.info("Skipping re-route: RAG returned no results")
            return False

        # Same agent tried multiple times → avoid agent loops
        agent_history = state_dict.get("agent_history", [])
        if len(agent_history) >= 2 and agent_history[-1] == agent_history[-2]:
            logger.info(f"Skipping re-route: Same agent ({agent_history[-1]}) already tried")
            return False

        return True

    def should_provide_final_response(
        self,
        quality_evaluation: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> bool:
        """
        Determine if supervisor should provide final response.

        Args:
            quality_evaluation: Quality evaluation results
            state_dict: Current conversation state

        Returns:
            True if should provide final response
        """
        overall_score = quality_evaluation.get("overall_score", 0.0)
        retry_count = state_dict.get("supervisor_retry_count", 0)

        # Criteria for providing final response:
        # 1. Quality is good enough
        if overall_score >= self.quality_threshold:
            return True

        # 2. Max retries reached
        if retry_count >= self.max_retries:
            return True

        # 3. Response is acceptable (medium score) - sufficient for user
        if overall_score >= 0.5:
            return True

        # 4. Critical error requiring immediate response
        if state_dict.get("error_count", 0) >= 2:
            return True

        # Otherwise, try re-routing
        return False

    def _needs_human_handoff(
        self,
        quality_evaluation: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> bool:
        """Determine if human handoff is needed."""
        error_count = state_dict.get("error_count", 0)
        retry_count = state_dict.get("supervisor_retry_count", 0)

        if error_count >= self.max_retries or retry_count >= self.max_retries:
            logger.info(
                f"Too many errors/retries ({error_count}/{retry_count}), suggesting human handoff"
            )
            return True

        overall_score = quality_evaluation.get("overall_score", 0.0)
        if overall_score < 0.3:
            logger.info(
                f"Very low quality score ({overall_score:.2f}), suggesting human handoff"
            )
            return True

        messages = state_dict.get("messages", [])
        if self.detect_user_frustration(messages):
            return True

        return False

    def detect_user_frustration(self, messages: list[dict[str, Any]]) -> bool:
        """
        Detect user frustration in recent messages.

        Args:
            messages: List of conversation messages

        Returns:
            True if frustration detected
        """
        frustration_keywords = [
            "no funciona",
            "terrible",
            "pésimo",
            "queja",
            "reclamo",
            "gerente",
            "supervisor",
            "no sirve",
            "horrible",
            "malo",
        ]

        # Check last 2 user messages
        user_messages = [
            msg
            for msg in messages[-4:]
            if isinstance(msg, dict) and msg.get("role") == "user"
        ][-2:]

        for msg in user_messages:
            content = msg.get("content", "").lower()
            if any(keyword in content for keyword in frustration_keywords):
                logger.info("Detected user frustration, suggesting human handoff")
                return True

        return False
