"""Graph builder for LangGraph StateGraph construction."""

import logging
from typing import TYPE_CHECKING, Any, Hashable, cast

from langgraph.graph import END, StateGraph

from app.core.graph.state_schema import LangGraphState
from app.core.schemas import AgentType, get_non_supervisor_agents

if TYPE_CHECKING:
    from app.core.graph.execution.node_executor import NodeExecutor
    from app.core.graph.routing.graph_router import GraphRouter

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Builder for LangGraph StateGraph construction.

    Responsible for:
    - Creating StateGraph with proper state schema
    - Adding agent nodes (orchestrator, supervisor, specialized)
    - Configuring conditional edges for routing
    """

    def __init__(
        self,
        enabled_agents: list[str],
        agents: dict[str, Any],
        executor: "NodeExecutor",
        router: "GraphRouter",
    ) -> None:
        """
        Initialize builder with dependencies.

        Args:
            enabled_agents: List of enabled agent names
            agents: Dictionary of initialized agent instances
            executor: Node executor for agent wrappers
            router: Graph router for conditional edges
        """
        self._enabled_agents = enabled_agents
        self._agents = agents
        self._executor = executor
        self._router = router

    def build(self) -> StateGraph:
        """
        Build the LangGraph StateGraph.

        Returns:
            Configured StateGraph ready for compilation
        """
        workflow = StateGraph(LangGraphState)

        # Add nodes
        self._add_nodes(workflow)

        # Configure entry point
        workflow.set_entry_point(AgentType.ORCHESTRATOR.value)

        # Add edges
        self._add_edges(workflow)

        return workflow

    def _add_nodes(self, workflow: StateGraph) -> None:
        """
        Add only enabled agent nodes to the workflow.

        Args:
            workflow: StateGraph to add nodes to
        """
        # Add orchestrator and supervisor nodes (always enabled)
        workflow.add_node(
            AgentType.ORCHESTRATOR.value, self._executor.execute_orchestrator
        )
        workflow.add_node(AgentType.SUPERVISOR.value, self._executor.execute_supervisor)

        # Add specialized agent nodes (only if enabled)
        for agent_type in get_non_supervisor_agents():
            agent_name = agent_type.value

            # Only add node if agent is enabled
            if agent_name in self._enabled_agents and agent_name in self._agents:
                # Create async wrapper function for each agent
                async def agent_executor(state: Any, name: str = agent_name) -> Any:
                    return await self._executor.execute_agent(state, name)

                workflow.add_node(agent_name, agent_executor)
                logger.debug(f"Added graph node for enabled agent: {agent_name}")
            else:
                logger.debug(f"Skipped graph node for disabled agent: {agent_name}")

    def _add_edges(self, workflow: StateGraph) -> None:
        """
        Configure edges only for enabled agents.

        Args:
            workflow: StateGraph to add edges to
        """
        # Orchestrator routing - only include enabled agents
        orchestrator_edges: dict[str, str] = {}
        for agent in get_non_supervisor_agents():
            if agent.value in self._enabled_agents and agent.value in self._agents:
                orchestrator_edges[agent.value] = agent.value
        orchestrator_edges["__end__"] = END

        workflow.add_conditional_edges(
            AgentType.ORCHESTRATOR.value,
            self._router.route_to_agent,
            cast(dict[Hashable, str], orchestrator_edges),
        )

        # Add edges only for enabled agents
        for agent_type in get_non_supervisor_agents():
            agent_name = agent_type.value

            # Only add edges for enabled agents
            if agent_name in self._enabled_agents and agent_name in self._agents:
                if agent_name == AgentType.GREETING_AGENT.value:
                    # Greeting agent goes directly to END (no supervisor needed)
                    workflow.add_edge(agent_name, END)
                else:
                    # Other agents route to supervisor
                    workflow.add_edge(agent_name, AgentType.SUPERVISOR.value)

        # Supervisor routing
        supervisor_edges: dict[str, str] = {
            "continue": AgentType.ORCHESTRATOR.value,
            "__end__": END,
        }

        workflow.add_conditional_edges(
            AgentType.SUPERVISOR.value,
            self._router.supervisor_should_continue,
            cast(dict[Hashable, str], supervisor_edges),
        )
