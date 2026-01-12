"""Intent validation and agent mapping.

Extracted from IntentRouter to follow Single Responsibility Principle.
Handles intent validation, agent mapping, and multi-turn flow detection.

Now supports database-driven configuration via IntentConfigCache:
- Intent mappings loaded from core.intent_agent_mappings
- Flow agents loaded from core.flow_agent_configs
- Keyword mappings loaded from core.keyword_agent_mappings

Falls back to hardcoded values when database is not available or empty.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.schemas import get_intent_to_agent_mapping, get_valid_intents

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class IntentValidator:
    """Validates intents and maps them to agents.

    Responsibilities:
    - Validate intents against schema
    - Map agent names to intent names (LLM correction)
    - Map intents to target agents
    - Detect active multi-turn flows

    Configuration Sources (priority order):
    1. Database via IntentConfigCache (multi-tenant, per-organization)
    2. Hardcoded defaults (fallback)
    """

    # ==========================================================================
    # HARDCODED DEFAULTS (fallback when DB is empty or unavailable)
    # ==========================================================================

    # Mapping from agent names to valid intents
    # Used when LLM returns agent name instead of intent name
    AGENT_TO_INTENT_MAPPING: dict[str, str] = {
        "excelencia_agent": "excelencia",
        "excelencia_support_agent": "excelencia_soporte",
        "excelencia_invoice_agent": "excelencia_facturacion",
        "excelencia_promotions_agent": "excelencia_promociones",
        "support_agent": "soporte",
        "greeting_agent": "saludo",
        "fallback_agent": "fallback",
        "farewell_agent": "despedida",
        "product_agent": "producto",
        "ecommerce_agent": "ecommerce",
        "data_insights_agent": "datos",
        "pharmacy_operations_agent": "pharmacy",
    }

    # Agents with multi-turn conversational flows
    FLOW_AGENTS: set[str] = {
        "excelencia_support_agent",  # 3-step incident creation
        "excelencia_invoice_agent",  # Invoice lookup flow
        "pharmacy_operations_agent",  # Pharmacy operations
    }

    # Keyword-based routing for fallback scenarios
    # Used when follow_up is detected but no previous agent exists
    KEYWORD_TO_AGENT: dict[str, list[str]] = {
        "pharmacy_operations_agent": [
            "receta", "medicamento", "farmacia", "medicamentos", "pedido farmacia",
            "deuda farmacia", "urgente receta", "envié receta", "mandé receta",
        ],
        "excelencia_support_agent": [
            "problema", "error", "falla", "no funciona", "ayuda", "soporte",
            "incidente", "bug", "ticket",
        ],
        "excelencia_invoice_agent": [
            "factura", "facturación", "cobro", "pago", "cuenta", "deuda",
        ],
        "greeting_agent": [
            "hola", "buenos días", "buenas tardes", "buenas noches", "hi", "hello",
        ],
        "farewell_agent": [
            "adiós", "chao", "bye", "hasta luego", "gracias", "nos vemos",
        ],
    }

    # ==========================================================================
    # INSTANCE STATE (loaded from cache/DB)
    # ==========================================================================

    def __init__(self) -> None:
        """Initialize with empty runtime caches."""
        # Runtime mappings (loaded from DB, per-organization)
        self._org_intent_mappings: dict[UUID, dict[str, str]] = {}
        self._org_flow_agents: dict[UUID, set[str]] = {}
        self._org_keyword_mappings: dict[UUID, dict[str, list[str]]] = {}

    # ==========================================================================
    # ASYNC LOADING FROM CACHE
    # ==========================================================================

    async def load_from_cache(
        self,
        db: "AsyncSession",
        organization_id: UUID,
    ) -> None:
        """
        Load all intent configurations from cache for an organization.

        This pre-loads the cache to avoid async calls during validation.
        Should be called at the start of request processing.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
        """
        from app.core.cache.intent_config_cache import intent_config_cache

        try:
            # Load all three types in parallel
            configs = await intent_config_cache.get_all_configs(db, organization_id)

            # Store in instance caches (filter out internal keys)
            intent_mappings = {
                k: v for k, v in configs["intent_mappings"].items()
                if not k.startswith("_")
            }

            if intent_mappings:
                self._org_intent_mappings[organization_id] = intent_mappings
                logger.debug(
                    f"Loaded {len(intent_mappings)} intent mappings for org {organization_id}"
                )

            flow_agents = set(configs["flow_agents"])
            if flow_agents:
                self._org_flow_agents[organization_id] = flow_agents
                logger.debug(
                    f"Loaded {len(flow_agents)} flow agents for org {organization_id}"
                )

            keyword_mappings = configs["keyword_mappings"]
            if keyword_mappings:
                self._org_keyword_mappings[organization_id] = keyword_mappings
                logger.debug(
                    f"Loaded keyword mappings for {len(keyword_mappings)} agents for org {organization_id}"
                )

        except Exception as e:
            logger.warning(
                f"Failed to load intent configs from cache for org {organization_id}: {e}. "
                "Using hardcoded defaults."
            )

    def clear_org_cache(self, organization_id: UUID) -> None:
        """Clear cached configurations for an organization."""
        self._org_intent_mappings.pop(organization_id, None)
        self._org_flow_agents.pop(organization_id, None)
        self._org_keyword_mappings.pop(organization_id, None)

    # ==========================================================================
    # GETTERS (with fallback to hardcoded)
    # ==========================================================================

    def get_intent_mappings(self, organization_id: UUID | None = None) -> dict[str, str]:
        """Get intent-to-agent mappings for an organization (or defaults)."""
        if organization_id and organization_id in self._org_intent_mappings:
            return self._org_intent_mappings[organization_id]
        return self.AGENT_TO_INTENT_MAPPING

    def get_flow_agents(self, organization_id: UUID | None = None) -> set[str]:
        """Get flow agent keys for an organization (or defaults)."""
        if organization_id and organization_id in self._org_flow_agents:
            return self._org_flow_agents[organization_id]
        return self.FLOW_AGENTS

    def get_keyword_mappings(self, organization_id: UUID | None = None) -> dict[str, list[str]]:
        """Get keyword-to-agent mappings for an organization (or defaults)."""
        if organization_id and organization_id in self._org_keyword_mappings:
            return self._org_keyword_mappings[organization_id]
        return self.KEYWORD_TO_AGENT

    # ==========================================================================
    # VALIDATION AND MAPPING
    # ==========================================================================

    def validate_and_map_intent(
        self,
        intent: str,
        valid_intents: set[str] | None = None,
        organization_id: UUID | None = None,
    ) -> tuple[str, float, str]:
        """Validate intent and map if needed.

        Args:
            intent: Intent from LLM response
            valid_intents: Set of valid intents (defaults to schema intents + follow_up)
            organization_id: Optional tenant UUID for org-specific mappings

        Returns:
            Tuple of (validated_intent, confidence, reasoning)
        """
        if valid_intents is None:
            valid_intents = set(get_valid_intents()) | {"follow_up"}

        # Check if already valid
        if intent in valid_intents:
            return intent, 1.0, "Valid intent"

        # Try mapping agent name to intent
        agent_to_intent = self.get_intent_mappings(organization_id)
        mapped_intent = agent_to_intent.get(intent)
        if mapped_intent and mapped_intent in valid_intents:
            logger.info(f"Mapped agent name '{intent}' to intent '{mapped_intent}'")
            return mapped_intent, 0.9, f"Mapped from agent name '{intent}'"

        # Invalid intent - fallback
        logger.warning(f"Invalid intent detected: {intent}. Using fallback intent.")
        return "fallback", 0.4, "LLM returned an invalid intent"

    def map_intent_to_agent(self, intent: str) -> str:
        """Map intent to target agent.

        Args:
            intent: Validated intent name

        Returns:
            Agent name to route to
        """
        mapping = get_intent_to_agent_mapping()
        agent = mapping.get(intent, "fallback_agent")
        logger.debug(f"Mapping intent '{intent}' to agent '{agent}'")
        return agent

    def check_active_flow(
        self,
        conversation_data: dict[str, Any] | None,
        organization_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """Check if previous agent has an active flow that should continue.

        This prevents routing away from agents during multi-step flows like:
        - excelencia_support_agent: incident creation (description → priority → confirm)
        - excelencia_invoice_agent: invoice lookup flow
        - pharmacy_operations_agent: pharmacy operations

        Args:
            conversation_data: Conversation context dict
            organization_id: Optional tenant UUID for org-specific flow agents

        Returns:
            Flow continuation result if active flow detected, None otherwise
        """
        if not conversation_data:
            return None

        previous_agent = conversation_data.get("previous_agent")

        # Skip if no previous agent or if it was orchestrator/supervisor
        if not previous_agent or previous_agent in ("orchestrator", "supervisor"):
            return None

        flow_agents = self.get_flow_agents(organization_id)
        if previous_agent in flow_agents:
            logger.info(f"Active flow detected, continuing with {previous_agent}")
            return {
                "primary_intent": "follow_up",
                "intent": "follow_up",
                "confidence": 0.95,
                "target_agent": previous_agent,
                "requires_handoff": False,
                "entities": {},
                "method": "flow_continuation",
                "reasoning": f"Continuing active flow with {previous_agent}",
            }

        return None

    def _try_keyword_routing(
        self,
        message: str,
        organization_id: UUID | None = None,
    ) -> str | None:
        """Try to route based on keywords in the message.

        This is used as a fallback when follow_up is detected but there's
        no previous agent to route to. Instead of going to fallback_agent,
        we try to match keywords to find an appropriate agent.

        Args:
            message: User message text
            organization_id: Optional tenant UUID for org-specific keywords

        Returns:
            Agent name if keywords match, None otherwise
        """
        if not message:
            return None

        message_lower = message.lower()
        keyword_mappings = self.get_keyword_mappings(organization_id)

        # Check each agent's keywords
        for agent, keywords in keyword_mappings.items():
            for keyword in keywords:
                if keyword in message_lower:
                    logger.info(f"Keyword '{keyword}' matched, routing to {agent}")
                    return agent

        return None

    def handle_follow_up_intent(
        self,
        conversation_data: dict[str, Any] | None,
        organization_id: UUID | None = None,
    ) -> str:
        """Determine target agent for follow_up intent.

        When follow_up is detected but no previous agent exists (e.g., new
        conversation misclassified as follow_up), tries keyword-based routing
        before falling back.

        Args:
            conversation_data: Conversation context
            organization_id: Optional tenant UUID for org-specific keywords

        Returns:
            Target agent name
        """
        if not conversation_data:
            return "fallback_agent"

        previous_agent = conversation_data.get("previous_agent")
        if previous_agent and previous_agent not in ("orchestrator", None):
            logger.info(f"Follow-up detected, routing to previous agent: {previous_agent}")
            return previous_agent

        # No previous agent - this might be a misclassification
        # Try keyword-based routing before defaulting to fallback
        message = conversation_data.get("message", "")
        if message:
            keyword_agent = self._try_keyword_routing(message, organization_id)
            if keyword_agent:
                logger.info(f"Follow-up reclassified via keywords to: {keyword_agent}")
                return keyword_agent

        logger.warning("Follow-up detected but no previous agent and no keyword match, using fallback")
        return "fallback_agent"

    def is_flow_agent(self, agent_key: str, organization_id: UUID | None = None) -> bool:
        """Check if an agent is a flow agent.

        Args:
            agent_key: Agent key to check
            organization_id: Optional tenant UUID for org-specific flow agents

        Returns:
            True if the agent has multi-turn flows
        """
        return agent_key in self.get_flow_agents(organization_id)


# Singleton instance for backward compatibility
# Use intent_validator.load_from_cache(db, org_id) to load org-specific configs
intent_validator = IntentValidator()
