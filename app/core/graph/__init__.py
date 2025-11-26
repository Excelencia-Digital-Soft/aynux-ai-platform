"""
Graph infrastructure for LangGraph multi-agent system.

This module provides:
- AynuxGraph: Main graph orchestrator
- LangGraphState: TypedDict state schema
- NodeExecutor: Agent execution wrapper
- GraphRouter: Routing logic
- AgentFactory: Agent instantiation
"""

from app.core.graph.state_schema import GraphState, LangGraphState

__all__ = [
    "AynuxGraph",
    "LangGraphState",
    "GraphState",
]


def __getattr__(name):
    """Lazy import for AynuxGraph to avoid circular imports."""
    if name == "AynuxGraph":
        from app.core.graph.graph import AynuxGraph
        return AynuxGraph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
