"""
Excelencia Domain Agents

Agents and graph components for the Excelencia ERP domain.
Includes:
- ExcelenciaAgent: IAgent wrapper for company info, modules, mission/vision
- ExcelenciaInvoiceAgent: Client invoicing for Excelencia
- ExcelenciaPromotionsAgent: Software promotions for Excelencia
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

# Import new independent agents (NEW)
from .excelencia_invoice_agent import ExcelenciaInvoiceAgent
from .excelencia_promotions_agent import ExcelenciaPromotionsAgent
from .excelencia_support_agent import ExcelenciaSupportAgent

__all__ = [
    # Excelencia domain agents (independent agents for Orchestrator)
    "ExcelenciaAgent",  # Company info, modules, mission/vision
    "ExcelenciaInvoiceAgent",  # Client invoices
    "ExcelenciaPromotionsAgent",  # Software promotions
    "ExcelenciaSupportAgent",  # Software support/incidents
    # State
    "ExcelenciaState",
    "ExcelenciaDomainState",
    # Domain Nodes
    "ExcelenciaNode",
    # Graph (for internal use)
    "ExcelenciaGraph",
    "ExcelenciaDomainGraph",
    "ExcelenciaNodeType",
]
