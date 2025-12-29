"""
Router for managing agent flow and decision making.

Supports multi-tenant agent filtering when TenantContext is available.
When a tenant has specific enabled_agent_types configured, only those
agents will be routable (intersection with global enabled_agents).

Enhanced with TenantAgentRegistry support for database-driven agent configuration:
- Keywords and priority from tenant_agents table
- Intent patterns for routing decisions
- Custom agent configurations per tenant
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from app.core.graph.state_schema import LangGraphState
from app.core.schemas import AgentType, get_agent_routing_literal
from app.core.tenancy.agent_factory import TenantAgentFactory
from app.core.tenancy.context import get_tenant_context
from app.core.utils.tracing import trace_sync_method

if TYPE_CHECKING:
    from app.core.schemas.tenant_agent_config import TenantAgentRegistry

logger = logging.getLogger(__name__)


class GraphRouter:
    """
    Handles routing decisions and flow control in the graph.

    Supports multi-tenant agent filtering:
    - When TenantContext is active, uses TenantAgentFactory to filter agents
    - Falls back to global enabled_agents when no tenant context

    Enhanced with TenantAgentRegistry for database-driven configuration:
    - Uses keywords and intent_patterns from tenant_agents table
    - Priority-based agent selection when multiple matches
    - Custom configurations per tenant
    """

    def __init__(
        self,
        enabled_agents: list[str] | None = None,
        tenant_registry: TenantAgentRegistry | None = None,
    ):
        """
        Initialize router with enabled agents configuration.

        Args:
            enabled_agents: List of enabled agent names (excluding orchestrator/supervisor)
                           Used as fallback when no tenant context is available.
            tenant_registry: Optional TenantAgentRegistry for database-driven config.
                           When provided, uses registry for agent lookup and routing.
        """
        self.max_errors = 3
        self.max_routing_attempts = 3
        self.max_supervisor_retries = 3
        self.enabled_agents = enabled_agents or []
        self._tenant_registry = tenant_registry
        logger.info(f"GraphRouter initialized with {len(self.enabled_agents)} enabled agents")
        if tenant_registry:
            logger.info(
                f"GraphRouter using TenantAgentRegistry for org {tenant_registry.organization_id}"
            )

    @property
    def tenant_registry(self) -> TenantAgentRegistry | None:
        """Get the tenant agent registry if available."""
        return self._tenant_registry

    def set_tenant_registry(self, registry: TenantAgentRegistry) -> None:
        """
        Set the tenant registry for database-driven routing.

        Args:
            registry: TenantAgentRegistry to use for routing decisions.
        """
        self._tenant_registry = registry
        logger.debug(f"Set tenant registry for org {registry.organization_id}")

    def get_effective_enabled_agents(self) -> list[str]:
        """
        Get the effective list of enabled agents for the current request.

        Priority:
        1. If TenantAgentRegistry is set, use it directly
        2. In multi-tenant mode with TenantContext, uses TenantAgentFactory
        3. Otherwise, uses global enabled_agents

        Returns:
            List of enabled agent names for the current context.
        """
        # Priority 1: Use TenantAgentRegistry if available
        if self._tenant_registry is not None:
            enabled = [
                agent.agent_key
                for agent in self._tenant_registry.get_enabled_agents()
            ]
            logger.debug(
                f"[ROUTING] Using TenantAgentRegistry: {len(enabled)} enabled agents"
            )
            return enabled

        # Priority 2: Multi-tenant mode with TenantContext
        ctx = get_tenant_context()

        if ctx and ctx.is_multi_tenant_mode:
            # Multi-tenant mode: use TenantAgentFactory for filtered agents
            factory = TenantAgentFactory.from_context()
            tenant_agents = factory.get_enabled_agents()
            logger.debug(
                f"[ROUTING] Tenant-aware agents for org={ctx.organization_id}: {tenant_agents}"
            )
            return tenant_agents

        # Priority 3: Generic mode: use global enabled agents
        return self.enabled_agents

    def get_agent_for_intent(self, intent: str) -> str | None:
        """
        Get the agent that handles a specific intent using tenant registry.

        Falls back to None if no registry or no mapping found.

        Args:
            intent: Intent name (e.g., "saludo", "producto")

        Returns:
            Agent key or None if not found.
        """
        if self._tenant_registry is None:
            return None
        return self._tenant_registry.get_agent_for_intent(intent)

    def get_agents_for_keyword(self, keyword: str) -> list[str]:
        """
        Get agents that might handle a message containing a keyword.

        Uses tenant registry's keyword index for matching.

        Args:
            keyword: Keyword to match

        Returns:
            List of agent keys that have this keyword configured.
        """
        if self._tenant_registry is None:
            return []
        return self._tenant_registry.get_agents_for_keyword(keyword)

    def get_agent_config(self, agent_key: str) -> dict | None:
        """
        Get configuration for a specific agent from the registry.

        Args:
            agent_key: Agent key (e.g., "greeting_agent")

        Returns:
            Agent configuration dict or None if not found.
        """
        if self._tenant_registry is None:
            return None
        agent = self._tenant_registry.get_agent(agent_key)
        return agent.config if agent else None

    def check_bypass_routing(self, state: LangGraphState) -> str | None:
        """
        Check if request should bypass orchestrator based on tenant config.

        Checks bypass rules in TenantConfig.advanced_config:
        1. Phone number patterns/lists
        2. WhatsApp phone_number_id

        Also checks if bypass_target_agent was set in the registry
        (by webhook.py when a bypass rule matched pre-routing).

        Returns:
            Target agent name if bypass applies, None otherwise
        """
        # FIRST: Check if bypass_target_agent was set in registry (from webhook pre-routing)
        if self._tenant_registry and self._tenant_registry.bypass_target_agent:
            logger.info(
                f"[BYPASS] Using pre-routed bypass agent: {self._tenant_registry.bypass_target_agent}"
            )
            return self._tenant_registry.bypass_target_agent

        # Get tenant context
        ctx = get_tenant_context()
        if not ctx or not ctx.config:
            return None

        # Get bypass config from advanced_config
        advanced = ctx.config.advanced_config or {}
        bypass_config = advanced.get("bypass_routing", {})

        if not bypass_config.get("enabled", False):
            return None

        rules = bypass_config.get("rules", [])

        # Extract identifiers from state
        phone_number = state.get("user_id") or state.get("customer_id")
        whatsapp_phone_id = state.get("whatsapp_phone_number_id")

        for rule in rules:
            rule_type = rule.get("type")
            target_agent = rule.get("target_agent")

            if not target_agent:
                continue

            if rule_type == "phone_number":
                pattern = rule.get("pattern", "")
                if self._match_phone_pattern(phone_number, pattern):
                    logger.info(
                        f"[BYPASS] Phone pattern match: {phone_number} -> {target_agent}"
                    )
                    return target_agent

            elif rule_type == "phone_number_list":
                phone_list = rule.get("phone_numbers", [])
                if phone_number in phone_list:
                    logger.info(
                        f"[BYPASS] Phone list match: {phone_number} -> {target_agent}"
                    )
                    return target_agent

            elif rule_type == "whatsapp_phone_number_id":
                config_id = rule.get("phone_number_id")
                if whatsapp_phone_id == config_id:
                    logger.info(
                        f"[BYPASS] WhatsApp ID match: {whatsapp_phone_id} -> {target_agent}"
                    )
                    return target_agent

        return None

    def _match_phone_pattern(self, phone: str | None, pattern: str) -> bool:
        """
        Match phone number against pattern with wildcard support.

        Args:
            phone: Phone number to match
            pattern: Pattern to match against (supports * wildcard at end)

        Returns:
            True if matches, False otherwise
        """
        if not phone or not pattern:
            return False

        # Simple wildcard matching (* at end)
        if pattern.endswith("*"):
            return phone.startswith(pattern[:-1])

        return phone == pattern

    @trace_sync_method(
        name="route_to_agent", run_type="chain", metadata={"operation": "agent_selection", "component": "router"}
    )
    def route_to_agent(self, state: LangGraphState) -> str:
        """
        Determine which agent to route to based on orchestrator analysis.

        Validates that the target agent is both valid and enabled. If the agent
        is disabled, routes to fallback_agent instead.

        Supports multi-tenant filtering:
        - In multi-tenant mode, checks tenant's enabled_agent_types
        - Falls back to global enabled_agents otherwise

        Args:
            state: Current graph state

        Returns:
            Name of next node or "__end__"
        """
        # Check completion conditions
        if state.get("is_complete") or state.get("human_handoff_requested"):
            logger.info("[ROUTING] Ending due to completion or human handoff")
            return "__end__"

        # Get next agent from state
        next_agent = state.get("next_agent")

        if not next_agent:
            logger.warning("[ROUTING] No next_agent in state, routing to fallback")
            return AgentType.FALLBACK_AGENT.value

        # Validate agent exists in enum
        valid_agents = get_agent_routing_literal()
        # Orchestrator and supervisor are always valid, but not in the routing literal
        valid_agents.extend([AgentType.ORCHESTRATOR.value, AgentType.SUPERVISOR.value])
        if next_agent not in valid_agents:
            logger.warning(f"[ROUTING] Invalid agent '{next_agent}', routing to fallback")
            return AgentType.FALLBACK_AGENT.value

        # Check if agent is enabled (this check is now implicitly covered by the effective_enabled list)
        effective_enabled = self.get_effective_enabled_agents()
        # System agents are always considered enabled for routing purposes
        system_agents = [AgentType.ORCHESTRATOR.value, AgentType.SUPERVISOR.value]

        if next_agent not in effective_enabled and next_agent not in system_agents:
            ctx = get_tenant_context()
            if ctx and ctx.is_multi_tenant_mode:
                logger.warning(
                    f"[ROUTING] Agent '{next_agent}' disabled for tenant {ctx.organization_id}, "
                    f"routing to fallback. Tenant agents: {effective_enabled}"
                )
            else:
                logger.warning(
                    f"[ROUTING] Agent '{next_agent}' is disabled globally, routing to fallback. "
                    f"Enabled agents: {effective_enabled}"
                )
            return AgentType.FALLBACK_AGENT.value

        logger.info(f"[ROUTING] Routing to enabled agent: {next_agent}")
        return next_agent

    @trace_sync_method(
        name="supervisor_should_continue",
        run_type="chain",
        metadata={"operation": "supervisor_flow_decision", "component": "router"},
    )
    def supervisor_should_continue(self, state: LangGraphState) -> Literal["continue", "__end__"]:
        """
        Determine if supervisor should continue or end conversation.

        Args:
            state: Current graph state

        Returns:
            "continue" to re-route or "__end__" to terminate
        """
        # Check completion flags
        if state.get("is_complete"):
            logger.info("Supervisor: Conversation complete")
            return "__end__"

        if state.get("human_handoff_requested"):
            logger.info("Supervisor: Human handoff requested")
            return "__end__"

        # Check re-routing needs
        if state.get("needs_re_routing"):
            routing_attempts = state.get("routing_attempts", 0)
            supervisor_retry_count = state.get("supervisor_retry_count", 0)

            if routing_attempts >= self.max_routing_attempts or supervisor_retry_count >= self.max_supervisor_retries:
                logger.warning(
                    f"Supervisor: Max attempts reached (routing: {routing_attempts}, retries: {supervisor_retry_count})"
                )
                return "__end__"

            logger.info("Supervisor: Re-routing needed")
            return "continue"

        # Check error count
        error_count = state.get("error_count", 0)
        if error_count >= self.max_errors:
            logger.warning(f"Supervisor: Too many errors ({error_count})")
            return "__end__"

        # Check conversation flow decision
        conversation_flow = state.get("conversation_flow") or {}
        flow_decision = conversation_flow.get("decision_type")

        if flow_decision in ["conversation_complete", "conversation_end", "human_handoff", "error_end"]:
            logger.info(f"Supervisor: Flow decision '{flow_decision}', ending")
            return "__end__"

        if flow_decision == "re_route":
            logger.info("Supervisor: Re-route decision")
            return "continue"

        # Default: end if response was satisfactory
        logger.info("Supervisor: Response satisfactory, ending")
        return "__end__"

    @trace_sync_method(
        name="should_continue", run_type="chain", metadata={"operation": "continuation_decision", "component": "router"}
    )
    def should_continue(self, state: LangGraphState) -> Literal["continue", "__end__"]:
        """
        Generic continuation decision (deprecated, kept for compatibility).

        Args:
            state: Current graph state

        Returns:
            "continue" or "__end__"
        """
        if state.get("is_complete"):
            logger.info("Conversation marked as complete")
            return "__end__"

        if state.get("human_handoff_requested"):
            logger.info("Human handoff requested")
            return "__end__"

        error_count = state.get("error_count", 0)
        if error_count >= self.max_errors:
            logger.warning(f"Too many errors ({error_count})")
            return "__end__"

        return "continue"
