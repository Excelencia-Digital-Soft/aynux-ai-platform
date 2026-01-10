"""Medical Appointments State Definition.

TypedDict for LangGraph state management in the medical appointments flow.
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


def add_agent_history(left: list[str], right: list[str]) -> list[str]:
    """Reducer para historial de agentes."""
    return left + right


class MedicalAppointmentsState(TypedDict, total=False):
    """Estado del flujo de turnos médicos.

    Contains all context needed for the appointment booking conversation,
    including patient data, selection state, and flow control.
    """

    # LangGraph messages (with reducer)
    messages: Annotated[list[BaseMessage], add_messages]

    # User identification
    user_phone: str | None
    wa_id: str | None

    # Patient context
    patient_document: str | None
    patient_phone: str | None
    patient_data: dict[str, Any] | None
    patient_id: str | None
    patient_name: str | None
    is_registered: bool

    # Booking flow selections
    selected_specialty: str | None
    selected_specialty_name: str | None
    selected_provider: dict[str, Any] | None
    selected_provider_id: str | None
    selected_provider_name: str | None
    selected_date: str | None
    selected_time: str | None

    # Lists for selection (populated by SOAP calls)
    specialties_list: list[dict[str, Any]] | None
    providers_list: list[dict[str, Any]] | None
    available_dates: list[str] | None
    available_times: list[str] | None

    # Pagination for provider selection
    current_page: int
    total_pages: int
    items_per_page: int

    # Current/confirmed appointment
    current_appointment: dict[str, Any] | None
    appointment_id: str | None
    suggested_appointment: dict[str, Any] | None

    # Institution
    institution: str  # "mercedario" | "patologia_digestiva"
    institution_id: str | None

    # Flow control
    current_node: str | None
    next_node: str | None
    previous_node: str | None
    agent_history: Annotated[list[str], add_agent_history]

    # Intent detection
    detected_intent: str | None
    awaiting_confirmation: bool

    # State flags
    is_complete: bool
    needs_registration: bool
    is_rescheduling: bool

    # Error handling
    error_count: int
    last_error: str | None
    max_errors: int

    # RAG context
    rag_context: str | None
    agent_knowledge_context: str | None

    # Response formatting
    response_text: str | None
    response_buttons: list[dict[str, Any]] | None


def get_initial_state(
    institution: str = "patologia_digestiva",
    user_phone: str | None = None,
) -> MedicalAppointmentsState:
    """Create initial state for a new conversation.

    Args:
        institution: Institution identifier.
        user_phone: User's WhatsApp number.

    Returns:
        Initial state dictionary.
    """
    return MedicalAppointmentsState(
        messages=[],
        user_phone=user_phone,
        wa_id=user_phone,
        patient_document=None,
        patient_phone=user_phone,
        patient_data=None,
        patient_id=None,
        patient_name=None,
        is_registered=False,
        selected_specialty=None,
        selected_specialty_name=None,
        selected_provider=None,
        selected_provider_id=None,
        selected_provider_name=None,
        selected_date=None,
        selected_time=None,
        specialties_list=None,
        providers_list=None,
        available_dates=None,
        available_times=None,
        current_page=0,
        total_pages=0,
        items_per_page=5,
        current_appointment=None,
        appointment_id=None,
        suggested_appointment=None,
        institution=institution,
        institution_id=None,
        current_node=None,
        next_node=None,
        previous_node=None,
        agent_history=[],
        detected_intent=None,
        awaiting_confirmation=False,
        is_complete=False,
        needs_registration=False,
        is_rescheduling=False,
        error_count=0,
        last_error=None,
        max_errors=3,
        rag_context=None,
        agent_knowledge_context=None,
        response_text=None,
        response_buttons=None,
    )
