"""
Pharmacy Domain State Schema

TypedDict-based state schema for the pharmacy domain LangGraph.
Handles customer identification, debt queries, confirmations, and invoice generation.
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


class PharmacyState(TypedDict):
    """
    Pharmacy domain state for LangGraph.

    Specialized state schema for handling pharmacy workflows:
    - Customer identification (from WhatsApp phone to Plex ID)
    - Debt checking (consulta deuda)
    - Confirmation (confirmar)
    - Invoice/receipt generation (generar factura/recibo)
    - Customer registration (for new customers)
    """

    # Core messages with LangGraph reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # =========================================================================
    # Customer Context (Original WhatsApp data)
    # =========================================================================
    customer_id: str | None  # WhatsApp phone number
    customer_name: str | None  # Display name (from Plex or registration)

    # =========================================================================
    # Plex Customer Identification
    # =========================================================================
    plex_customer_id: int | None  # Plex internal ID (e.g., 70)
    plex_customer: dict[str, Any] | None  # Full PlexCustomer data as dict
    customer_identified: bool  # True if Plex customer is resolved

    # Disambiguation state (multiple Plex matches)
    requires_disambiguation: bool  # Multiple customer matches found
    disambiguation_candidates: list[dict[str, Any]] | None  # List of candidate customers
    awaiting_document_input: bool  # Waiting for user to provide document

    # Phone normalization
    whatsapp_phone: str | None  # Original WhatsApp phone (e.g., 5493446405060)
    normalized_phone: str | None  # Phone normalized for Plex (e.g., 3446405060)

    # =========================================================================
    # Customer Registration (for new customers)
    # =========================================================================
    awaiting_registration_data: bool  # In registration flow
    registration_step: str | None  # "nombre", "documento", "confirmar", "complete"
    registration_data: dict[str, Any] | None  # Collected registration data
    registration_document: str | None  # Pre-provided document from identification (skips DNI step)

    # =========================================================================
    # Debt Context
    # =========================================================================
    debt_id: str | None  # Current debt being processed
    debt_data: dict[str, Any] | None  # Full debt information
    debt_status: str | None  # pending, confirmed, invoiced
    total_debt: float | None
    has_debt: bool

    # =========================================================================
    # Payment Context (Partial Payment Support)
    # =========================================================================
    payment_amount: float | None  # Amount customer wants to pay (can be partial)
    is_partial_payment: bool  # True if payment_amount < total_debt
    remaining_balance: float | None  # Balance after payment

    # =========================================================================
    # Mercado Pago Payment Context
    # =========================================================================
    mp_preference_id: str | None  # Mercado Pago preference ID
    mp_payment_id: str | None  # MP payment ID (after payment completes)
    mp_init_point: str | None  # Payment link URL
    mp_payment_status: str | None  # pending, approved, rejected, cancelled
    mp_external_reference: str | None  # Reference for webhook correlation (customer_id:debt_id:uuid)
    awaiting_payment: bool  # True when payment link sent, waiting for payment
    plex_receipt_number: str | None  # PLEX receipt after REGISTRAR_PAGO_CLIENTE (e.g., RC X 0001-00016790)
    plex_new_balance: float | None  # Customer's new balance after payment

    # =========================================================================
    # Invoice/Receipt Context
    # =========================================================================
    invoice_id: str | None
    invoice_number: str | None
    pdf_url: str | None
    receipt_number: str | None  # For payment receipts

    # =========================================================================
    # Workflow State (transactional flow)
    # =========================================================================
    workflow_step: str | None  # identify, check_debt, confirmation, invoice, registration
    awaiting_confirmation: bool  # Waiting for user to confirm debt
    confirmation_received: bool  # User confirmed

    # =========================================================================
    # Intent and Routing
    # =========================================================================
    current_intent: dict[str, Any] | None
    pharmacy_intent_type: str | None  # debt_query, confirm, invoice, register, data_query
    extracted_entities: dict[str, Any] | None  # Entities extracted from message (amount, date, etc.)

    # =========================================================================
    # Auto-Flow Flags (for intelligent routing)
    # =========================================================================
    auto_proceed_to_invoice: bool  # Auto-fetch debt then proceed to invoice
    auto_return_to_query: bool  # Return to data_query after debt fetch
    pending_data_query: str | None  # Pending question to answer after debt fetch

    # =========================================================================
    # Agent Flow State
    # =========================================================================
    current_agent: str | None
    next_agent: str | None
    agent_history: Annotated[list[str], add_agent_history]

    # =========================================================================
    # Retrieved Data
    # =========================================================================
    retrieved_data: Annotated[dict[str, Any], merge_retrieved_data]

    # =========================================================================
    # Control Flow
    # =========================================================================
    is_complete: bool
    is_out_of_scope: bool  # True if last response was out-of-scope
    out_of_scope_handled: bool  # True after out-of-scope response given (prevents loop)
    error_count: int
    max_errors: int
    requires_human: bool

    # =========================================================================
    # Routing Decisions
    # =========================================================================
    routing_decision: dict[str, Any] | None

    # =========================================================================
    # Conversation Metadata
    # =========================================================================
    conversation_id: str | None
    timestamp: str | None

    # =========================================================================
    # Bypass Indicator
    # =========================================================================
    is_bypass_route: bool  # True if came via bypass routing

    # =========================================================================
    # Multi-Tenant Context
    # =========================================================================
    organization_id: str | None  # Organization UUID for multi-tenant config lookup
    pharmacy_id: str | None  # Pharmacy UUID for pharmacy-specific config (MP credentials, etc.)

    # =========================================================================
    # Pharmacy Configuration (cached from DB)
    # =========================================================================
    pharmacy_name: str | None  # Pharmacy name for personalized responses
    pharmacy_phone: str | None  # Pharmacy phone for contact redirection

    # =========================================================================
    # Greeting State (daily tracking)
    # =========================================================================
    greeted_today: bool  # True if customer was greeted in current session/day
    last_greeting_date: str | None  # ISO date of last greeting (YYYY-MM-DD)
    pending_greeting: str | None  # Greeting to prepend to next response
    greeting_sent: bool  # True if greeting was sent this turn (prevents duplicates)

    # =========================================================================
    # Identification State (turn tracking)
    # =========================================================================
    just_identified: bool  # True if customer was just identified this turn
    identification_step: str | None  # "awaiting_identifier", "name", None
    identification_retries: int  # Number of identification attempts (max 3)

    # =========================================================================
    # Person Resolution State (NEW - Registered Persons Flow)
    # =========================================================================
    registered_persons: list[dict[str, Any]] | None  # List of valid registrations for this phone
    active_registered_person_id: str | None  # Selected registered person UUID
    awaiting_person_selection: bool  # Waiting for user to select a person from list
    awaiting_own_or_other: bool  # Waiting for "own debt" or "other's debt" answer
    is_querying_for_other: bool  # True if querying debt for someone else
    is_self: bool  # True if current customer is the phone owner

    # Person Selection State
    selection_list_shown: bool  # True if person selection list was displayed
    selection_options_map: dict[str, Any] | None  # Maps option numbers to person data
    include_self_in_list: bool  # Include phone owner in person selection list
    self_plex_customer: dict[str, Any] | None  # PLEX customer matching phone (is_self=True)

    # Account Selection State (for returning users with registered accounts)
    registered_accounts_for_selection: list[dict[str, Any]] | None  # List of registered accounts to select from
    account_count: int | None  # Number of accounts in selection list

    # Person Validation State
    validation_step: str | None  # "dni", "name", "confirm" - current validation step
    dni_requested: bool  # True if we already asked for DNI (distinguishes first time vs retry)
    pending_dni: str | None  # DNI being validated
    plex_candidates: list[dict[str, Any]] | None  # Multiple PLEX matches for disambiguation
    is_new_person_flow: bool  # True if user requested to add new person
    name_mismatch_count: int  # Count of name mismatches for retry limiting
    plex_customer_to_confirm: dict[str, Any] | None  # PLEX customer pending confirmation
    provided_name_to_confirm: str | None  # Name provided by user pending confirmation

    # Node Routing
    next_node: str | None  # Next node to route to (for explicit routing)

    # =========================================================================
    # Partial Payment Flow State
    # =========================================================================
    awaiting_partial_payment_question: bool  # Asked if user wants partial payment (after NO)
    awaiting_payment_amount_input: bool  # Waiting for user to enter amount
    partial_payment_declined: bool  # User said NO to partial payment too
    minimum_payment_amount: float | None  # Minimum allowed partial payment (from config)

    # =========================================================================
    # Smart Debt Negotiation State
    # =========================================================================
    auth_level: str | None  # "STRONG", "MEDIUM", "WEAK" - for context-based ofuscation
    payment_options_map: dict[str, float] | None  # Pre-calculated options {"full": 15000, "half": 7500, ...}
    selected_payment_option: str | None  # "full", "half", "minimum", "custom"
    awaiting_payment_option_selection: bool  # Waiting for user to select 1/2/3/4

    # =========================================================================
    # Entry Validation State (CASO 0 - pharmacy_flujo_mejorado_v2.md)
    # =========================================================================
    validation_passed: bool  # True if entry validation passed
    rate_limited: bool  # True if user is rate limited
    rate_limit_reason: str | None  # Reason for rate limiting
    message_id: str | None  # WhatsApp message ID for deduplication
    is_within_service_hours: bool  # True if within bot service hours
    service_hours_message: str | None  # Message to show if outside hours
    emergency_phone: str | None  # Emergency contact number

    # =========================================================================
    # Menu Navigation State (CASO 2 - pharmacy_flujo_mejorado_v2.md)
    # =========================================================================
    current_menu: str | None  # "main", "help", "debt_action", "payment_problem"
    menu_history: list[str] | None  # Navigation history for "volver"
    show_reduced_menu: bool  # True to show reduced menu for recurring users
    first_interaction_today: bool  # True if this is first interaction today
    last_interaction_date: str | None  # ISO date YYYY-MM-DD of last interaction

    # =========================================================================
    # Debt Action Menu State (CASO 3 - pharmacy_flujo_mejorado_v2.md)
    # =========================================================================
    awaiting_debt_action: bool  # Waiting for user to select 1/2/3/4 after debt display
    debt_items: list[dict[str, Any]] | None  # Detailed invoice items from PLEX
    debt_fetched_at: str | None  # ISO timestamp when debt was fetched

    # =========================================================================
    # Payment Confirmation State (CASO 4 - pharmacy_flujo_mejorado_v2.md)
    # =========================================================================
    awaiting_payment_confirmation: bool  # Waiting for SI/NO before generating link
    payment_confirmation_shown: bool  # True if confirmation message was shown

    # =========================================================================
    # Help Center State (CASO 8 - pharmacy_flujo_mejorado_v2.md)
    # =========================================================================
    help_submenu: str | None  # "payment_problem", "debt_dispute", None
    escalation_reason: str | None  # Reason for human escalation
    wants_callback_notification: bool  # User wants callback when agent available

    # =========================================================================
    # Interruption Handling State (pharmacy_flujo_mejorado_v2.md)
    # =========================================================================
    pending_flow: str | None  # Flow that was interrupted (e.g., "payment_confirmation")
    pending_flow_context: dict[str, Any] | None  # Context of interrupted flow

    # =========================================================================
    # Person Selection Pagination (CASO 9 - pharmacy_flujo_mejorado_v2.md)
    # =========================================================================
    person_selection_page: int  # Current page in person selection (0-indexed)
    person_selection_total_pages: int  # Total pages available


# =============================================================================
# Domain State Registry Interface
# =============================================================================
# These module-level constants and functions enable auto-discovery by
# DomainStateRegistry for generic state management.

DOMAIN_KEY = "pharmacy"
"""Domain key for registry discovery."""

STATE_CLASS = PharmacyState
"""State TypedDict class for this domain."""


def get_state_defaults() -> dict[str, Any]:
    """
    Return default values for all pharmacy state fields.

    Used by DomainStateRegistry for generic state initialization.
    """
    return {
        # Core messages (handled by reducer, but need initial value)
        "messages": [],
        # Customer Context
        "customer_id": None,
        "customer_name": None,
        # Plex Customer Identification
        "plex_customer_id": None,
        "plex_customer": None,
        "customer_identified": False,
        "requires_disambiguation": False,
        "disambiguation_candidates": None,
        "awaiting_document_input": False,
        "whatsapp_phone": None,
        "normalized_phone": None,
        # Customer Registration
        "awaiting_registration_data": False,
        "registration_step": None,
        "registration_data": None,
        "registration_document": None,
        # Debt Context
        "debt_id": None,
        "debt_data": None,
        "debt_status": None,
        "total_debt": None,
        "has_debt": False,
        # Payment Context
        "payment_amount": None,
        "is_partial_payment": False,
        "remaining_balance": None,
        # Mercado Pago Payment Context
        "mp_preference_id": None,
        "mp_payment_id": None,
        "mp_init_point": None,
        "mp_payment_status": None,
        "mp_external_reference": None,
        "awaiting_payment": False,
        "plex_receipt_number": None,
        "plex_new_balance": None,
        # Invoice/Receipt Context
        "invoice_id": None,
        "invoice_number": None,
        "pdf_url": None,
        "receipt_number": None,
        # Workflow State
        "workflow_step": None,
        "awaiting_confirmation": False,
        "confirmation_received": False,
        # Intent and Routing
        "current_intent": None,
        "pharmacy_intent_type": None,
        "extracted_entities": None,
        # Auto-Flow Flags
        "auto_proceed_to_invoice": False,
        "auto_return_to_query": False,
        "pending_data_query": None,
        # Agent Flow State
        "current_agent": None,
        "next_agent": None,
        "agent_history": [],
        # Retrieved Data
        "retrieved_data": {},
        # Control Flow
        "is_complete": False,
        "is_out_of_scope": False,
        "out_of_scope_handled": False,
        "error_count": 0,
        "max_errors": 3,
        "requires_human": False,
        # Routing Decisions
        "routing_decision": None,
        # Conversation Metadata
        "conversation_id": None,
        "timestamp": None,
        # Bypass Indicator
        "is_bypass_route": False,
        # Multi-Tenant Context
        "organization_id": None,
        "pharmacy_id": None,
        # Pharmacy Configuration
        "pharmacy_name": None,
        "pharmacy_phone": None,
        # Greeting State
        "greeted_today": False,
        "last_greeting_date": None,
        "pending_greeting": None,
        "greeting_sent": False,
        # Identification State
        "just_identified": False,
        "identification_step": None,
        "identification_retries": 0,
        # Person Resolution State
        "registered_persons": None,
        "active_registered_person_id": None,
        "awaiting_person_selection": False,
        "awaiting_own_or_other": False,
        "is_querying_for_other": False,
        "is_self": False,
        # Person Selection State
        "selection_list_shown": False,
        "selection_options_map": None,
        "include_self_in_list": False,
        "self_plex_customer": None,
        # Account Selection State
        "registered_accounts_for_selection": None,
        "account_count": None,
        # Person Validation State
        "validation_step": None,
        "dni_requested": False,
        "pending_dni": None,
        "plex_candidates": None,
        "is_new_person_flow": False,
        "name_mismatch_count": 0,
        "plex_customer_to_confirm": None,
        "provided_name_to_confirm": None,
        # Node Routing
        "next_node": None,
        # Partial Payment Flow State
        "awaiting_partial_payment_question": False,
        "awaiting_payment_amount_input": False,
        "partial_payment_declined": False,
        "minimum_payment_amount": None,
        # Smart Debt Negotiation State
        "auth_level": None,
        "payment_options_map": None,
        "selected_payment_option": None,
        "awaiting_payment_option_selection": False,
        # Entry Validation State
        "validation_passed": False,
        "rate_limited": False,
        "rate_limit_reason": None,
        "message_id": None,
        "is_within_service_hours": False,
        "service_hours_message": None,
        "emergency_phone": None,
        # Menu Navigation State
        "current_menu": None,
        "menu_history": None,
        "show_reduced_menu": False,
        "first_interaction_today": False,
        "last_interaction_date": None,
        # Debt Action Menu State
        "awaiting_debt_action": False,
        "debt_items": None,
        "debt_fetched_at": None,
        # Payment Confirmation State
        "awaiting_payment_confirmation": False,
        "payment_confirmation_shown": False,
        # Help Center State
        "help_submenu": None,
        "escalation_reason": None,
        "wants_callback_notification": False,
        # Interruption Handling State
        "pending_flow": None,
        "pending_flow_context": None,
        # Person Selection Pagination
        "person_selection_page": 0,
        "person_selection_total_pages": 0,
    }


# Alias for compatibility
PharmacyDomainState = PharmacyState
