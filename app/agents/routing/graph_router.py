"""
Router for managing agent flow and decision making
"""

import logging
from typing import Literal

from ..schemas import AgentType, get_agent_routing_literal
from ..state_schema import LangGraphState
from ..utils.tracing import trace_sync_method

logger = logging.getLogger(__name__)


class GraphRouter:
    """Handles routing decisions and flow control in the graph"""

    def __init__(self, enabled_agents: list[str] = None):
        """
        Initialize router with enabled agents configuration.

        Args:
            enabled_agents: List of enabled agent names (excluding orchestrator/supervisor)
        """
        self.max_errors = 3
        self.max_routing_attempts = 3
        self.max_supervisor_retries = 3
        self.enabled_agents = enabled_agents or []
        logger.info(f"GraphRouter initialized with {len(self.enabled_agents)} enabled agents")

    @trace_sync_method(
        name="route_to_agent", run_type="chain", metadata={"operation": "agent_selection", "component": "router"}
    )
    def route_to_agent(self, state: LangGraphState) -> str:
        """
        Determine which agent to route to based on orchestrator analysis.

        Validates that the target agent is both valid and enabled. If the agent
        is disabled, routes to fallback_agent instead.

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
        if next_agent not in valid_agents:
            logger.warning(f"[ROUTING] Invalid agent '{next_agent}', routing to fallback")
            return AgentType.FALLBACK_AGENT.value

        # Check if agent is enabled (orchestrator and supervisor always pass)
        if next_agent not in [AgentType.ORCHESTRATOR.value, AgentType.SUPERVISOR.value]:
            if next_agent not in self.enabled_agents:
                logger.warning(
                    f"[ROUTING] Agent '{next_agent}' is disabled, routing to fallback. "
                    f"Enabled agents: {self.enabled_agents}"
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
        conversation_flow = state.get("conversation_flow", {})
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
