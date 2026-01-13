"""
Pharmacy Domain State Schema V2

Simplified TypedDict-based state schema for the refactored pharmacy domain LangGraph.
Reduces from ~90 fields to ~30 essential fields for cleaner state management.

Changes from V1:
- Consolidated awaiting_* flags into single `awaiting_input` field
- Removed deprecated greeting/identification flow fields
- Simplified person resolution to `registered_accounts` and `current_account_id`
- Added WhatsApp response fields for buttons/lists
- Added `state_version` for migration compatibility
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def merge_retrieved_data(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer for retrieved data."""
    return {**left, **right}


def add_agent_history(left: list[str], right: list[str]) -> list[str]:
    """Reducer for agent history."""
    return left + right


class PharmacyStateV2(TypedDict):
    """
    Simplified pharmacy domain state for LangGraph V2.

    Organized into logical groups:
    1. Core Messages (~1 field)
    2. Identification (~7 fields)
    3. Account (~4 fields)
    4. Debt (~5 fields)
    5. Payment (~6 fields)
    6. Routing & Control (~8 fields)
    7. WhatsApp Response (~3 fields)
    8. Multi-tenant (~3 fields)

    Total: ~37 fields (down from ~90 in V1)
    """

    # =========================================================================
    # State Version (for migration compatibility)
    # =========================================================================
    state_version: int  # Always 2 for V2 state

    # =========================================================================
    # Core Messages (1 field)
    # =========================================================================
    messages: Annotated[list[BaseMessage], add_messages]

    # =========================================================================
    # Identification (7 fields)
    # =========================================================================
    user_phone: str | None  # WhatsApp phone number (e.g., 5493446405060)
    plex_user_id: int | None  # PLEX internal customer ID
    plex_customer: dict[str, Any] | None  # Full PLEX customer data
    is_authenticated: bool  # True if customer is identified and verified
    customer_name: str | None  # Display name for personalization
    auth_level: str | None  # "STRONG", "MEDIUM", "WEAK" for obfuscation rules
    pending_dni: str | None  # DNI being validated (during auth flow)

    # =========================================================================
    # Account Selection (4 fields)
    # =========================================================================
    current_account_id: str | None  # Selected RegisteredPerson UUID
    registered_accounts: list[dict[str, Any]] | None  # Valid accounts for this phone
    awaiting_account_selection: bool  # Waiting for user to pick from list
    is_self: bool  # True if current query is for phone owner

    # =========================================================================
    # Debt Context (5 fields)
    # =========================================================================
    total_debt: float | None  # Current total debt amount
    debt_items: list[dict[str, Any]] | None  # Detailed invoice items
    has_debt: bool  # Quick check for debt existence
    debt_fetched_at: str | None  # ISO timestamp of last fetch
    debt_id: str | None  # Current debt being processed

    # =========================================================================
    # Payment Context (6 fields)
    # =========================================================================
    payment_amount: float | None  # Amount customer wants to pay
    is_partial_payment: bool  # True if paying less than total
    mp_payment_link: str | None  # Mercado Pago payment URL
    mp_payment_status: str | None  # pending, approved, rejected, cancelled
    mp_external_reference: str | None  # Reference for webhook correlation
    awaiting_payment_confirmation: bool  # Waiting for SI/NO before link

    # =========================================================================
    # Routing & Control (8 fields)
    # =========================================================================
    intent: str | None  # Current intent (check_debt, pay, switch_account, etc.)
    previous_intent: str | None  # For context switching/back navigation
    awaiting_input: str | None  # What input we're waiting for (dni, name, amount, etc.)
    current_node: str | None  # Current node being executed
    next_node: str | None  # Next node to route to
    is_complete: bool  # True when conversation flow is complete
    error_count: int  # Number of consecutive errors
    requires_human: bool  # True if human escalation is needed

    # =========================================================================
    # WhatsApp Response Formatting (3 fields)
    # =========================================================================
    response_type: str | None  # "text", "buttons", or "list"
    response_buttons: list[dict[str, str]] | None  # Button configs [{id, titulo}]
    response_list_items: list[dict[str, str]] | None  # List items [{id, titulo, descripcion}]

    # =========================================================================
    # Multi-Tenant Context (3 fields)
    # =========================================================================
    organization_id: str | None  # Organization UUID
    pharmacy_id: str | None  # Pharmacy UUID for config lookup
    pharmacy_name: str | None  # Pharmacy name for responses

    # =========================================================================
    # Agent Flow State (from V1, kept for compatibility)
    # =========================================================================
    agent_history: Annotated[list[str], add_agent_history]
    retrieved_data: Annotated[dict[str, Any], merge_retrieved_data]

    # =========================================================================
    # Conversation Metadata (2 fields)
    # =========================================================================
    conversation_id: str | None
    timestamp: str | None


