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

        Args:
            quality_evaluation: Quality evaluation results
            state_dict: Current conversation state

        Returns:
            Dictionary with flow decision
        """
        overall_score = quality_evaluation.get("overall_score", 0.0)
        retry_count = state_dict.get("supervisor_retry_count", 0)

        # Check if needs human handoff
        if self._needs_human_handoff(quality_evaluation, state_dict):
            return {
                "decision_type": "human_handoff",
                "should_end": True,
                "needs_human_handoff": True,
                "reason": "Response quality below threshold or user frustration detected",
            }

        # Check if response is satisfactory (high quality)
        if overall_score >= self.quality_threshold:
            return {
                "decision_type": "conversation_complete",
                "should_end": True,
                "reason": f"High quality response (score: {overall_score:.2f})",
            }

        # Check if response is acceptable (medium quality but sufficient)
        if overall_score >= 0.5 and retry_count > 0:
            return {
                "decision_type": "acceptable_response",
                "should_end": True,
                "reason": f"Acceptable response after retries (score: {overall_score:.2f})",
            }

        # Check if needs re-routing (low quality and retries available)
        if self.enable_re_routing and retry_count < self.max_retries and overall_score < 0.5:
            return {
                "decision_type": "re_route",
                "should_end": False,
                "needs_re_routing": True,
                "reason": f"Low quality response (score: {overall_score:.2f}), attempting re-route",
            }

        # Cannot improve further, end conversation
        return {
            "decision_type": "conversation_end",
            "should_end": True,
            "reason": "Max retries reached or quality cannot be improved further",
        }

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

        # 3. Response is acceptable (medium score) after retries
        if overall_score >= 0.5 and retry_count > 0:
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
