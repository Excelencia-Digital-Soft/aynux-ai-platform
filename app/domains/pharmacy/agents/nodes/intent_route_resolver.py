"""
Intent Route Resolver - Maps intent analysis to routing decisions.

This class bridges PharmacyIntentAnalyzer with RouterSupervisor,
converting intent analysis results into routing state updates.

Responsibilities:
- Call PharmacyIntentAnalyzer for intent detection
- Map detected intent to target node
- Handle unknown/out-of-scope intents
- Check authentication requirements
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.cache.routing_config_cache import routing_config_cache
from app.domains.pharmacy.agents.intent_analyzer import (
    PharmacyIntentAnalyzer,
    get_pharmacy_intent_analyzer,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domains.pharmacy.agents.intent_result import PharmacyIntentResult
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


class IntentRouteResolver:
    """
    Resolves user intent to routing decisions using hybrid spaCy + LLM analysis.

    This class is responsible for:
    1. Analyzing user messages with PharmacyIntentAnalyzer
    2. Mapping detected intents to target nodes (from database config)
    3. Handling unknown/out-of-scope intents gracefully
    4. Checking authentication requirements for intents

    Usage:
        resolver = IntentRouteResolver(db_session)
        result = await resolver.resolve(message, state, org_id)
        # result contains intent, next_node, and state updates
    """

    def __init__(self, db: "AsyncSession") -> None:
        """
        Initialize resolver with database session.

        Args:
            db: AsyncSession for database operations
        """
        self._db = db
        self._analyzer: PharmacyIntentAnalyzer | None = None
        self._intent_node_mapping: dict[str, tuple[str, bool]] | None = None

    def _get_analyzer(self) -> PharmacyIntentAnalyzer:
        """Get or create intent analyzer (lazy initialization)."""
        if self._analyzer is None:
            self._analyzer = get_pharmacy_intent_analyzer(
                db=self._db,
                use_llm_fallback=True,
            )
        return self._analyzer

    async def _load_intent_mappings(self, org_id: UUID | None) -> None:
        """Load intent-to-node mappings from database cache."""
        if self._intent_node_mapping is not None:
            return

        configs = await routing_config_cache.get_configs(self._db, org_id, "pharmacy")
        self._intent_node_mapping = {}

        for config in configs.get("intent_node_mapping", []):
            intent = config.trigger_value
            node = config.target_node or "main_menu_node"
            requires_auth = config.requires_auth
            self._intent_node_mapping[intent] = (node, requires_auth)

    async def resolve(
        self,
        message: str,
        state: "PharmacyStateV2",
        org_id: UUID | None,
    ) -> dict[str, Any]:
        """
        Resolve user message intent to routing decision.

        Uses hybrid spaCy + LLM analysis for intelligent intent detection,
        then maps the result to appropriate routing state updates.

        Args:
            message: User message to analyze
            state: Current conversation state
            org_id: Organization ID for multi-tenant patterns

        Returns:
            State update dict with:
            - intent: Detected intent key
            - previous_intent: Previous intent (for context)
            - next_node: Target node to route to
            - awaiting_input: Cleared (routing to new flow)
            - extracted_entities: Any entities extracted (amount, dni, etc.)
        """
        await self._load_intent_mappings(org_id)

        # Build context for analyzer
        context = self._build_context(state)

        # Analyze with hybrid spaCy + LLM analyzer
        analyzer = self._get_analyzer()
        result = await analyzer.analyze(
            message=message,
            context=context,
            db=self._db,
            organization_id=org_id,
        )

        logger.info(
            f"Intent analysis: intent={result.intent}, " f"confidence={result.confidence:.2f}, method={result.method}"
        )

        # Handle out-of-scope / unknown intents
        if result.is_out_of_scope or result.intent == "unknown":
            return self._handle_unknown_intent(state)

        # Map intent to routing decision
        return self._map_intent_to_route(result, state)

    def _build_context(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """Build context dict for intent analyzer."""
        return {
            "customer_identified": state.get("is_authenticated", False),
            "awaiting_confirmation": state.get("awaiting_payment_confirmation", False),
            "debt_status": "has_debt" if (state.get("total_debt") or 0) > 0 else "no_debt",
            "conversation_history": self._get_recent_messages(state),
        }

    def _get_recent_messages(self, state: "PharmacyStateV2", limit: int = 5) -> str:
        """Extract recent conversation for context."""
        messages = state.get("messages", [])
        if not messages:
            return ""
        recent = messages[-limit:]
        parts = []
        for m in recent:
            if hasattr(m, "content") and hasattr(m, "type"):
                role = "Usuario" if m.type == "human" else "Bot"
                parts.append(f"{role}: {m.content}")
        return "\n".join(parts)

    def _map_intent_to_route(
        self,
        result: "PharmacyIntentResult",
        state: "PharmacyStateV2",
    ) -> dict[str, Any]:
        """Map intent analysis result to routing decision."""
        intent = result.intent
        current_intent = state.get("intent")

        # Get node and auth requirement from database config
        target_node = "main_menu_node"
        requires_auth = False

        if self._intent_node_mapping and intent in self._intent_node_mapping:
            target_node, requires_auth = self._intent_node_mapping[intent]

        # Check authentication requirement
        if requires_auth and not state.get("is_authenticated"):
            return {
                "intent": intent,
                "previous_intent": current_intent,
                "next_node": "auth_plex",
                "awaiting_input": None,
            }

        updates: dict[str, Any] = {
            "intent": intent,
            "previous_intent": current_intent,
            "next_node": target_node,
            "awaiting_input": None,
        }

        # Pass entities if extracted (amount, dni, etc.)
        if result.entities:
            updates["extracted_entities"] = result.entities

        return updates

    def _handle_unknown_intent(
        self,
        state: "PharmacyStateV2",
    ) -> dict[str, Any]:
        """Handle unknown or out-of-scope intents."""
        # Route to main menu for authenticated users
        if state.get("is_authenticated"):
            return {
                "intent": "show_menu",
                "next_node": "main_menu_node",
            }
        # Route to greeting/auth for unauthenticated
        return {
            "intent": "greeting",
            "next_node": "auth_plex",
        }