# =============================================================================
# Domain State Registry Interface
# =============================================================================

DOMAIN_KEY = "pharmacy_v2"
"""Domain key for V2 state registry discovery."""

STATE_CLASS = PharmacyStateV2
"""State TypedDict class for this domain."""


def get_state_defaults() -> dict[str, Any]:
    """
    Return default values for all pharmacy V2 state fields.

    Used by DomainStateRegistry for generic state initialization.
    """
    return {
        # State version
        "state_version": 2,
        # Core messages
        "messages": [],
        # Identification
        "user_phone": None,
        "plex_user_id": None,
        "plex_customer": None,
        "is_authenticated": False,
        "customer_name": None,
        "auth_level": None,
        "pending_dni": None,
        # Account Selection
        "current_account_id": None,
        "registered_accounts": None,
        "awaiting_account_selection": False,
        "is_self": False,
        # Debt Context
        "total_debt": None,
        "debt_items": None,
        "has_debt": False,
        "debt_fetched_at": None,
        "debt_id": None,
        # Payment Context
        "payment_amount": None,
        "is_partial_payment": False,
        "mp_payment_link": None,
        "mp_payment_status": None,
        "mp_external_reference": None,
        "awaiting_payment_confirmation": False,
        # Routing & Control
        "intent": None,
        "previous_intent": None,
        "awaiting_input": None,
        "current_node": None,
        "next_node": None,
        "is_complete": False,
        "error_count": 0,
        "requires_human": False,
        # WhatsApp Response
        "response_type": None,
        "response_buttons": None,
        "response_list_items": None,
        # Multi-Tenant
        "organization_id": None,
        "pharmacy_id": None,
        "pharmacy_name": None,
        # Agent Flow (from V1)
        "agent_history": [],
        "retrieved_data": {},
        # Conversation Metadata
        "conversation_id": None,
        "timestamp": None,
    }


# =============================================================================
# State Migration Utilities
# =============================================================================


