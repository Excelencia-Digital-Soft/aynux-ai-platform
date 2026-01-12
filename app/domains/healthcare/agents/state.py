"""
Healthcare Domain State Schema

TypedDict-based state schema for the healthcare domain LangGraph.
Specialized for managing patient appointments, medical records, and triage.
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def add_agent_responses(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reducer for agent responses."""
    return left + right


def merge_retrieved_data(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer for retrieved data (merge dictionaries)."""
    return {**left, **right}


def add_agent_history(left: list[str], right: list[str]) -> list[str]:
    """Reducer for agent history."""
    return left + right


class HealthcareState(TypedDict):
    """
    Healthcare domain state for LangGraph.

    Specialized state schema for handling patient appointments,
    medical records, triage, and healthcare-related queries.
    """

    # Core messages with LangGraph reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Patient context
    patient: dict[str, Any] | None
    patient_id: int | None
    patient_phone: str | None

    # Healthcare specific context
    current_appointment: dict[str, Any] | None  # Active appointment being discussed
    upcoming_appointments: list[dict[str, Any]] | None
    medical_history: dict[str, Any] | None

    # Intent and routing
    current_intent: dict[str, Any] | None
    healthcare_intent_type: str | None  # appointment_booking, patient_records, triage, doctor_search, etc.

    # Agent flow state
    current_agent: str | None
    next_agent: str | None
    agent_history: Annotated[list[str], add_agent_history]

    # Responses and data
    agent_responses: Annotated[list[dict[str, Any]], add_agent_responses]
    retrieved_data: Annotated[dict[str, Any], merge_retrieved_data]

    # Appointment specific
    available_slots: list[dict[str, Any]] | None
    selected_slot: dict[str, Any] | None
    appointment_confirmation: dict[str, Any] | None
    doctor_info: dict[str, Any] | None

    # Triage specific
    triage_priority: str | None
    symptoms: list[str] | None
    vital_signs: dict[str, Any] | None
    wait_time_estimate: int | None  # Minutes

    # Medical records specific
    recent_visits: list[dict[str, Any]] | None
    prescriptions: list[dict[str, Any]] | None
    lab_results: list[dict[str, Any]] | None

    # Emergency handling
    is_emergency: bool
    emergency_instructions: str | None

    # Control flow
    is_complete: bool
    error_count: int
    max_errors: int
    requires_human: bool

    # Routing decisions
    routing_decision: dict[str, Any] | None

    # Conversation metadata
    conversation_id: str | None
    timestamp: str | None


# =============================================================================
# Domain State Registry Interface
# =============================================================================
# These module-level constants and functions enable auto-discovery by
# DomainStateRegistry for generic state management.

DOMAIN_KEY = "healthcare"
"""Domain key for registry discovery."""

STATE_CLASS = HealthcareState
"""State TypedDict class for this domain."""


def get_state_defaults() -> dict[str, Any]:
    """
    Return default values for all healthcare state fields.

    Used by DomainStateRegistry for generic state initialization.
    """
    return {
        # Core messages
        "messages": [],
        # Patient context
        "patient": None,
        "patient_id": None,
        "patient_phone": None,
        # Healthcare specific context
        "current_appointment": None,
        "upcoming_appointments": None,
        "medical_history": None,
        # Intent and routing
        "current_intent": None,
        "healthcare_intent_type": None,
        # Agent flow state
        "current_agent": None,
        "next_agent": None,
        "agent_history": [],
        # Responses and data
        "agent_responses": [],
        "retrieved_data": {},
        # Appointment specific
        "available_slots": None,
        "selected_slot": None,
        "appointment_confirmation": None,
        "doctor_info": None,
        # Triage specific
        "triage_priority": None,
        "symptoms": None,
        "vital_signs": None,
        "wait_time_estimate": None,
        # Medical records specific
        "recent_visits": None,
        "prescriptions": None,
        "lab_results": None,
        # Emergency handling
        "is_emergency": False,
        "emergency_instructions": None,
        # Control flow
        "is_complete": False,
        "error_count": 0,
        "max_errors": 3,
        "requires_human": False,
        # Routing decisions
        "routing_decision": None,
        # Conversation metadata
        "conversation_id": None,
        "timestamp": None,
    }


# Alias for compatibility
HealthcareDomainState = HealthcareState
