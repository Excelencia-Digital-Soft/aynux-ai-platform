"""PersonResolution node package - Entry point for pharmacy flow."""

# Re-export Pydantic state models for convenience
from app.domains.pharmacy.agents.models import (
    PreservedContext,
    StatePreserver,
)
from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    MAX_IDENTIFICATION_RETRIES,
    NAME_MATCH_THRESHOLD,
    STEP_AWAITING_IDENTIFIER,
    STEP_AWAITING_WELCOME,
    STEP_NAME,
)
from app.domains.pharmacy.agents.nodes.person_resolution.factory import (
    PersonResolutionFactory,
)
from app.domains.pharmacy.agents.nodes.person_resolution.node import (
    PersonResolutionNode,
)

__all__ = [
    # Node and Factory
    "PersonResolutionNode",
    "PersonResolutionFactory",
    # Constants
    "STEP_AWAITING_WELCOME",
    "STEP_AWAITING_IDENTIFIER",
    "STEP_NAME",
    "MAX_IDENTIFICATION_RETRIES",
    "NAME_MATCH_THRESHOLD",
    # Pydantic state models (replaces PRESERVED_STATE_FIELDS)
    "PreservedContext",
    "StatePreserver",
    # NOTE: WELCOME_OPTIONS, OWN_INDICATORS, OTHER_INDICATORS moved to database
    # Use domain_intent_cache.get_patterns() to load patterns from DB
]