# Field mapping from V1 to V2 state
V1_TO_V2_FIELD_MAP: dict[str, str | None] = {
    # Identification
    "customer_id": "user_phone",
    "whatsapp_phone": "user_phone",
    "plex_customer_id": "plex_user_id",
    "customer_identified": "is_authenticated",
    # Account
    "active_registered_person_id": "current_account_id",
    "registered_persons": "registered_accounts",
    "awaiting_person_selection": "awaiting_account_selection",
    # Debt
    "total_debt": "total_debt",
    "debt_items": "debt_items",
    "has_debt": "has_debt",
    "debt_fetched_at": "debt_fetched_at",
    "debt_id": "debt_id",
    # Payment
    "payment_amount": "payment_amount",
    "is_partial_payment": "is_partial_payment",
    "mp_init_point": "mp_payment_link",
    "mp_payment_status": "mp_payment_status",
    "mp_external_reference": "mp_external_reference",
    "awaiting_payment_confirmation": "awaiting_payment_confirmation",
    # Routing
    "pharmacy_intent_type": "intent",
    "next_agent": "next_node",
    "current_agent": "current_node",
    # Control
    "is_complete": "is_complete",
    "error_count": "error_count",
    "requires_human": "requires_human",
    # Multi-tenant
    "organization_id": "organization_id",
    "pharmacy_id": "pharmacy_id",
    "pharmacy_name": "pharmacy_name",
    # Conversation
    "conversation_id": "conversation_id",
    "timestamp": "timestamp",
    # Deprecated fields (mapped to None = dropped)
    "greeting_sent": None,
    "pending_greeting": None,
    "greeted_today": None,
    "last_greeting_date": None,
    "just_identified": None,
    "identification_step": None,
    "identification_retries": None,
    "validation_step": None,
    "dni_requested": None,
    "plex_candidates": None,
    "is_new_person_flow": None,
    "name_mismatch_count": None,
    "plex_customer_to_confirm": None,
    "provided_name_to_confirm": None,
    "selection_list_shown": None,
    "selection_options_map": None,
    "include_self_in_list": None,
    "self_plex_customer": None,
    "registered_accounts_for_selection": None,
    "account_count": None,
    "awaiting_own_or_other": None,
    "is_querying_for_other": None,
    "awaiting_partial_payment_question": None,
    "awaiting_payment_amount_input": None,
    "partial_payment_declined": None,
    "minimum_payment_amount": None,
    "payment_options_map": None,
    "selected_payment_option": None,
    "awaiting_payment_option_selection": None,
    "awaiting_debt_action": None,
    "current_menu": None,
    "menu_history": None,
    "show_reduced_menu": None,
    "first_interaction_today": None,
    "last_interaction_date": None,
    "pending_flow": None,
    "pending_flow_context": None,
    "help_submenu": None,
    "escalation_reason": None,
    "wants_callback_notification": None,
    "person_selection_page": None,
    "person_selection_total_pages": None,
    "validation_passed": None,
    "rate_limited": None,
    "rate_limit_reason": None,
    "message_id": None,
    "is_within_service_hours": None,
    "service_hours_message": None,
    "emergency_phone": None,
    "payment_confirmation_shown": None,
}


def migrate_v1_to_v2(v1_state: dict[str, Any]) -> dict[str, Any]:
    """
    Migrate V1 state to V2 format.

    Args:
        v1_state: State dictionary from V1 format

    Returns:
        State dictionary in V2 format with defaults for new fields
    """
    v2_state = get_state_defaults()

    for v1_field, v2_field in V1_TO_V2_FIELD_MAP.items():
        if v2_field is not None and v1_field in v1_state:
            v1_value = v1_state[v1_field]
            if v1_value is not None:
                v2_state[v2_field] = v1_value

    # Handle messages specially (needs reducer)
    if "messages" in v1_state:
        v2_state["messages"] = v1_state["messages"]

    # Handle reducers
    if "agent_history" in v1_state:
        v2_state["agent_history"] = v1_state["agent_history"]
    if "retrieved_data" in v1_state:
        v2_state["retrieved_data"] = v1_state["retrieved_data"]

    # Consolidate awaiting_* flags into awaiting_input
    awaiting_fields = [
        ("awaiting_document_input", "dni"),
        ("awaiting_person_selection", "account_selection"),
        ("awaiting_own_or_other", "own_or_other"),
        ("awaiting_payment_amount_input", "amount"),
        ("awaiting_payment_confirmation", "payment_confirmation"),
        ("awaiting_payment_option_selection", "payment_option"),
        ("awaiting_debt_action", "debt_action"),
    ]

    for v1_flag, input_type in awaiting_fields:
        if v1_state.get(v1_flag):
            v2_state["awaiting_input"] = input_type
            break

    return v2_state


def is_v2_state(state: dict[str, Any]) -> bool:
    """Check if state is V2 format."""
    return state.get("state_version") == 2


# Alias for backward compatibility during transition
PharmacyState = PharmacyStateV2
