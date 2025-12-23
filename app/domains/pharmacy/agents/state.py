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

    # =========================================================================
    # Greeting State (daily tracking)
    # =========================================================================
    greeted_today: bool  # True if customer was greeted in current session/day
    last_greeting_date: str | None  # ISO date of last greeting (YYYY-MM-DD)
    pending_greeting: str | None  # Greeting to prepend to next response


# Alias for compatibility
PharmacyDomainState = PharmacyState
