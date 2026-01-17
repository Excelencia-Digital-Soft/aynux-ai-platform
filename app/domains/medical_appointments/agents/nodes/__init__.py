# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: LangGraph nodes for the medical appointments flow.
# ============================================================================
"""Medical Appointments LangGraph Nodes.

Contains all node implementations for the appointment booking conversation flow.
Each node handles a specific step in the booking process.
"""

from .appointment_management import AppointmentManagementNode
from .base import BaseNode
from .booking_confirmation import BookingConfirmationNode
from .date_selection import DateSelectionNode
from .fallback import FallbackNode
from .greeting import GreetingNode
from .human_handoff import HumanHandoffNode
from .patient_identification import PatientIdentificationNode
from .patient_registration import PatientRegistrationNode
from .provider_selection import ProviderSelectionNode
from .registry import NodeRegistry, get_node_registry
from .reschedule import RescheduleNode
from .router import RouterNode
from .specialty_selection import SpecialtySelectionNode
from .time_selection import TimeSelectionNode

__all__ = [
    # Base
    "BaseNode",
    # Registry
    "NodeRegistry",
    "get_node_registry",
    # Flow nodes
    "RouterNode",
    "GreetingNode",
    "PatientIdentificationNode",
    "PatientRegistrationNode",
    "SpecialtySelectionNode",
    "ProviderSelectionNode",
    "DateSelectionNode",
    "TimeSelectionNode",
    "BookingConfirmationNode",
    # Management nodes
    "AppointmentManagementNode",
    "RescheduleNode",
    "FallbackNode",
    # Routing nodes
    "HumanHandoffNode",
]
