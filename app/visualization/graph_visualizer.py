"""
Graph Visualizer - Creates visual representations of the LangGraph execution flow
"""

import graphviz
from typing import List, Optional, Set


class GraphVisualizer:
    """Visualizes the LangGraph multi-agent system as a directed graph"""

    # Color scheme
    COLORS = {
        "orchestrator": "#4A90E2",  # Blue
        "supervisor": "#50C878",  # Green
        "agent": "#F5A623",  # Orange
        "current": "#E74C3C",  # Red (current node)
        "visited": "#95A5A6",  # Gray (visited)
        "inactive": "#ECF0F1",  # Light gray (not visited)
    }

    def __init__(self):
        pass

    def create_graph_visualization(
        self,
        enabled_agents: List[str],
        current_node: Optional[str] = None,
        visited_nodes: Optional[Set[str]] = None,
    ) -> graphviz.Digraph:
        """
        Create a visual representation of the agent graph.

        Args:
            enabled_agents: List of enabled agent names
            current_node: Currently executing node (highlighted in red)
            visited_nodes: Set of visited nodes (highlighted in gray)

        Returns:
            Graphviz Digraph object
        """
        visited_nodes = visited_nodes or set()

        # Create directed graph
        dot = graphviz.Digraph(comment="Aynux Agent Graph")
        dot.attr(rankdir="TB")  # Top to bottom layout
        dot.attr("node", shape="box", style="rounded,filled", fontname="Arial")
        dot.attr("edge", fontname="Arial")

        # Add orchestrator node (entry point)
        orchestrator_color = self._get_node_color("orchestrator", current_node, visited_nodes)
        dot.node(
            "orchestrator",
            "🎯 Orchestrator\n(Entry Point)",
            fillcolor=orchestrator_color,
            shape="doubleoctagon",
        )

        # Add supervisor node
        supervisor_color = self._get_node_color("supervisor", current_node, visited_nodes)
        dot.node(
            "supervisor",
            "👁️ Supervisor\n(Quality Control)",
            fillcolor=supervisor_color,
            shape="diamond",
        )

        # Add agent nodes
        for agent in enabled_agents:
            agent_color = self._get_node_color(agent, current_node, visited_nodes)

            # Get agent icon and label
            icon, label = self._get_agent_display_info(agent)

            dot.node(agent, f"{icon} {label}", fillcolor=agent_color)

        # Add END node
        dot.node("END", "🏁 END", fillcolor=self.COLORS["inactive"], shape="oval")

        # Add edges
        self._add_edges(dot, enabled_agents, visited_nodes)

        return dot

    def _get_node_color(self, node: str, current_node: Optional[str], visited_nodes: Set[str]) -> str:
        """Get the color for a node based on its state"""
        if node == current_node:
            return self.COLORS["current"]
        elif node in visited_nodes:
            return self.COLORS["visited"]
        elif node == "orchestrator":
            return self.COLORS["orchestrator"]
        elif node == "supervisor":
            return self.COLORS["supervisor"]
        else:
            return self.COLORS["inactive"]

    def _get_agent_display_info(self, agent_name: str) -> tuple[str, str]:
        """Get icon and display label for an agent"""
        agent_info = {
            "greeting_agent": ("👋", "Greeting"),
            "product_agent": ("🛍️", "Product"),
            "data_insights_agent": ("📊", "Data Insights"),
            "promotions_agent": ("🎁", "Promotions"),
            "tracking_agent": ("📦", "Tracking"),
            "support_agent": ("🆘", "Support"),
            "invoice_agent": ("💰", "Invoice"),
            "excelencia_agent": ("🏢", "Excelencia"),
            "fallback_agent": ("❓", "Fallback"),
            "farewell_agent": ("👋", "Farewell"),
        }

        icon, label = agent_info.get(agent_name, ("🤖", agent_name.replace("_", " ").title()))
        return icon, label

    def _add_edges(self, dot: graphviz.Digraph, enabled_agents: List[str], visited_nodes: Set[str]):
        """Add edges between nodes"""
        # Orchestrator to agents
        for agent in enabled_agents:
            edge_color = "red" if agent in visited_nodes else "gray"
            dot.edge("orchestrator", agent, color=edge_color, penwidth="2" if agent in visited_nodes else "1")

        # Orchestrator to END
        dot.edge("orchestrator", "END", label="complete", color="gray", style="dashed")

        # Agents to supervisor (except greeting and farewell which go to END)
        for agent in enabled_agents:
            if agent in ["greeting_agent", "farewell_agent"]:
                edge_color = "red" if agent in visited_nodes else "gray"
                dot.edge(agent, "END", color=edge_color)
            else:
                edge_color = "red" if agent in visited_nodes else "gray"
                dot.edge(agent, "supervisor", color=edge_color, penwidth="2" if agent in visited_nodes else "1")

        # Supervisor to orchestrator (re-routing)
        dot.edge("supervisor", "orchestrator", label="continue", color="blue", style="dashed")

        # Supervisor to END
        dot.edge("supervisor", "END", label="complete", color="green", style="dashed")
