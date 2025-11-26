"""
Excelencia Domain Agents

Agents and graph components for the Excelencia ERP domain.
Includes:
- ExcelenciaAgent: IAgent wrapper for SuperOrchestrator integration
- ExcelenciaGraph: LangGraph StateGraph for Excelencia
- ExcelenciaState: TypedDict state schema
- ExcelenciaNode: Main node for ERP queries
"""

# Import state first (no dependencies)
from .state import ExcelenciaDomainState, ExcelenciaState

# Import nodes (depends on base agent)
from .nodes import ExcelenciaNode

# Import graph (depends on nodes and state)
from .graph import ExcelenciaDomainGraph, ExcelenciaGraph, ExcelenciaNodeType

# Import IAgent wrapper (depends on graph)
from .excelencia_agent import ExcelenciaAgent

__all__ = [
    # Agent (IAgent implementation for SuperOrchestrator)
    "ExcelenciaAgent",
    # State
    "ExcelenciaState",
    "ExcelenciaDomainState",
    # Domain Nodes
    "ExcelenciaNode",
    # Graph
    "ExcelenciaGraph",
    "ExcelenciaDomainGraph",
    "ExcelenciaNodeType",
]
