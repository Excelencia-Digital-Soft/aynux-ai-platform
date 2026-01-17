# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Human handoff node for transferring to human agents.
# ============================================================================
"""Human Handoff Node.

Handles transferring the conversation to a human agent when:
- User requests human assistance
- Certain specialties require human booking (e.g., FONOAUDIOLOGIA)
- Error threshold exceeded
- Routing rules trigger handoff

The node sends a message to the user and marks the conversation
for human takeover.
"""

import logging
from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class HumanHandoffNode(BaseNode):
    """Node for transferring conversation to human agent.

    Sends handoff message and sets state flags for the conversation
    to be picked up by a human agent.

    Config options:
        message: Custom handoff message.
        transfer_to: Queue/agent to transfer to (default: "default").
        include_context: Whether to include conversation context.
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process handoff request.

        Args:
            state: Current conversation state.

        Returns:
            State updates with handoff flags set.
        """
        # Get configuration
        config = self._config or {}
        custom_message = config.get("message")
        transfer_to = config.get("transfer_to", "default")
        include_context = config.get("include_context", True)

        # Determine handoff reason
        handoff_reason = self._determine_reason(state)

        # Build handoff message
        message = self._build_message(state, custom_message, handoff_reason)

        # Send message to user
        phone = state.get("user_phone", "")
        if phone and self._notification:
            try:
                await self._notification.send_message(phone=phone, message=message)
            except Exception as e:
                logger.warning(f"Failed to send handoff message: {e}")

        # Build context summary for human agent
        context_summary = None
        if include_context:
            context_summary = self._build_context_summary(state)

        logger.info(
            f"Human handoff triggered: reason={handoff_reason}, "
            f"transfer_to={transfer_to}, phone={phone}"
        )

        return {
            "next_node": "__end__",
            "transferred_to_human": True,
            "handoff_reason": handoff_reason,
            "handoff_transfer_to": transfer_to,
            "handoff_context": context_summary,
            "messages": [self._create_ai_message(message)],
        }

    def _determine_reason(self, state: "MedicalAppointmentsState") -> str:
        """Determine the reason for handoff.

        Args:
            state: Current conversation state.

        Returns:
            Handoff reason string.
        """
        # Check for explicit request
        detected_intent = state.get("detected_intent")
        if detected_intent == "human_request":
            return "user_requested"

        # Check for specialty-based handoff
        specialty = state.get("selected_specialty") or state.get("specialty_name")
        if specialty:
            # Get handoff specialties from config
            handoff_specialties = self._config.get("human_handoff_specialties", [])
            if specialty.upper() in [s.upper() for s in handoff_specialties]:
                return f"specialty:{specialty}"

        # Check for error-based handoff
        error_count = state.get("error_count", 0)
        max_errors = self._config.get("max_errors_before_handoff", 3)
        if error_count >= max_errors:
            return "error_threshold"

        # Check for routing rule triggered
        routing_rule = state.get("triggered_routing_rule")
        if routing_rule:
            return f"routing_rule:{routing_rule}"

        return "unknown"

    def _build_message(
        self,
        state: "MedicalAppointmentsState",
        custom_message: str | None,
        reason: str,
    ) -> str:
        """Build the handoff message.

        Args:
            state: Current conversation state.
            custom_message: Optional custom message from config.
            reason: Handoff reason.

        Returns:
            Formatted message string.
        """
        if custom_message:
            # Allow placeholders in custom message
            patient_name = self._get_patient_name(state)
            specialty = state.get("selected_specialty", "")
            return custom_message.format(
                patient_name=patient_name,
                specialty=specialty,
                institution_name=self.institution_name,
            )

        # Default messages based on reason
        if reason == "user_requested":
            return (
                "Entendido. Te estoy transfiriendo con un agente para brindarte "
                "mejor asistencia. Por favor espera un momento."
            )

        if reason.startswith("specialty:"):
            specialty = reason.split(":", 1)[1]
            return (
                f"Para agendar un turno de {specialty}, necesitamos derivarte "
                "con un agente que te ayudará a coordinar la cita. "
                "Por favor espera un momento."
            )

        if reason == "error_threshold":
            return (
                "Parece que estamos teniendo dificultades para ayudarte. "
                "Te estamos transfiriendo con un agente humano que podrá "
                "asistirte mejor. Por favor espera."
            )

        # Default fallback
        return (
            "Te estamos transfiriendo con un agente para continuar con tu consulta. "
            "Por favor espera un momento."
        )

    def _build_context_summary(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Build a context summary for the human agent.

        Args:
            state: Current conversation state.

        Returns:
            Dictionary with relevant context.
        """
        summary: dict[str, Any] = {
            "patient_document": state.get("patient_document"),
            "patient_name": self._get_patient_name(state),
            "is_registered": state.get("is_registered", False),
        }

        # Add booking context if available
        if state.get("selected_specialty"):
            summary["selected_specialty"] = state.get("selected_specialty")
        if state.get("selected_provider"):
            provider = state.get("selected_provider", {})
            summary["selected_provider"] = provider.get("nombre") if isinstance(provider, dict) else provider
        if state.get("selected_date"):
            summary["selected_date"] = state.get("selected_date")
        if state.get("selected_time"):
            summary["selected_time"] = state.get("selected_time")

        # Add conversation summary
        messages = state.get("messages", [])
        if messages:
            # Get last few messages for context
            recent_messages = messages[-5:] if len(messages) > 5 else messages
            summary["recent_messages"] = [
                {
                    "role": "user" if hasattr(m, "type") and m.type == "human" else "assistant",
                    "content": m.content if hasattr(m, "content") else str(m),
                }
                for m in recent_messages
            ]

        # Add error context
        if state.get("error_count", 0) > 0:
            summary["error_count"] = state.get("error_count")
            summary["last_error"] = state.get("last_error")

        return summary

    def _get_patient_name(self, state: "MedicalAppointmentsState") -> str:
        """Extract patient name from state.

        Args:
            state: Current conversation state.

        Returns:
            Patient name or generic greeting.
        """
        patient_data = state.get("patient_data", {})
        if isinstance(patient_data, dict):
            name = patient_data.get("nombre") or patient_data.get("name")
            if name:
                return name
        return "estimado/a"

    def _create_ai_message(self, content: str) -> Any:
        """Create an AI message for the state.

        Args:
            content: Message content.

        Returns:
            AIMessage instance.
        """
        from langchain_core.messages import AIMessage

        return AIMessage(content=content)
