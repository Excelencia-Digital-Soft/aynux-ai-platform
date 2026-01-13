"""
Legacy Pharmacy Flow V1 - DEPRECATED

This module contains the original pharmacy flow implementation with ~90 state fields
and complex routing logic. It has been superseded by the V2 implementation in
app/domains/pharmacy/agents/

DEPRECATION NOTICE:
- This module will be removed in version 2.0.0
- New development should use app/domains/pharmacy/agents/graph_v2.py
- For migration assistance, see app/domains/pharmacy/agents/state_v2.py

V2 Improvements:
- Simplified state (~30 fields vs ~90)
- Database-driven routing (routing_configs table)
- WhatsApp buttons/lists support
- Cleaner context switching

Migration Guide:
1. Import from app.domains.pharmacy.agents.graph_v2 instead
2. Use PharmacyStateV2 instead of PharmacyState
3. Use RouterSupervisor instead of PharmacyRouter
4. Use ResponseFormatter for WhatsApp message formatting

Example:
    # Old (deprecated)
    from app.domains.pharmacy.legacy.graph import PharmacyGraph
    from app.domains.pharmacy.legacy.state import PharmacyState

    # New (recommended)
    from app.domains.pharmacy.agents.graph_v2 import PharmacyGraphV2
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2
"""

import warnings

warnings.warn(
    "pharmacy.legacy module is deprecated. Use pharmacy.agents (V2) instead. "
    "This module will be removed in version 2.0.0. "
    "See app/domains/pharmacy/agents/graph_v2.py for the new implementation.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compatibility during transition period
# These imports will trigger the warning above when the module is imported

# Note: Actual re-exports would go here, but since we're just creating
# the structure, we'll leave this empty for now. The plan is to move
# the existing files here incrementally.

__all__: list[str] = []
