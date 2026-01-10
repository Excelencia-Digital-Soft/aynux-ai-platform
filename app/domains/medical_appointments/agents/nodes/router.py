# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Router node for intent detection.
# ============================================================================
"""Router Node.

Handles intent detection and routing to appropriate nodes.
Uses IntentDetector with Strategy pattern for OCP compliance.
"""

import logging
from typing import TYPE_CHECKING, Any

from .base import BaseNode
from .intent import IntentDetector, create_default_detector

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class RouterNode(BaseNode):
    """Node for routing messages to appropriate handlers.

    Uses IntentDetector for extensible intent detection (OCP).
    Custom patterns can be added without modifying this class.
    """

    def __init__(
        self,
        medical_client: Any,
        notification_service: Any = None,
        config: dict[str, Any] | None = None,
        intent_detector: IntentDetector | None = None,
    ) -> None:
        """Initialize router.

        Args:
            medical_client: Medical system client.
            notification_service: Optional notification service.
            config: Optional configuration dictionary.
            intent_detector: Optional custom intent detector.
        """
        super().__init__(medical_client, notification_service, config)
        self._detector = intent_detector or create_default_detector()

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Route message to appropriate node.

        Args:
            state: Current state.

        Returns:
            State updates with next_node set.
        """
        message = self._get_message(state)

        # 1. Try pattern-based detection
        result = self._detector.detect(message, state)
        if result.detected:
            return result.to_dict()

        # 2. If patient is registered, continue booking flow
        if state.get("patient_data"):
            return self._route_booking_flow(state, message.lower().strip())

        # 3. If needs registration
        if state.get("needs_registration"):
            return {
                "next_node": "patient_registration",
                "detected_intent": "registration",
            }

        # 4. Default: fallback
        return {"next_node": "fallback", "detected_intent": "unknown"}

    def _route_booking_flow(
        self,
        state: "MedicalAppointmentsState",
        message: str,
    ) -> dict[str, Any]:
        """Route within the booking flow based on current state.

        Args:
            state: Current state.
            message: User message (lowercase).

        Returns:
            State updates for booking flow progression.
        """
        selection = self._get_selection(state)

        # Handle confirmation awaiting
        if state.get("awaiting_confirmation"):
            if self._is_confirmation(message):
                return {"next_node": "booking_confirmation", "detected_intent": "confirm_booking"}
            if self._is_cancellation(message):
                return {
                    "next_node": "fallback",
                    "detected_intent": "cancel_booking",
                    "awaiting_confirmation": False,
                }

        # Progress through flow based on current selections
        if state.get("selected_time"):
            return {
                "next_node": "booking_confirmation",
                "detected_intent": "booking_confirmation",
                "awaiting_confirmation": True,
            }

        if state.get("selected_date") and selection is not None:
            return {"next_node": "time_selection", "detected_intent": "time_selection"}

        if state.get("selected_provider") and selection is not None:
            return {"next_node": "date_selection", "detected_intent": "date_selection"}

        if state.get("selected_specialty") and selection is not None:
            return {"next_node": "provider_selection", "detected_intent": "provider_selection"}

        if state.get("specialties_list") and selection is not None:
            return {"next_node": "specialty_selection", "detected_intent": "specialty_selection"}

        # Default to specialty selection
        return {"next_node": "specialty_selection", "detected_intent": "show_specialties"}
