"""
Pharmacy Domain Agents - V2 Only

Contains the PharmacyOperationsAgent and its LangGraph implementation
for handling pharmacy debt workflows.

Graph Architecture:
- PharmacyGraphV2 with ~30 state fields
- 7 main nodes (router, auth_plex, debt_manager, payment_processor,
  account_switcher, info, response_formatter)
- Database-driven routing
- WhatsApp buttons/lists support
"""

from app.domains.pharmacy.agents.graph_v2 import (
    PharmacyGraphV2,
    create_pharmacy_graph_v2,
)
from app.domains.pharmacy.agents.pharmacy_operations_agent import (
    PharmacyOperationsAgent,
)
from app.domains.pharmacy.agents.state_v2 import (
    PharmacyStateV2,
    get_state_defaults,
)

# Aliases for compatibility
PharmacyGraph = PharmacyGraphV2
PharmacyState = PharmacyStateV2

__all__ = [
    # Agent entry point
    "PharmacyOperationsAgent",
    # Graph
    "PharmacyGraph",
    "PharmacyGraphV2",
    "create_pharmacy_graph_v2",
    # State
    "PharmacyState",
    "PharmacyStateV2",
    "get_state_defaults",
]
