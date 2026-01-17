# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: NLU Router combining intent detection and entity extraction.
# ============================================================================
"""NLU Router for Medical Appointments.

Combines intent detection and entity extraction to provide intelligent
routing decisions for the medical appointments workflow. Can skip workflow
steps when entities are already provided in the user message.

Usage:
    router = NLURouter()
    result = await router.process("Quiero turno para cardiología mañana a la tarde")

    print(result.intent)  # "book_appointment"
    print(result.entities)  # {"specialty": "cardiología", "date": "mañana", ...}
    print(result.suggested_node)  # "date_selection" (skipped specialty since provided)
    print(result.skip_nodes)  # ["specialty_selection"]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .entity_extractor import ExtractedEntities, MedicalEntityExtractor
from .intent_detector import MedicalIntentDetector, MedicalIntentResult

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Node mapping for intents
INTENT_TO_NODE: dict[str, str] = {
    "book_appointment": "patient_identification",
    "cancel_appointment": "appointment_management",
    "reschedule_appointment": "reschedule",
    "view_appointments": "appointment_management",
    "greeting": "greeting",
    "human_request": "human_handoff",
    "farewell": "__end__",
    "info_query": "fallback",
    "unknown": "fallback",
}

# Nodes that can be skipped when entities are present
SKIP_CONDITIONS: dict[str, str] = {
    "specialty_selection": "specialty",  # Skip if specialty provided
    "date_selection": "date_value",  # Skip if date provided
    "provider_selection": "provider_name",  # Skip if provider mentioned
}

# Node sequence for booking flow
BOOKING_FLOW_SEQUENCE = [
    "patient_identification",
    "specialty_selection",
    "provider_selection",
    "date_selection",
    "time_selection",
    "booking_confirmation",
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class NLUResult:
    """Combined result from NLU processing.

    Attributes:
        intent_result: Intent detection result.
        entities: Extracted entities.
        suggested_node: Recommended next node.
        skip_nodes: Nodes that can be skipped.
        confidence: Overall confidence score.
        state_updates: Suggested state updates.
        analysis: Analysis metadata.
    """

    intent_result: MedicalIntentResult
    entities: ExtractedEntities
    suggested_node: str
    skip_nodes: list[str] = field(default_factory=list)
    confidence: float = 0.0
    state_updates: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)

    @property
    def intent(self) -> str:
        """Get detected intent."""
        return self.intent_result.intent

    @property
    def is_high_confidence(self) -> bool:
        """Check if result has high confidence."""
        return self.confidence >= 0.75

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent": self.intent,
            "intent_confidence": self.intent_result.confidence,
            "suggested_node": self.suggested_node,
            "skip_nodes": self.skip_nodes,
            "overall_confidence": self.confidence,
            "entities": self.entities.to_dict(),
            "state_updates": self.state_updates,
            "analysis": self.analysis,
        }


# =============================================================================
# NLU Router
# =============================================================================

class NLURouter:
    """NLU Router for intelligent workflow navigation.

    Combines intent detection and entity extraction to determine:
    1. What the user wants to do (intent)
    2. What information they've already provided (entities)
    3. Which workflow node to route to (considering skips)
    4. State updates to apply

    Config options:
        enable_skip_logic: Allow skipping nodes when entities present.
        min_confidence: Minimum confidence for skip decisions.
        interaction_mode: "buttons_only", "nlu_only", "hybrid"
    """

    def __init__(
        self,
        intent_detector: MedicalIntentDetector | None = None,
        entity_extractor: MedicalEntityExtractor | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize NLU router.

        Args:
            intent_detector: Intent detector instance (created if None).
            entity_extractor: Entity extractor instance (created if None).
            config: Optional configuration dictionary.
        """
        self._intent_detector = intent_detector or MedicalIntentDetector()
        self._entity_extractor = entity_extractor or MedicalEntityExtractor()
        self._config = config or {}

        # Settings
        self._enable_skip = self._config.get("enable_skip_logic", True)
        self._min_confidence = self._config.get("min_confidence_for_skip", 0.75)

        logger.info("NLURouter initialized")

    async def process(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> NLUResult:
        """Process message through NLU pipeline.

        Args:
            message: User message to process.
            context: Conversation context.

        Returns:
            NLUResult with combined analysis.
        """
        context = context or {}

        # Step 1: Detect intent
        intent_result = await self._intent_detector.detect(message, context)

        # Step 2: Extract entities
        entities = await self._entity_extractor.extract(message, context)

        # Step 3: Determine routing
        suggested_node = self._determine_suggested_node(intent_result, entities, context)

        # Step 4: Calculate skip nodes
        skip_nodes = self._calculate_skip_nodes(
            intent_result, entities, suggested_node, context
        )

        # Step 5: Build state updates
        state_updates = self._build_state_updates(intent_result, entities)

        # Step 6: Calculate overall confidence
        confidence = self._calculate_confidence(intent_result, entities)

        result = NLUResult(
            intent_result=intent_result,
            entities=entities,
            suggested_node=suggested_node,
            skip_nodes=skip_nodes,
            confidence=confidence,
            state_updates=state_updates,
            analysis={
                "intent_method": intent_result.method,
                "entities_found": list(entities.to_dict().keys()),
                "skip_enabled": self._enable_skip,
            },
        )

        logger.info(
            f"NLU processed: intent={result.intent}, "
            f"node={suggested_node}, skips={skip_nodes}"
        )

        return result

    def _determine_suggested_node(
        self,
        intent_result: MedicalIntentResult,
        entities: ExtractedEntities,
        context: dict[str, Any],
    ) -> str:
        """Determine the suggested next node.

        Args:
            intent_result: Intent detection result.
            entities: Extracted entities.
            context: Conversation context.

        Returns:
            Suggested node key.
        """
        intent = intent_result.intent

        # First check intent mapping
        base_node = INTENT_TO_NODE.get(intent)

        if base_node:
            return base_node

        # For selection intents, return to current flow
        if intent in {"confirm", "reject", "select_option", "provide_document"}:
            current_node = context.get("current_node")
            if current_node:
                return current_node

        # Special handling for specialty selection
        if intent == "select_specialty" or (
            intent == "book_appointment" and entities.specialty
        ):
            # If specialty is already known, skip to provider selection
            if entities.specialty:
                return "provider_selection"
            return "specialty_selection"

        # Handle date selection intent
        if intent == "select_date" and entities.date_value:
            return "time_selection"

        # Default to router for unknown
        return "router"

    def _calculate_skip_nodes(
        self,
        intent_result: MedicalIntentResult,
        entities: ExtractedEntities,
        suggested_node: str,
        context: dict[str, Any],
    ) -> list[str]:
        """Calculate which nodes can be skipped.

        Args:
            intent_result: Intent detection result.
            entities: Extracted entities.
            suggested_node: Currently suggested node.
            context: Conversation context.

        Returns:
            List of node keys that can be skipped.
        """
        if not self._enable_skip:
            return []

        # Only apply skip logic for high-confidence results
        if intent_result.confidence < self._min_confidence:
            return []

        skip_nodes: list[str] = []
        entities_dict = entities.to_dict()

        for node, required_entity in SKIP_CONDITIONS.items():
            # Check if entity is present
            if required_entity in entities_dict:
                # Don't skip if we're already past this node
                if node == suggested_node:
                    continue

                # Verify we would naturally go through this node
                if self._is_node_in_future_path(node, suggested_node):
                    skip_nodes.append(node)

        return skip_nodes

    def _is_node_in_future_path(
        self,
        node: str,
        current_node: str,
    ) -> bool:
        """Check if a node is in the future booking path.

        Args:
            node: Node to check.
            current_node: Current suggested node.

        Returns:
            True if node is in future path.
        """
        if node not in BOOKING_FLOW_SEQUENCE:
            return False

        if current_node not in BOOKING_FLOW_SEQUENCE:
            return True

        current_idx = BOOKING_FLOW_SEQUENCE.index(current_node)
        node_idx = BOOKING_FLOW_SEQUENCE.index(node)

        return node_idx > current_idx

    def _build_state_updates(
        self,
        intent_result: MedicalIntentResult,
        entities: ExtractedEntities,
    ) -> dict[str, Any]:
        """Build state updates from NLU results.

        Args:
            intent_result: Intent detection result.
            entities: Extracted entities.

        Returns:
            Dictionary of state updates.
        """
        updates: dict[str, Any] = {
            "detected_intent": intent_result.intent,
            "intent_confidence": intent_result.confidence,
            "nlu_method": intent_result.method,
        }

        # Add entity-based updates
        if entities.specialty_normalized:
            updates["selected_specialty"] = entities.specialty_normalized
        elif entities.specialty:
            updates["selected_specialty"] = entities.specialty

        if entities.date_value:
            updates["selected_date"] = entities.date_value.isoformat()
            updates["date_text"] = entities.date_text

        if entities.time_period:
            updates["time_preference"] = entities.time_period

        if entities.provider_name:
            updates["provider_search"] = entities.provider_name

        if entities.document:
            updates["patient_document"] = entities.document

        if entities.selection is not None:
            updates["user_selection"] = entities.selection

        return updates

    def _calculate_confidence(
        self,
        intent_result: MedicalIntentResult,
        entities: ExtractedEntities,
    ) -> float:
        """Calculate overall confidence score.

        Args:
            intent_result: Intent detection result.
            entities: Extracted entities.

        Returns:
            Overall confidence (0.0 to 1.0).
        """
        # Base confidence from intent
        confidence = intent_result.confidence

        # Boost confidence if entities support the intent
        if entities.has_entities:
            # Entity presence increases confidence
            entity_count = len(entities.to_dict())
            entity_boost = min(entity_count * 0.05, 0.15)
            confidence = min(confidence + entity_boost, 1.0)

        return confidence

    async def should_use_nlu(
        self,
        message: str,
        ctx: dict[str, Any] | None = None,
    ) -> bool:
        """Check if NLU should be used for this message.

        In hybrid mode, determines whether to use NLU or fall back to
        button/list selection based on context and message type.

        Args:
            message: User message.
            ctx: Conversation context.

        Returns:
            True if NLU should be used.
        """
        ctx = ctx or {}
        mode = self._config.get("interaction_mode", "hybrid")

        if mode == "nlu_only":
            return True

        if mode == "buttons_only":
            return False

        # Hybrid mode logic
        # Don't use NLU if awaiting specific input
        if ctx.get("awaiting_selection"):
            # But use NLU if message is not a number
            return not message.strip().isdigit()

        if ctx.get("awaiting_confirmation"):
            # Simple confirm/reject doesn't need full NLU
            return False

        # Use NLU for natural language input
        return len(message.split()) > 2 or not message.isdigit()


# =============================================================================
# Factory Function
# =============================================================================

def get_nlu_router(
    config: dict[str, Any] | None = None,
) -> NLURouter:
    """Factory function to create NLURouter.

    Args:
        config: Optional configuration.

    Returns:
        Configured NLURouter instance.
    """
    return NLURouter(config=config)
