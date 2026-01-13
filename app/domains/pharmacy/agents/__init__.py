"""
Pharmacy Domain Agents

Contains the PharmacyOperationsAgent and its LangGraph implementation
for handling pharmacy debt workflows.

Version Support:
- V1 (default): PharmacyGraph with ~90 state fields, 15+ nodes
- V2 (USE_PHARMACY_V2=true): PharmacyGraphV2 with ~30 state fields, 6 nodes

The agent automatically selects the appropriate graph based on the
USE_PHARMACY_V2 feature flag in settings.
"""

from app.domains.pharmacy.agents.pharmacy_operations_agent import (
    PharmacyOperationsAgent,
)

# V2 Exports (available when USE_PHARMACY_V2=true)
from app.domains.pharmacy.agents.graph_v2 import (
    PharmacyGraphV2,
    create_pharmacy_graph_v2,
)
from app.domains.pharmacy.agents.state_v2 import (
    PharmacyStateV2,
    get_state_defaults,
    migrate_v1_to_v2,
)

__all__ = [
    # Agent entry point (supports both V1 and V2)
    "PharmacyOperationsAgent",
    # V2 Graph
    "PharmacyGraphV2",
    "create_pharmacy_graph_v2",
    # V2 State
    "PharmacyStateV2",
    "get_state_defaults",
    "migrate_v1_to_v2",
]
