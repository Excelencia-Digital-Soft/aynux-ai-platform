"""
Pydantic models for Pharmacy domain state management.

These models provide type-safe state preservation across node transitions,
ensuring that context is not lost as users flow through the pharmacy graph.
"""

from app.domains.pharmacy.agents.models.debt import DebtContext
from app.domains.pharmacy.agents.models.identification import IdentificationState
from app.domains.pharmacy.agents.models.payment import PaymentContext
from app.domains.pharmacy.agents.models.pharmacy_config import PharmacyConfig
from app.domains.pharmacy.agents.models.preserved_context import (
    PreservedContext,
    StatePreserver,
)
from app.domains.pharmacy.agents.models.welcome_flow import WelcomeFlowState

__all__ = [
    # Core preservation
    "PreservedContext",
    "StatePreserver",
    # Domain models
    "PharmacyConfig",
    "IdentificationState",
    "PaymentContext",
    "DebtContext",
    # Flow-specific models
    "WelcomeFlowState",
]
